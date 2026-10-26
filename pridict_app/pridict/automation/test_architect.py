"""AI architect tests with a scripted model: tool loop, operations, questions, conflicts, tools."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe

from pridict.agent_studio import assistant, gateway
from pridict.automation import api, architect
from pridict.automation import spec as specs
from pridict.automation.test_helpers import AutomationTestCase

MODEL = "_architect-test"


def call(name: str, **arguments) -> dict:
	return {"tool": name, "arguments": arguments}


class Script:
	"""Stands in for gateway.chat: each response is the next item, a call() or a final string."""

	def __init__(self, steps: list):
		self.steps = list(steps)
		self.seen: list[list[dict]] = []

	def __call__(self, config, messages, *, tools=None, **_):
		self.seen.append(json.loads(json.dumps(messages, default=str)))
		step = self.steps.pop(0)
		usage = gateway.Usage(300, 60, 360)
		if isinstance(step, Exception):
			raise step
		if isinstance(step, list):
			calls = [
				gateway.ToolCall(f"c{len(self.seen)}_{i}", s["tool"], s["arguments"])
				for i, s in enumerate(step)
			]
			return gateway.LLMResponse(None, calls, "tool_calls", usage, config, "scripted", 5)
		if isinstance(step, dict):
			tool_call = gateway.ToolCall(f"c{len(self.seen)}", step["tool"], step["arguments"])
			return gateway.LLMResponse(None, [tool_call], "tool_calls", usage, config, "scripted", 5)
		return gateway.LLMResponse(step, [], "stop", usage, config, "scripted", 5)

	def tool_results(self, index: int) -> list[dict]:
		return [json.loads(m["content"]) for m in self.seen[index] if m["role"] == "tool"]


S3_OPS = [
	{"op": "set_meta", "title": "Supplier welcome", "description": "Welcome new suppliers."},
	{
		"op": "add_node",
		"id": "has_email",
		"type": "logic.if",
		"label": "Has email?",
		"config": {"condition": "trigger.doc.email_id"},
		"after": "trigger",
	},
	{"op": "connect", "from": "has_email", "to": "END", "branch": "false"},
	{
		"op": "add_node",
		"id": "welcome",
		"type": "action.send_email",
		"label": "Welcome email",
		"config": {
			"to": "{{ trigger.doc.email_id }}",
			"subject": "Welcome {{ trigger.doc.supplier_name }}",
			"message": "Hello",
		},
		"after": "has_email",
		"branch": "true",
	},
	{"op": "connect", "from": "welcome", "to": "END"},
]


class TestArchitect(AutomationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("LLM Provider", "_Test Architect Provider"):
			frappe.get_doc(
				{
					"doctype": "LLM Provider",
					"provider_name": "_Test Architect Provider",
					"provider_type": "OpenAI-compatible",
					"endpoint": "http://llm.local/v1",
				}
			).insert()
		if not frappe.db.exists("LLM Model Config", MODEL):
			frappe.get_doc(
				{
					"doctype": "LLM Model Config",
					"config_name": MODEL,
					"provider": "_Test Architect Provider",
					"model_id": "mock",
					"status": "Active",
				}
			).insert()
		frappe.db.set_single_value("Automation Settings", "architect_model", MODEL)
		frappe.clear_document_cache("Automation Settings", "Automation Settings")

	def setUp(self):
		super().setUp()
		self.automation = api.create_automation(
			"Chat built", "trigger.document_event", {"doctype": "Supplier", "event": "after_insert"}
		)["name"]

	def say(self, text: str, script: Script, focus_node=None):
		with patch.object(gateway, "chat", script):
			architect.send_message(self.automation, text, focus_node)

	def chat(self) -> list[dict]:
		return architect.get_chat(self.automation)["messages"]

	def draft(self) -> dict:
		return specs.load(frappe.db.get_value("Automation", self.automation, "draft_spec"))

	def test_builds_from_a_prompt(self):
		script = Script(
			[
				call("get_doctype_fields", doctype="Supplier"),
				call("apply_changes", ops=S3_OPS, summary="Welcome email for new suppliers"),
				"Done: new suppliers with an email address get a welcome email.",
			]
		)
		self.say("Email new suppliers a welcome note", script)
		spec = self.draft()
		self.assertEqual([n["id"] for n in spec["nodes"]], ["has_email", "welcome"])
		self.assertFalse(specs.has_errors(specs.validate(spec)))
		self.assertEqual(frappe.db.get_value("Automation", self.automation, "title"), "Supplier welcome")
		history = api.get_history(self.automation)
		self.assertEqual(
			(history[0]["source"], history[0]["summary"]), ("ai", "Welcome email for new suppliers")
		)
		messages = self.chat()
		self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
		self.assertIn("welcome email", messages[-1]["content"])
		self.assertFalse(architect.get_chat(self.automation)["working"])
		# The model saw the rules, the catalog and the current draft; fields came from the tool.
		system = script.seen[0][0]["content"] + script.seen[0][1]["content"]
		self.assertIn("action.send_email", system)
		self.assertIn("CURRENT DRAFT", system)
		fields = script.tool_results(1)[0]["fields"]
		self.assertTrue(any(f.startswith("supplier_name (Data)") for f in fields))
		# Its apply_changes result carried the validation of the new draft.
		applied = script.tool_results(2)[-1]
		self.assertTrue(applied["ok"])
		self.assertIn("errors", applied)
		conversation = frappe.get_doc(
			"Assistant Conversation", frappe.db.get_value("Automation", self.automation, "conversation")
		)
		self.assertEqual(
			(conversation.purpose, conversation.automation), ("Automation Builder", self.automation)
		)
		self.assertEqual(conversation.total_tokens, 3 * 360)
		self.assertIn("apply_changes", [s.node_id for s in conversation.steps])

	def test_ask_user_ends_the_turn_and_the_answer_continues(self):
		self.say(
			"Email new suppliers",
			Script(
				[call("ask_user", question="Send from which account?", choices=["accounts@", "purchase@"])]
			),
		)
		messages = self.chat()
		self.assertEqual(messages[-1]["kind"], "question")
		self.assertEqual(messages[-1]["choices"], ["accounts@", "purchase@"])
		script = Script(["Thanks, noted."])
		self.say("purchase@", script)
		history = [m["content"] for m in script.seen[0] if m["role"] in ("user", "assistant")]
		self.assertEqual(history, ["Email new suppliers", "Send from which account?", "purchase@"])

	def test_errors_in_ops_are_reported_back_to_the_model(self):
		script = Script(
			[
				call("apply_changes", ops=[{"op": "remove_node", "id": "ghost"}], summary="x"),
				call(
					"apply_changes",
					ops=[
						{"op": "add_node", "id": "only", "type": "logic.if", "config": {}, "after": "trigger"}
					],
					summary="y",
				),
				"Added a check.",
			]
		)
		self.say("Add a check", script)
		first = script.tool_results(1)[-1]
		self.assertFalse(first["ok"])
		self.assertIn("ghost", first["error"])
		second = script.tool_results(2)[-1]
		self.assertTrue(second["ok"])
		self.assertIn("only: 'condition' is required.", second["errors"])

	def test_conflicting_canvas_edit_is_handed_back(self):
		def canvas_edit_then(apply):
			def wrapped(automation, base_revision, ops, **kwargs):
				# Someone moves a step on the canvas just before the architect applies.
				if not getattr(wrapped, "done", False):
					wrapped.done = True
					api.apply_ops(automation, base_revision, [{"op": "set_meta", "title": "Canvas rename"}])
				return apply(automation, base_revision, ops, **kwargs)

			return wrapped

		script = Script(
			[
				call("apply_changes", ops=[{"op": "set_meta", "description": "AI"}], summary="a"),
				call("apply_changes", ops=[{"op": "set_meta", "description": "AI"}], summary="a"),
				"Updated.",
			]
		)
		with patch.object(api, "apply_ops", canvas_edit_then(api.apply_ops)):
			self.say("Describe it", script)
		conflict = script.tool_results(1)[-1]
		self.assertFalse(conflict["ok"])
		self.assertEqual(conflict["draft"]["title"], "Canvas rename")
		self.assertTrue(script.tool_results(2)[-1]["ok"])
		self.assertEqual(self.draft()["description"], "AI")
		self.assertEqual(self.draft()["title"], "Canvas rename")

	def test_next_turn_sees_canvas_edits_and_focus(self):
		revision = frappe.db.get_value("Automation", self.automation, "draft_revision")
		api.apply_ops(
			self.automation,
			revision,
			[
				{
					"op": "add_node",
					"id": "note",
					"type": "action.add_comment",
					"label": "Canvas note",
					"config": {"comment": "hi"},
					"after": "trigger",
				}
			],
		)
		script = Script(["I see the note."])
		self.say("What does the note do?", script, focus_node="note")
		context = script.seen[0][1]["content"]
		self.assertIn("Canvas note", context)
		self.assertIn("asking about the step 'Canvas note'", context)

	def test_lookup_tools(self):
		turn = architect.Turn(self.automation, architect.conversation_for(self.automation))
		found, _ = turn.tool_search_doctypes("Supplier")
		self.assertIn("Supplier", [d["doctype"] for d in found["doctypes"]])
		fields, _ = turn.tool_get_doctype_fields("Request for Quotation")
		self.assertTrue(fields["submittable"])
		self.assertIn("Request for Quotation Item", fields["child_tables"])
		missing, _ = turn.tool_get_doctype_fields("No Such DocType")
		self.assertFalse(missing["ok"])
		people, _ = turn.tool_list_users_and_roles("Purchase")
		self.assertIn("Purchase Manager", people["roles"])
		accounts, _ = turn.tool_list_email_accounts()
		self.assertTrue(accounts["email_accounts"])
		good, _ = turn.tool_validate_expression("trigger.doc.email_id", "condition")
		self.assertTrue(good["ok"])
		bad, _ = turn.tool_validate_expression("{{ nodes.ghost.x }}", "template", at_node="trigger")
		self.assertFalse(bad["ok"])
		sample, _ = turn.tool_get_sample_document("Supplier")
		self.assertTrue(sample["document"] is None or "name" in sample["document"])

	def test_model_failures_end_with_a_friendly_message(self):
		self.say("Build something", Script([gateway.LLMError("boom")]))
		messages = self.chat()
		self.assertEqual(messages[-1]["kind"], "error")
		self.assertIn("can't reach the AI model", messages[-1]["content"])
		self.assertFalse(architect.get_chat(self.automation)["working"])

	def test_unknown_tools_and_bad_arguments_do_not_stop_the_turn(self):
		script = Script([call("drop_database"), call("get_doctype_fields", table="Supplier"), "Sorry."])
		self.say("hi", script)
		self.assertIn("Unknown tool", script.tool_results(1)[-1]["error"])
		self.assertIn("Bad arguments", script.tool_results(2)[-1]["error"])
		self.assertEqual(self.chat()[-1]["content"], "Sorry.")

	def test_builder_chats_stay_out_of_the_assistant(self):
		self.say("hello", Script(["Hi."]))
		conversation = frappe.db.get_value("Automation", self.automation, "conversation")
		self.assertNotIn(conversation, [c["name"] for c in assistant.get_conversations()])

	def test_needs_a_model_and_write_access(self):
		frappe.db.set_single_value("Automation Settings", "architect_model", None)
		frappe.clear_document_cache("Automation Settings", "Automation Settings")
		try:
			with self.assertRaises(frappe.ValidationError):
				architect.send_message(self.automation, "hi")
		finally:
			frappe.db.set_single_value("Automation Settings", "architect_model", MODEL)
			frappe.clear_document_cache("Automation Settings", "Automation Settings")
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				architect.send_message(self.automation, "hi")
		finally:
			frappe.set_user("Administrator")

	def test_plain_questions_count_as_questions(self):
		self.say("Email suppliers", Script(["Which role should get the assignment?"]))
		self.assertEqual(self.chat()[-1]["kind"], "question")
		self.say(
			"Purchase Manager",
			Script([call("apply_changes", ops=S3_OPS, summary="build"), "Built it. Want a comment too?"]),
		)
		# After changing the draft, a closing question is just part of the reply.
		self.assertEqual(self.chat()[-1]["kind"], "text")

	def test_deleting_an_automation_removes_its_chat(self):
		self.say("hello", Script(["Hi."]))
		conversation = frappe.db.get_value("Automation", self.automation, "conversation")
		frappe.delete_doc("Automation", self.automation)
		self.assertFalse(frappe.db.exists("Assistant Conversation", conversation))

	def test_empty_answer_is_retried_once(self):
		script = Script(["", "Here you go."])
		self.say("hi", script)
		self.assertEqual(len(script.seen), 2)
		self.assertIn("Your last answer was empty", script.seen[1][-1]["content"])
		self.assertEqual(self.chat()[-1]["content"], "Here you go.")
