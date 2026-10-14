import json

import frappe
from frappe import _
from frappe.model.document import Document


class AgentDefinition(Document):
	def validate(self):
		for field, label in (
			("max_steps", _("Max Steps")),
			("max_runtime_s", _("Max Runtime")),
			("token_budget", _("Token Budget")),
		):
			if (self.get(field) or 0) <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(label))
		if self.output_schema:
			try:
				json.loads(self.output_schema)
			except ValueError:
				frappe.throw(_("Output Schema must be valid JSON."))
		if self.status == "Active" and not self.model_config:
			frappe.throw(_("An active agent needs a Model Configuration."))
		if self.mode != "readonly" and not self.approval_required:
			frappe.throw(
				_("Agents that can prepare documents must keep Human Approval Required switched on.")
			)
		self.validate_tools()
		self.validate_evaluation()

	def validate_evaluation(self):
		"""An agent with a workflow goes live only after its current version passed a live evaluation."""
		previous = self.get_doc_before_save()
		activating = self.status == "Active" and (
			not previous or previous.status != "Active" or previous.version != self.version
		)
		if not activating or not self.workflow_key:
			return
		latest = frappe.get_all(
			"Agent Evaluation",
			filters={
				"agent": self.name,
				"agent_version": self.version,
				"mode": "Live",
				"status": "Completed",
			},
			fields=["name", "passed", "total"],
			order_by="creation desc",
			limit=1,
		)
		if not latest or latest[0].passed != latest[0].total:
			frappe.throw(
				_(
					"Before activating version {0}, run the evaluation suite in Live mode (Runs & Traces > Evaluation suite) and make sure every scenario passes."
				).format(self.version)
				+ (
					" "
					+ _("Latest: {0}/{1} passed ({2}).").format(
						latest[0].passed, latest[0].total, latest[0].name
					)
					if latest
					else ""
				)
			)

	def validate_tools(self):
		seen = set()
		for row in self.tools:
			if row.tool in seen:
				frappe.throw(_("Tool {0} is listed more than once.").format(frappe.bold(row.tool)))
			seen.add(row.tool)
			access, status = frappe.db.get_value("Agent Tool", row.tool, ["access", "status"])
			if status == "Blocked for agents" or access == "Write (submit)":
				frappe.throw(_("Tool {0} may not be given to agents.").format(frappe.bold(row.tool)))
			if self.mode == "readonly" and access != "Read":
				frappe.throw(
					_(
						"Read-only agents cannot use write tool {0}. Change the autonomy mode or remove the tool."
					).format(frappe.bold(row.tool))
				)
