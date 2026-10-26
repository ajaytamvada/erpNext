import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from pridict.automation import guards, triggers
from pridict.automation import spec as specs

# Roles every user has; they never count as privileges for the Run As rule.
AUTOMATIC_ROLES = {"All", "Guest", "Desk User"}


def check_run_as(run_as: str, user: str | None = None):
	"""An admin may only run automations as a user whose roles are a subset of their own."""
	user = user or frappe.session.user
	if not run_as or user == "Administrator" or run_as == user:
		return
	extra = set(frappe.get_roles(run_as)) - set(frappe.get_roles(user)) - AUTOMATIC_ROLES
	if extra:
		frappe.throw(
			_("You cannot run automations as {0}: that user has roles you do not have ({1}).").format(
				run_as, ", ".join(sorted(extra))
			),
			frappe.PermissionError,
		)


class Automation(Document):
	def before_insert(self):
		if not self.run_as:
			self.run_as = guards.settings().default_run_as or frappe.session.user
		self.status = "Draft"
		self.active_version = None

	def validate(self):
		spec = specs.load(self.draft_spec or "{}")
		spec["title"] = self.title
		if self.description:
			spec["description"] = self.description
		self.draft_spec = json.dumps(spec, indent=1, ensure_ascii=False)
		if not self.active_version:
			# Until the first activation, show the draft's trigger in lists.
			self.update(specs.trigger_summary(spec))
		if self.is_new() or self.has_value_changed("run_as"):
			check_run_as(self.run_as)
		if self.has_value_changed("draft_spec") and not self.is_new():
			self.draft_revision = (self.draft_revision or 0) + 1
			if not self.flags.from_ops:
				self.flags.log_direct_edit = True
		if not self.flags.status_change and not self.is_new() and self.has_value_changed("status"):
			frappe.throw(_("Use Activate, Pause or Resume to change the status."))

	def on_update(self):
		if self.flags.log_direct_edit:
			log_change(self, "api", _("Edited the spec directly"), None)
		triggers.clear_index()

	def on_trash(self):
		if frappe.db.exists("Agent Run", {"automation": self.name}):
			frappe.throw(_("This automation has runs. Archive it instead of deleting it."))
		for doctype in ("Automation Change", "Automation Version"):
			frappe.db.delete(doctype, {"automation": self.name})
		# The builder chat belongs to the automation and goes with it.
		self.db_set("conversation", None, update_modified=False)
		for conversation in frappe.get_all(
			"Assistant Conversation", filters={"automation": self.name}, pluck="name"
		):
			frappe.delete_doc("Assistant Conversation", conversation, ignore_permissions=True, force=True)
		triggers.clear_index()

	# --- lifecycle ------------------------------------------------------------

	def activate(self, change_note: str | None = None) -> str:
		"""Freeze the draft into a new version and make it the one triggers run."""
		self.check_permission("write")
		check_run_as(self.run_as)
		spec = specs.load(self.draft_spec or "{}")
		errors = [
			issue["message"]
			for issue in specs.validate(spec, live=True, run_as=self.run_as)
			if issue["level"] == "error"
		]
		if errors:
			frappe.throw(
				_("Fix these problems before activating:") + "<br>" + "<br>".join(map(frappe.bold, errors))
			)
		spec_hash = specs.spec_hash(spec)
		current = self.active_version and frappe.db.get_value(
			"Automation Version", self.active_version, "spec_hash"
		)
		if current != spec_hash:
			number = (
				frappe.db.get_value("Automation Version", {"automation": self.name}, "max(version)") or 0
			) + 1
			version = frappe.get_doc(
				{
					"doctype": "Automation Version",
					"automation": self.name,
					"version": number,
					"spec": json.dumps(spec, indent=1, ensure_ascii=False),
					"spec_hash": spec_hash,
					"activated_by": frappe.session.user,
					"activated_at": now_datetime(),
					"change_note": change_note,
				}
			).insert(ignore_permissions=True)
			self.active_version = version.name
		self.update(specs.trigger_summary(spec))
		self.consecutive_failures = 0
		self.paused_reason = None
		if self.trigger_type == "trigger.schedule":
			# Start counting from now, not from past slots.
			self.last_fired_at = now_datetime()
		self._set_status("Active")
		return self.active_version

	def pause(self, reason: str | None = None):
		self.check_permission("write")
		self.paused_reason = reason or _("Paused by {0}").format(frappe.session.user)
		self._set_status("Paused")

	def resume(self):
		self.check_permission("write")
		if not self.active_version:
			frappe.throw(_("Activate the automation first."))
		self.consecutive_failures = 0
		self.paused_reason = None
		if self.trigger_type == "trigger.schedule":
			self.last_fired_at = now_datetime()
		self._set_status("Active")

	def disable(self):
		self.check_permission("write")
		self._set_status("Disabled")

	def _set_status(self, status: str):
		self.status = status
		self.flags.status_change = True
		self.save()


def log_change(doc, source: str, summary: str, ops):
	frappe.get_doc(
		{
			"doctype": "Automation Change",
			"automation": doc.name,
			"revision": doc.draft_revision,
			"source": source,
			"summary": summary,
			"ops": json.dumps(ops, ensure_ascii=False) if ops is not None else None,
			"spec": doc.draft_spec,
		}
	).insert(ignore_permissions=True)
