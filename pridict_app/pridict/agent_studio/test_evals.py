"""The offline evaluation suite must pass, and must leave no data behind."""

from __future__ import annotations

import unittest

import frappe

from pridict.agent_studio import evals, registry
from pridict.agent_studio.setup import ensure_agent_studio_setup


class TestEvaluationSuite(unittest.TestCase):
	# run_scenario() rolls back its own transaction, so this is a plain TestCase.

	def setUp(self):
		frappe.set_user("Administrator")
		ensure_agent_studio_setup()

	def test_offline_suite_passes_and_cleans_up(self):
		items_before = frappe.db.count("Item")
		runs_before = frappe.db.count("Agent Run")
		for index, scenario in enumerate(evals.SCENARIOS, start=1):
			with self.subTest(scenario.key):
				result = evals.run_scenario(registry.PROCUREMENT_AGENT, scenario, index, live=False)
				self.assertEqual(
					result["result"],
					"PASS",
					f"{scenario.key}: {result.get('note')} | steps {result.get('steps')}",
				)
		self.assertEqual(frappe.db.count("Item"), items_before)
		self.assertEqual(frappe.db.count("Agent Run"), runs_before)
		self.assertFalse(frappe.db.exists("Supplier", "Agent Eval Supplier A"))

	def test_failed_expectation_is_reported(self):
		scenario = evals.Scenario(
			"broken", "Broken", "Never matches", stock=600, expect={"status": "Awaiting approval"}
		)
		result = evals.run_scenario(registry.PROCUREMENT_AGENT, scenario, 99, live=False)
		self.assertEqual(result["result"], "FAIL")
		self.assertIn("status was Completed", result["note"])
