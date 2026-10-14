"""Unit tests for workflow graph validation (no database needed)."""

from __future__ import annotations

import copy
import unittest

from pridict.agent_studio import registry
from pridict.agent_studio.graph import validate_workflow

TOOL_ACCESS = {tool["tool_name"]: tool["access"] for tool in registry.TOOLS}


def _results(workflow, max_steps=8):
	return {r["check"]: r["result"] for r in validate_workflow(workflow, TOOL_ACCESS, max_steps)}


def _node(workflow, node_id):
	return next(n for n in workflow["nodes"] if n["id"] == node_id)


class TestWorkflowValidation(unittest.TestCase):
	def setUp(self):
		self.workflow = copy.deepcopy(registry.WORKFLOWS[registry.PROCUREMENT_WORKFLOW])

	def test_procurement_workflow_passes_every_check(self):
		results = validate_workflow(self.workflow, TOOL_ACCESS, 8)
		self.assertTrue(results)
		self.assertEqual({r["result"] for r in results}, {"PASS"}, results)

	def test_unknown_edge_target_fails(self):
		_node(self.workflow, "calc_shortage")["next"] = [["", "does_not_exist"]]
		self.assertEqual(_results(self.workflow)["Every edge points to an existing node"], "FAIL")

	def test_unreachable_node_fails(self):
		self.workflow["nodes"].append(
			{"id": "orphan", "label": "Orphan", "kind": "rule", "next": [["", "END"]]}
		)
		self.assertEqual(_results(self.workflow)["Every node is reachable from the entry point"], "FAIL")

	def test_dead_end_fails(self):
		_node(self.workflow, "verify_audit")["next"] = []
		self.assertEqual(_results(self.workflow)["Every path ends at END or a human pause"], "FAIL")

	def test_write_tool_before_approval_fails(self):
		# Skipping human review lets the draft RFQ be created without approval.
		_node(self.workflow, "prepare_recommendation")["next"] = [["", "create_draft"]]
		self.assertEqual(
			_results(self.workflow)["Write tools are only reachable after a human approval node"], "FAIL"
		)

	def test_unlabelled_branch_fails(self):
		_node(self.workflow, "shortage_router")["next"] = [
			["", "explain_no_purchase"],
			["yes", "find_suppliers"],
		]
		self.assertEqual(_results(self.workflow)["Router edges cover every possible outcome"], "FAIL")

	def test_loop_without_human_pause_warns_when_step_limit_set(self):
		# find_suppliers -> read_supply -> calc_shortage -> shortage_router -> find_suppliers, no person involved.
		_node(self.workflow, "find_suppliers")["next"].append(["retry", "read_supply"])
		check = "Loops pause for a person or are bounded by the step limit"
		self.assertEqual(_results(self.workflow, max_steps=8)[check], "WARN")
		self.assertEqual(_results(self.workflow, max_steps=None)[check], "FAIL")


class TestRegistry(unittest.TestCase):
	def test_tool_names_are_unique(self):
		names = [tool["tool_name"] for tool in registry.TOOLS]
		self.assertEqual(len(names), len(set(names)))

	def test_agent_tools_exist_and_exclude_submit(self):
		for tool in registry.PROCUREMENT_AGENT_DEFAULTS["tools"]:
			self.assertIn(tool, TOOL_ACCESS)
			self.assertNotEqual(TOOL_ACCESS[tool], "Write (submit)")

	def test_workflow_tools_exist(self):
		for workflow in registry.WORKFLOWS.values():
			for node in workflow["nodes"]:
				for tool in node.get("tools", []):
					self.assertIn(tool, TOOL_ACCESS, node["id"])

	def test_policy_names_and_rule_keys_are_unique(self):
		for field in ("policy_name", "rule_key"):
			values = [policy[field] for policy in registry.POLICIES]
			self.assertEqual(len(values), len(set(values)), field)
