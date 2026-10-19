"""Procurement Assistant conversations: tool-calling turns, sourcing hand-off and chat drafts."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.stock.doctype.item.test_item import make_item
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from pridict.agent_studio import assistant, gateway, registry, runtime, tools
from pridict.agent_studio import conversation as chat
from pridict.agent_studio.evals import ScriptedLLM
from pridict.agent_studio.setup import ensure_agent_studio_setup

WAREHOUSE = "_Test Warehouse - _TC"
ITEM = "_Test Conversation Bolt"


def call(name: str, **arguments) -> dict:
	return {"tool": name, "arguments": arguments}


class ChatScript:
	"""Stands in for gateway.chat. Conversation turns (sent with tools) are answered from
	`turns` in order: a dict from call() makes a tool call, a string is the final reply.
	Everything else (the sourcing workflow's structured prompts) goes to a ScriptedLLM."""

	def __init__(self, turns: list, requirements: list[dict] | None = None):
		self.turns = list(turns)
		self.sourcing = ScriptedLLM(requirements or [{}])
		self.seen: list[list[dict]] = []

	def __call__(self, config, messages, *, tools=None, response_schema=None, max_tokens=None, **_):
		if not tools:
			return self.sourcing(config, messages, response_schema=response_schema, max_tokens=max_tokens)
		self.seen.append(messages)
		step = self.turns.pop(0)
		usage = gateway.Usage(200, 40, 240)
		if isinstance(step, dict):
			tool_call = gateway.ToolCall(
				id=f"call_{len(self.seen)}", name=step["tool"], arguments=step["arguments"]
			)
			return gateway.LLMResponse(None, [tool_call], "tool_calls", usage, config, "scripted", 5)
		return gateway.LLMResponse(step, [], "stop", usage, config, "scripted", 5)


def requirement(qty=20) -> dict:
	return {
		"item_query": ITEM,
		"qty": qty,
		"uom": "",
		"warehouse": WAREHOUSE,
		"need_by": add_days(nowdate(), 10),
		"company": "",
	}


class TestAssistantConversation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_agent_studio_setup()
		if not frappe.db.exists("LLM Provider", "_Test Chat Provider"):
			frappe.get_doc(
				{
					"doctype": "LLM Provider",
					"provider_name": "_Test Chat Provider",
					"provider_type": "OpenAI-compatible",
					"endpoint": "http://llm.local/v1",
				}
			).insert()
		if not frappe.db.exists("LLM Model Config", "_chat-test"):
			frappe.get_doc(
				{
					"doctype": "LLM Model Config",
					"config_name": "_chat-test",
					"provider": "_Test Chat Provider",
					"model_id": "mock",
					"status": "Active",
				}
			).insert()
		for agent in (registry.ASSISTANT_AGENT, registry.PROCUREMENT_AGENT):
			frappe.db.set_value("Agent Definition", agent, {"model_config": "_chat-test", "max_steps": 8})
		item = make_item(ITEM, {"item_name": "Conversation Bolt M8", "is_stock_item": 1})
		item.set("supplier_items", [{"supplier": "_Test Supplier"}])
		item.save()
		cls.po = create_purchase_order(
			item_code=ITEM, warehouse=WAREHOUSE, qty=5, rate=10, supplier="_Test Supplier"
		)

	def setUp(self):
		# Jobs would only start after a commit; tests run each step inline instead.
		for target in (
			"pridict.agent_studio.conversation.enqueue_respond",
			"pridict.agent_studio.runtime._enqueue",
		):
			patcher = patch(target, lambda *args, **kwargs: None)
			patcher.start()
			self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.set_user("Administrator")
		for agent in (registry.ASSISTANT_AGENT, registry.PROCUREMENT_AGENT):
			frappe.clear_document_cache("Agent Definition", agent)

	def say(self, script: ChatScript, text: str, conversation: str | None = None) -> str:
		with patch("pridict.agent_studio.gateway.chat", script):
			name = assistant.send_message(text, conversation)["conversation"]
			chat.respond(name)
		return name

	def run_sourcing(self, script: ChatScript, conversation: str, resume=None):
		run = frappe.db.get_value(chat.DOCTYPE, conversation, "active_run")
		with patch("pridict.agent_studio.gateway.chat", script):
			runtime.execute(run, resume)
		return frappe.get_doc("Agent Run", run)

	def messages(self, conversation: str) -> list[dict]:
		return assistant.get_conversation(conversation)["messages"]

	# --- questions ----------------------------------------------------------------

	def test_answers_a_question_from_a_read_tool(self):
		script = ChatScript(
			[
				call("list_documents", doctype="Purchase Order", item_code=ITEM),
				"You have one open purchase order for the bolts.",
			]
		)
		name = self.say(script, "Show purchase orders for the bolts")
		last = self.messages(name)[-1]
		self.assertEqual(
			(last["role"], last["content"]), ("assistant", "You have one open purchase order for the bolts.")
		)
		# The tool result went back to the model, with a link to the document.
		tool_message = next(m for m in script.seen[1] if m["role"] == "tool")
		result = json.loads(tool_message["content"])
		self.assertEqual([d["name"] for d in result["documents"]], [self.po.name])
		self.assertTrue(result["documents"][0]["url"].startswith("/app/purchase-order/"))
		doc = frappe.get_doc(chat.DOCTYPE, name)
		self.assertEqual([s.node_id for s in doc.steps], ["assistant", "list_documents", "assistant"])
		self.assertEqual((doc.llm_calls, doc.total_tokens, doc.working), (2, 480, 0))

	def test_general_question_needs_no_tool(self):
		name = self.say(ChatScript(["An RFQ asks suppliers for prices."]), "What is an RFQ?")
		self.assertEqual(self.messages(name)[-1]["content"], "An RFQ asks suppliers for prices.")

	def test_follow_up_sees_the_earlier_conversation(self):
		script = ChatScript(["First answer.", "Second answer."])
		name = self.say(script, "First question")
		self.say(script, "And a follow-up?", name)
		history = [(m["role"], m["content"]) for m in script.seen[1] if m["role"] != "system"]
		self.assertEqual(
			history,
			[("user", "First question"), ("assistant", "First answer."), ("user", "And a follow-up?")],
		)

	def test_tools_not_bound_to_the_assistant_are_refused(self):
		script = ChatScript([call("create_draft_rfq", item_code=ITEM), "Sorry."])
		self.say(script, "Make an RFQ")
		tool_message = next(m for m in script.seen[1] if m["role"] == "tool")
		self.assertIn("not available", tool_message["content"])

	def test_step_limit_ends_the_turn_politely(self):
		frappe.db.set_value("Agent Definition", registry.ASSISTANT_AGENT, "max_steps", 1)
		self.addCleanup(frappe.db.set_value, "Agent Definition", registry.ASSISTANT_AGENT, "max_steps", 8)
		name = self.say(ChatScript([call("list_items", query="bolt"), "never reached"]), "List bolts")
		last = self.messages(name)[-1]
		self.assertEqual(last["kind"], "error")
		self.assertIn("more steps", last["content"])
		self.assertFalse(frappe.db.get_value(chat.DOCTYPE, name, "working"))

	# --- sourcing hand-off ------------------------------------------------------------

	def test_purchase_request_starts_sourcing_in_the_same_conversation(self):
		script = ChatScript([call("start_sourcing", request="20 bolts for Stores")], [requirement()])
		name = self.say(script, "I need 20 bolts in 10 days")
		run_name = frappe.db.get_value(chat.DOCTYPE, name, "active_run")
		self.assertEqual(frappe.db.get_value("Agent Run", run_name, "conversation"), name)
		self.assertIn("On it", self.messages(name)[-1]["content"])
		self.assertTrue(assistant.get_conversation(name)["working"])

		run = self.run_sourcing(script, name)
		self.assertEqual(run.status, "Awaiting approval", run.error)
		messages = self.messages(name)
		# The user's request is not repeated by the run; the run's approval card follows the ack.
		self.assertEqual([m["role"] for m in messages], ["user", "assistant", "assistant"])
		self.assertEqual(messages[-1]["kind"], "approval")
		self.assertEqual(assistant.get_conversation(name)["state"], "approval")

	def test_side_question_while_sourcing_waits_then_quick_reply_answers_it(self):
		script = ChatScript(
			[
				call("start_sourcing", request="bolts"),
				"We have 0 in Stores.",
			],
			[{**requirement(), "warehouse": "", "company": "_Test Company"}],
		)
		name = self.say(script, "I need 20 bolts")
		run = self.run_sourcing(script, name)
		self.assertEqual(run.status, "Waiting for buyer", run.error)
		choices = self.messages(name)[-1]["choices"]
		self.assertTrue(choices)

		# A different question is answered; the run keeps waiting.
		self.say(script, "How many do we have?", name)
		self.assertEqual(frappe.db.get_value("Agent Run", run.name, "status"), "Waiting for buyer")
		self.assertEqual(self.messages(name)[-1]["content"], "We have 0 in Stores.")
		# The question it is still waiting on stays reachable, pinned with its quick replies.
		self.assertEqual(assistant.get_conversation(name)["pinned_question"]["choices"], choices)
		context = script.seen[-1][1]["content"]
		self.assertIn("waiting for the user's answer", context)

		# Clicking one of the run's quick replies goes straight to the run, without the model.
		calls = len(script.seen)
		self.say(script, choices[0], name)
		self.assertEqual(len(script.seen), calls)
		self.assertEqual(frappe.db.get_value("Agent Run", run.name, "status"), "Queued")

	def test_free_text_answer_is_passed_to_sourcing_by_the_model(self):
		script = ChatScript(
			[call("start_sourcing", request="bolts"), call("answer_sourcing", answer=WAREHOUSE)],
			[{**requirement(), "warehouse": ""}],
		)
		name = self.say(script, "I need 20 bolts")
		run = self.run_sourcing(script, name)
		self.say(script, "Put them in the test warehouse", name)
		self.assertEqual(frappe.db.get_value("Agent Run", run.name, "status"), "Queued")
		# answer_sourcing ends the turn: the run will reply, so the assistant adds nothing.
		self.assertEqual(self.messages(name)[-1]["role"], "user")

	def test_only_one_open_sourcing_request_per_conversation(self):
		script = ChatScript(
			[
				call("start_sourcing", request="bolts"),
				call("start_sourcing", request="more bolts"),
				"Finish the first one first.",
			],
			[requirement()],
		)
		name = self.say(script, "I need 20 bolts")
		self.run_sourcing(script, name)
		self.say(script, "Also 5 more", name)
		tool_message = next(m for m in script.seen[-1] if m["role"] == "tool")
		self.assertIn("still open", tool_message["content"])
		self.assertEqual(frappe.db.count("Agent Run", {"conversation": name}), 1)

	# --- drafts confirmed in chat ------------------------------------------------------

	def test_material_request_is_created_only_after_confirmation(self):
		due = add_days(nowdate(), 7)
		script = ChatScript(
			[
				call(
					"propose_material_request",
					items=[{"item_code": ITEM, "qty": 4}],
					warehouse=WAREHOUSE,
					schedule_date=due,
				)
			]
		)
		name = self.say(script, "Raise a material request for 4 bolts")
		card = self.messages(name)[-1]
		self.assertEqual(card["choices"], [chat.create_label(), chat.discard_label()])
		self.assertIn("4 Nos", json.dumps(card["card"]))
		before = frappe.db.count("Material Request")

		calls = len(script.seen)
		self.say(script, chat.create_label(), name)
		self.assertEqual(len(script.seen), calls)  # the button needs no model call
		self.assertEqual(frappe.db.count("Material Request"), before + 1)
		result = self.messages(name)[-1]
		mr = frappe.get_doc("Material Request", result["card"]["link"]["name"])
		self.assertEqual((mr.docstatus, mr.material_request_type, mr.items[0].qty), (0, "Purchase", 4))
		self.assertFalse(frappe.db.get_value(chat.DOCTYPE, name, "pending_action_json"))

	def test_discarding_the_draft_creates_nothing(self):
		due = add_days(nowdate(), 7)
		script = ChatScript(
			[
				call(
					"propose_material_request",
					items=[{"item_code": ITEM, "qty": 4}],
					warehouse=WAREHOUSE,
					schedule_date=due,
				)
			]
		)
		name = self.say(script, "Raise a material request")
		before = frappe.db.count("Material Request")
		self.say(script, chat.discard_label(), name)
		self.assertEqual(frappe.db.count("Material Request"), before)
		self.assertIn("discarded", self.messages(name)[-1]["content"])

	def test_invalid_draft_goes_back_to_the_model(self):
		script = ChatScript(
			[
				call(
					"propose_material_request",
					items=[{"item_code": "NO-SUCH-ITEM", "qty": 1}],
					warehouse=WAREHOUSE,
					schedule_date=nowdate(),
				),
				"I couldn't find that item.",
			]
		)
		name = self.say(script, "Raise a material request for widgets")
		tool_message = next(m for m in script.seen[1] if m["role"] == "tool")
		self.assertIn("does not exist", tool_message["content"])
		self.assertFalse(frappe.db.get_value(chat.DOCTYPE, name, "pending_action_json"))

	def test_draft_tool_refuses_without_confirmation(self):
		outcome = tools.run_tool(
			"create_draft_material_request",
			{"items": [{"item_code": ITEM, "qty": 1}], "warehouse": WAREHOUSE, "schedule_date": nowdate()},
		)
		self.assertFalse(outcome["ok"])
		self.assertIn("confirmation", outcome["error"])

	# --- read tools and access -------------------------------------------------------------

	def test_read_tools_return_permitted_data(self):
		summary = {}
		for group in ("supplier", "item", "month"):
			summary[group] = tools.run_tool("purchase_summary", {"group_by": group})
			self.assertTrue(summary[group]["ok"], summary[group].get("error"))
		self.assertTrue(any(r["label"] == ITEM for r in summary["item"]["result"]["rows"]))
		detail = tools.run_tool("get_document", {"doctype": "Purchase Order", "name": self.po.name})
		self.assertEqual(detail["result"]["items"][0]["item_code"], ITEM)
		stock = tools.run_tool("get_stock_levels", {"item_code": ITEM})
		self.assertTrue(stock["ok"], stock.get("error"))
		found = tools.run_tool("list_items", {"query": "Conversation Bolt"})
		self.assertEqual([i["name"] for i in found["result"]["items"]], [ITEM])
		overdue = tools.run_tool("list_documents", {"doctype": "Material Request", "overdue": True})
		self.assertFalse(overdue["ok"])

	def test_conversations_are_private(self):
		name = self.say(ChatScript(["Hello."]), "Hi")
		self.assertIn(name, [c["name"] for c in assistant.get_conversations()])
		frappe.set_user("test1@example.com")
		with self.assertRaises(frappe.PermissionError):
			assistant.get_conversation(name)
		self.assertNotIn(name, [c["name"] for c in assistant.get_conversations()])

	def test_cannot_send_while_working(self):
		name = self.say(ChatScript(["Hello."]), "Hi")
		frappe.db.set_value(chat.DOCTYPE, name, "working", 1)
		with self.assertRaises(frappe.ValidationError):
			assistant.send_message("Another", name)
