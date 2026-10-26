"""Spec validation and expression tests (no database writes)."""

from __future__ import annotations

import copy

from frappe.tests.utils import FrappeTestCase

from pridict.automation import expressions
from pridict.automation import spec as specs
from pridict.automation.examples import load_example


def messages(spec, level="error"):
	return [issue["message"] for issue in specs.validate(spec) if issue["level"] == level]


class TestSpecValidation(FrappeTestCase):
	def setUp(self):
		self.spec = specs.load(load_example("s3_supplier_onboarding"))

	def test_example_is_valid(self):
		self.assertEqual(specs.validate(self.spec), [])

	def test_hash_is_stable_and_changes_with_content(self):
		again = specs.load(copy.deepcopy(self.spec))
		self.assertEqual(specs.spec_hash(self.spec), specs.spec_hash(again))
		again["nodes"][0]["label"] = "Changed"
		self.assertNotEqual(specs.spec_hash(self.spec), specs.spec_hash(again))

	def test_trigger_summary(self):
		self.assertEqual(
			specs.trigger_summary(self.spec),
			{
				"trigger_type": "trigger.document_event",
				"trigger_doctype": "Supplier",
				"trigger_event": "after_insert",
			},
		)

	def test_missing_trigger(self):
		del self.spec["trigger"]
		self.assertIn("The automation has no trigger.", messages(self.spec))

	def test_unknown_node_type_and_dangling_edge(self):
		self.spec["nodes"].append({"id": "x", "type": "action.nope", "config": {}})
		self.spec["edges"].append({"from": "assign_check", "to": "ghost"})
		errors = messages(self.spec)
		self.assertTrue(any("Unknown node type" in m for m in errors))
		self.assertTrue(any("unknown node 'ghost'" in m for m in errors))

	def test_branch_rules(self):
		self.spec["edges"] = [e for e in self.spec["edges"] if e.get("branch") != "false"]
		self.assertIn("The 'false' branch is not connected.", messages(self.spec))

	def test_single_exit_node_cannot_fork(self):
		self.spec["edges"].append({"from": "welcome_email", "to": "END"})
		self.assertTrue(any("more than one next step" in m for m in messages(self.spec)))

	def test_dead_end_and_unreachable(self):
		self.spec["nodes"].append({"id": "orphan", "type": "logic.if", "config": {"condition": "True"}})
		self.assertTrue(any("leads nowhere" in m for m in messages(self.spec)))
		self.assertTrue(any("No path from the trigger" in m for m in messages(self.spec, "warning")))

	def test_cycle_is_an_error(self):
		self.spec["edges"] = [e for e in self.spec["edges"] if e["from"] != "assign_check"]
		self.spec["edges"].append({"from": "assign_check", "to": "has_email"})
		self.assertTrue(any("cycle" in m for m in messages(self.spec)))

	def test_config_checks(self):
		self.spec["nodes"][0]["config"]["condition"] = "trigger.doc.email_id ==="
		self.spec["nodes"][1]["config"]["subject"] = "{{ trigger.doc.__class__ }}"
		self.spec["nodes"][2]["config"].pop("role")
		errors = messages(self.spec)
		self.assertTrue(any("Condition does not parse" in m for m in errors))
		self.assertTrue(any("underscore" in m for m in errors))
		self.assertIn("Choose users or a role to assign to.", errors)


class TestExpressions(FrappeTestCase):
	def scope(self):
		return expressions.scope_from_state(
			{
				"trigger": {"doc": {"supplier_name": "Acme", "email_id": "", "grand_total": 120}},
				"nodes": {"stock": {"rows": [{"qty": 1}, {"qty": -2}]}},
			}
		)

	def test_render(self):
		self.assertEqual(expressions.render("Hi {{ trigger.doc.supplier_name }}", self.scope()), "Hi Acme")
		self.assertEqual(expressions.render("plain text.txt", self.scope()), "plain text.txt")
		self.assertEqual(expressions.render(5, self.scope()), 5)
		self.assertEqual(
			expressions.render("{% if not nodes.missing %}none{% endif %}", self.scope()), "none"
		)

	def test_render_blocks_dunder(self):
		with self.assertRaises(expressions.ExpressionError):
			expressions.render("{{ trigger.__class__ }}", self.scope())

	def test_evaluate(self):
		scope = self.scope()
		self.assertTrue(expressions.evaluate("trigger.doc.grand_total > 100", scope))
		self.assertFalse(expressions.evaluate("trigger.doc.email_id", scope))
		self.assertTrue(expressions.evaluate("any(r.qty < 0 for r in nodes.stock.rows)", scope))

	def test_evaluate_is_restricted(self):
		with self.assertRaises(expressions.ExpressionError):
			expressions.evaluate("__import__('os').system('true')", self.scope())
		with self.assertRaises(expressions.ExpressionError):
			expressions.evaluate("open('/etc/passwd').read()", self.scope())
