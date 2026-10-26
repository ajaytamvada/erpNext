"""Spec validation, operations and expression tests (no database writes)."""

from __future__ import annotations

import copy

from frappe.tests.utils import FrappeTestCase

from pridict.automation import expressions
from pridict.automation import spec as specs
from pridict.automation.examples import EXAMPLES, load_example
from pridict.automation.test_helpers import manual_spec


def messages(spec, level="error"):
	return [issue["message"] for issue in specs.validate(spec) if issue["level"] == level]


class TestSpecValidation(FrappeTestCase):
	def setUp(self):
		self.spec = specs.load(load_example("s3_supplier_onboarding"))

	def test_examples_have_no_structural_errors(self):
		# The email template leaves the inbox for the admin to choose.
		left_open = {"s5_email_to_sales_order": ["'email_account' is required."]}
		for key in EXAMPLES:
			self.assertEqual(messages(specs.load(load_example(key))), left_open.get(key, []), key)

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
				"trigger_cron": None,
			},
		)
		s2 = specs.load(load_example("s2_overdue_invoice_reminders"))
		self.assertEqual(specs.trigger_summary(s2)["trigger_cron"], "0 9 * * *")

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

	def test_cycle_is_an_error_unless_through_a_loop(self):
		self.spec["edges"] = [e for e in self.spec["edges"] if e["from"] != "assign_check"]
		self.spec["edges"].append({"from": "assign_check", "to": "has_email"})
		self.assertTrue(any("cycle" in m for m in messages(self.spec)))
		s2 = specs.load(load_example("s2_overdue_invoice_reminders"))
		self.assertFalse(any("cycle" in m for m in messages(s2)))

	def test_config_checks(self):
		self.spec["nodes"][0]["config"]["condition"] = "trigger.doc.email_id ==="
		self.spec["nodes"][1]["config"]["subject"] = "{{ trigger.doc.__class__ }}"
		self.spec["nodes"][2]["config"].pop("role")
		errors = messages(self.spec)
		self.assertTrue(any("Condition does not parse" in m for m in errors))
		self.assertTrue(any("underscore" in m for m in errors))
		self.assertIn("Choose users or a role to assign to.", errors)

	def test_references(self):
		# welcome_email does not run on every path to assign_check: a warning, not an error.
		self.assertTrue(
			any("nodes.welcome_email may not have run" in m for m in messages(self.spec, "warning"))
		)
		self.spec["nodes"][1]["config"]["subject"] = "{{ nodes.ghost.x }} {{ nodes.welcome_email.y }}"
		errors = messages(self.spec)
		self.assertIn("nodes.ghost does not exist.", errors)
		self.assertIn("A step cannot use its own output.", errors)

	def test_switch_branches_come_from_cases(self):
		spec = manual_spec(
			[
				{
					"id": "route",
					"type": "logic.switch",
					"config": {
						"cases": [
							{"name": "big", "condition": "True"},
							{"name": "small", "condition": "False"},
						]
					},
				}
			],
			[
				{"from": "trigger", "to": "route"},
				{"from": "route", "to": "END", "branch": "big"},
				{"from": "route", "to": "END", "branch": "small"},
			],
		)
		self.assertIn("The 'default' branch is not connected.", messages(spec))
		spec["edges"].append({"from": "route", "to": "END", "branch": "default"})
		self.assertEqual(messages(spec), [])

	def test_stop_is_terminal(self):
		spec = manual_spec(
			[{"id": "halt", "type": "logic.stop", "config": {"status": "Failed", "message": "no"}}],
			[{"from": "trigger", "to": "halt"}],
		)
		self.assertEqual(messages(spec), [])
		spec["edges"].append({"from": "halt", "to": "END"})
		self.assertIn("This step ends the run, so nothing can follow it.", messages(spec))

	def test_settings_are_checked(self):
		self.spec["settings"] = {"on_error": "explode", "max_steps": 0}
		errors = messages(self.spec)
		self.assertTrue(any("max_steps" in m for m in errors))
		self.assertTrue(any("on_error" in m for m in errors))

	def test_schedule_checks(self):
		spec = load_example("s2_overdue_invoice_reminders")
		spec["trigger"]["config"] = {"cron": "* * * * *"}
		self.assertTrue(any("fixed minute" in m for m in messages(specs.load(spec))))
		spec["trigger"]["config"] = {"frequency": "weekly", "weekday": "Funday"}
		self.assertTrue(any("weekday" in m for m in messages(specs.load(spec))))


class TestSpecOperations(FrappeTestCase):
	def setUp(self):
		self.spec = specs.load(load_example("s3_supplier_onboarding"))

	def test_add_node_after_inserts_between(self):
		new = specs.apply_ops(
			self.spec,
			[
				{
					"op": "add_node",
					"type": "action.add_comment",
					"label": "Note",
					"config": {"comment": "Welcome sent"},
					"after": "welcome_email",
				}
			],
		)
		self.assertIn({"from": "welcome_email", "to": "add_comment"}, new["edges"])
		self.assertIn({"from": "add_comment", "to": "assign_check"}, new["edges"])
		self.assertNotIn({"from": "welcome_email", "to": "assign_check"}, new["edges"])
		self.assertEqual(specs.validate(new), specs.validate(self.spec))
		# The original spec is untouched.
		self.assertNotIn("add_comment", specs.all_nodes(self.spec))

	def test_add_node_after_a_branch(self):
		new = specs.apply_ops(
			self.spec,
			[
				{
					"op": "add_node",
					"id": "skip_note",
					"type": "action.add_comment",
					"config": {"comment": "No email"},
					"after": "has_email",
					"branch": "false",
				}
			],
		)
		self.assertIn({"from": "has_email", "to": "skip_note", "branch": "false"}, new["edges"])
		self.assertIn({"from": "skip_note", "to": "assign_check"}, new["edges"])

	def test_update_remove_connect(self):
		new = specs.apply_ops(
			self.spec,
			[
				{
					"op": "update_node",
					"id": "welcome_email",
					"label": "Welcome",
					"config_patch": {"cc": "a@b.example"},
				},
				{"op": "remove_node", "id": "welcome_email", "reconnect": True},
			],
		)
		self.assertNotIn("welcome_email", specs.all_nodes(new))
		self.assertIn({"from": "has_email", "to": "assign_check", "branch": "true"}, new["edges"])
		# assign_check still mentions the removed step.
		self.assertEqual(messages(new), ["nodes.welcome_email does not exist."])
		moved = specs.apply_ops(new, [{"op": "move_node", "id": "assign_check", "position": [10.4, 20.6]}])
		self.assertEqual(specs.all_nodes(moved)["assign_check"]["position"], [10, 21])
		reconnected = specs.apply_ops(
			new, [{"op": "connect", "from": "has_email", "to": "END", "branch": "true"}]
		)
		targets = [
			e["to"] for e in reconnected["edges"] if e["from"] == "has_email" and e.get("branch") == "true"
		]
		self.assertEqual(targets, ["END"])

	def test_merge_patch_removes_keys(self):
		new = specs.apply_ops(
			self.spec, [{"op": "update_node", "id": "assign_check", "config_patch": {"role": None}}]
		)
		self.assertNotIn("role", specs.all_nodes(new)["assign_check"]["config"])

	def test_bad_ops(self):
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "explode"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "add_node", "id": "has_email", "type": "logic.if"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "add_node", "id": "Bad Id", "type": "logic.if"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "add_node", "type": "trigger.manual"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "disconnect", "from": "x", "to": "y"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(self.spec, [{"op": "update_node", "id": "has_email", "config_patch": "oops"}])
		with self.assertRaises(specs.OpError):
			specs.apply_ops(
				self.spec, [{"op": "add_node", "type": "logic.if", "config": "x", "after": "has_email"}]
			)

	def test_set_trigger_and_meta(self):
		new = specs.apply_ops(
			self.spec,
			[
				{"op": "set_trigger", "type": "trigger.manual", "config": {"doctype": "Supplier"}},
				{"op": "set_meta", "title": "Renamed"},
				{"op": "set_settings", "settings_patch": {"max_steps": 10}},
			],
		)
		self.assertEqual(new["trigger"]["type"], "trigger.manual")
		self.assertEqual(new["trigger"]["id"], "trigger")
		self.assertEqual(new["title"], "Renamed")
		self.assertEqual(new["settings"]["max_steps"], 10)

	def test_describe_ops(self):
		self.assertEqual(
			specs.describe_ops([{"op": "add_node", "label": "Approve"}, {"op": "remove_node", "id": "x"}]),
			"added Approve; removed x",
		)
		self.assertEqual(
			specs.describe_ops([{"op": "move_node", "id": "a"}, {"op": "move_node", "id": "b"}]), "moved a, b"
		)


class TestExpressions(FrappeTestCase):
	def scope(self):
		return expressions.scope_from_state(
			{
				"trigger": {
					"doc": {
						"supplier_name": "Acme",
						"email_id": "",
						"grand_total": 120,
						"items": [{"item_code": "A", "qty": 2}],
					}
				},
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

	def test_resolve_keeps_types(self):
		scope = self.scope()
		self.assertEqual(expressions.resolve("{{ nodes.stock.rows | length }}", scope), 2)
		self.assertEqual(
			expressions.resolve("{{ trigger.doc['items'] | map(attribute='item_code') | list }}", scope),
			["A"],
		)
		self.assertEqual(expressions.resolve("Total {{ trigger.doc.grand_total }}", scope), "Total 120")
		self.assertIsNone(expressions.resolve("{{ nodes.missing }}", scope))

	def test_each_builds_rows(self):
		rows = expressions.resolve_all(
			{
				"$each": "{{ trigger.doc['items'] }}",
				"item_code": "{{ row.item_code }}",
				"qty": "{{ row.qty * 2 }}",
			},
			self.scope(),
		)
		self.assertEqual(rows, [{"item_code": "A", "qty": 4}])

	def test_render_blocks_dunder(self):
		with self.assertRaises(expressions.ExpressionError):
			expressions.render("{{ trigger.__class__ }}", self.scope())
		with self.assertRaises(expressions.ExpressionError):
			expressions.resolve("{{ trigger.__class__ }}", self.scope())

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

	def test_references_and_cap(self):
		self.assertEqual(expressions.references({"a": ["{{ nodes.x.y }}", "nodes.z"]}), {"x", "z"})
		self.assertEqual(len(expressions.cap(list(range(900)))), expressions.MAX_LIST_ITEMS)


class TestTriggerLabels(FrappeTestCase):
	def test_changing_trigger_type_resets_the_label(self):
		spec = manual_spec([], [{"from": "trigger", "to": "END"}])
		spec["trigger"]["label"] = "Manual"
		new = specs.apply_ops(
			spec, [{"op": "set_trigger", "type": "trigger.schedule", "config": {"frequency": "daily"}}]
		)
		self.assertEqual(new["trigger"]["label"], "Schedule")
		same = specs.apply_ops(spec, [{"op": "set_trigger", "type": "trigger.manual", "config": {}}])
		self.assertEqual(same["trigger"]["label"], "Manual")
