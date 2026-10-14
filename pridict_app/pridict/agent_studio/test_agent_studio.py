"""Integration tests for Agent Studio DocTypes, seeding and read API."""

from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from pridict.agent_studio import api, registry
from pridict.agent_studio.setup import ensure_agent_studio_setup

PROVIDER = "_Test Agent Provider"


class TestAgentStudio(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_agent_studio_setup()
		if not frappe.db.exists("LLM Provider", PROVIDER):
			frappe.get_doc(
				{
					"doctype": "LLM Provider",
					"provider_name": PROVIDER,
					"provider_type": "OpenAI-compatible",
					"endpoint": "http://llm.test.internal:8000/v1",
					"api_key": "test-secret-key",
				}
			).insert()

	def make_config(self, name, fallback=None):
		if frappe.db.exists("LLM Model Config", name):
			frappe.delete_doc("LLM Model Config", name, force=True)
		return frappe.get_doc(
			{
				"doctype": "LLM Model Config",
				"config_name": name,
				"provider": PROVIDER,
				"model_id": "test-model",
				"fallback": fallback,
				"max_tokens": 100,
				"timeout_s": 10,
			}
		).insert()

	def make_agent(self, **overrides):
		values = {
			"doctype": "Agent Definition",
			"agent_name": "_Test Agent",
			"mode": "readonly",
			"approval_required": 1,
			"max_steps": 4,
			"max_runtime_s": 30,
			"token_budget": 1000,
			"tools": [{"tool": "search_items"}],
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_seed_is_idempotent(self):
		before = {dt: frappe.db.count(dt) for dt in ("Agent Tool", "Agent Policy", "Agent Definition")}
		ensure_agent_studio_setup()
		after = {dt: frappe.db.count(dt) for dt in before}
		self.assertEqual(before, after)
		self.assertEqual(after["Agent Tool"], len(registry.TOOLS))

	def test_sync_reapplies_block_on_submit_tools(self):
		frappe.db.set_value("Agent Tool", "submit_purchase_order", "status", "Enabled")
		ensure_agent_studio_setup()
		self.assertEqual(
			frappe.db.get_value("Agent Tool", "submit_purchase_order", "status"), "Blocked for agents"
		)

	def test_sync_keeps_admin_disabled_status(self):
		frappe.db.set_value("Agent Tool", "get_price_history", "status", "Disabled")
		ensure_agent_studio_setup()
		self.assertEqual(frappe.db.get_value("Agent Tool", "get_price_history", "status"), "Disabled")

	def test_fallback_loop_is_rejected(self):
		self.make_config("_test-cfg-a")
		self.make_config("_test-cfg-b", fallback="_test-cfg-a")
		config_a = frappe.get_doc("LLM Model Config", "_test-cfg-a")
		config_a.fallback = "_test-cfg-b"
		self.assertRaises(frappe.ValidationError, config_a.save)

	def test_azure_requires_api_version(self):
		doc = frappe.get_doc(
			{
				"doctype": "LLM Provider",
				"provider_name": "_Test Azure",
				"provider_type": "Azure OpenAI",
				"endpoint": "https://example.cognitiveservices.azure.com/",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_hosted_provider_rejects_plain_http(self):
		doc = frappe.get_doc(
			{
				"doctype": "LLM Provider",
				"provider_name": "_Test Plain",
				"provider_type": "OpenAI",
				"endpoint": "http://api.example.com/v1",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_readonly_agent_cannot_have_write_tool(self):
		agent = self.make_agent(tools=[{"tool": "create_draft_rfq"}])
		self.assertRaises(frappe.ValidationError, agent.insert)

	def test_submit_tool_can_never_be_granted(self):
		agent = self.make_agent(mode="recommend", tools=[{"tool": "submit_purchase_order"}])
		self.assertRaises(frappe.ValidationError, agent.insert)

	def test_writing_agent_must_keep_approval_gate(self):
		agent = self.make_agent(mode="recommend", approval_required=0)
		self.assertRaises(frappe.ValidationError, agent.insert)

	def test_api_never_returns_api_key(self):
		payload = json.dumps(api.get_models(), default=str)
		self.assertNotIn("test-secret-key", payload)
		provider = next(p for p in api.get_models()["providers"] if p.name == PROVIDER)
		self.assertTrue(provider.key_set)

	def test_workflow_api_validates_seeded_graph(self):
		data = api.get_workflow()
		self.assertEqual({r["result"] for r in data["validation"]}, {"PASS"})

	def test_policies_are_grouped_in_display_order(self):
		groups = [g["group"] for g in api.get_policies()["policies"]]
		self.assertEqual(groups[0], "Suppliers")
		self.assertEqual(groups[-1], "Prohibited for agents")
