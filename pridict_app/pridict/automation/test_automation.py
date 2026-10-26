"""Automation lifecycle and builder API tests: versions, Run As rule, operations, history."""

from __future__ import annotations

import json

import frappe

from pridict.automation import api, engine
from pridict.automation import spec as specs
from pridict.automation.examples import load_example
from pridict.automation.test_helpers import MANAGER, AutomationTestCase, install_example, make_supplier


class TestLifecycle(AutomationTestCase):
	def test_activation_freezes_a_version(self):
		automation = install_example("s3_supplier_onboarding")
		doc = frappe.get_doc("Automation", automation)
		self.assertEqual(doc.status, "Active")
		version = frappe.get_doc("Automation Version", doc.active_version)
		self.assertEqual(version.version, 1)
		self.assertEqual(version.spec_hash, specs.spec_hash(specs.load(doc.draft_spec)))
		# Activating an unchanged draft keeps the same version.
		self.assertEqual(doc.activate(), version.name)
		# A changed draft becomes version 2; version 1 is untouched.
		spec = specs.load(doc.draft_spec)
		spec["nodes"][2]["label"] = "Check documents"
		doc.draft_spec = json.dumps(spec)
		doc.save()
		second = doc.activate("relabel")
		self.assertNotEqual(second, version.name)
		self.assertEqual(frappe.db.get_value("Automation Version", second, "version"), 2)
		self.assertIn(
			"Assign onboarding check", frappe.db.get_value("Automation Version", version.name, "spec")
		)

	def test_errors_block_activation(self):
		spec = load_example("s3_supplier_onboarding")
		spec["title"] = "Broken"
		spec["nodes"][2]["config"]["role"] = "No Such Role"
		doc = frappe.get_doc(
			{"doctype": "Automation", "title": "Broken", "draft_spec": json.dumps(spec)}
		).insert()
		with self.assertRaises(frappe.ValidationError) as caught:
			doc.activate()
		self.assertIn("No Such Role", str(caught.exception))
		self.assertEqual(frappe.db.get_value("Automation", doc.name, "status"), "Draft")

	def test_status_changes_only_through_actions(self):
		automation = install_example("s3_supplier_onboarding")
		doc = frappe.get_doc("Automation", automation)
		doc.status = "Disabled"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		doc.reload()
		doc.pause()
		self.assertEqual(doc.status, "Paused")
		doc.resume()
		self.assertEqual(doc.status, "Active")

	def test_default_run_as_is_the_automation_user(self):
		doc = frappe.get_doc(
			{
				"doctype": "Automation",
				"title": "Default user",
				"draft_spec": json.dumps(load_example("s3_supplier_onboarding")),
			}
		).insert()
		self.assertEqual(doc.run_as, frappe.db.get_single_value("Automation Settings", "default_run_as"))

	def test_run_as_cannot_exceed_the_admins_roles(self):
		doc = frappe.get_doc(
			{
				"doctype": "Automation",
				"title": "Escalation",
				"draft_spec": json.dumps(load_example("s3_supplier_onboarding")),
			}
		).insert()
		frappe.get_doc("User", MANAGER).add_roles("Automation Manager")
		frappe.set_user(MANAGER)
		try:
			doc = frappe.get_doc("Automation", doc.name)
			doc.run_as = "Administrator"
			with self.assertRaises(frappe.PermissionError):
				doc.save()
		finally:
			frappe.set_user("Administrator")

	def test_live_validation_checks_run_as_permissions(self):
		spec = specs.load(load_example("s3_supplier_onboarding"))
		automation_user = frappe.db.get_single_value("Automation Settings", "default_run_as")
		issues = specs.validate(spec, live=True, run_as=automation_user)
		self.assertTrue(any("no read permission on Supplier" in i["message"] for i in issues))
		self.assertFalse(specs.has_errors(specs.validate(spec, live=True, run_as="Administrator")))


class TestBuilderApi(AutomationTestCase):
	def setUp(self):
		super().setUp()
		self.automation = install_example("s3_supplier_onboarding", activate=False)
		self.revision = frappe.db.get_value("Automation", self.automation, "draft_revision")

	def test_apply_ops_and_history(self):
		result = api.apply_ops(
			self.automation,
			self.revision,
			[
				{
					"op": "add_node",
					"type": "action.add_comment",
					"config": {"comment": "hi"},
					"after": "welcome_email",
				}
			],
			source="canvas",
		)
		self.assertTrue(result["ok"])
		self.assertEqual(result["revision"], self.revision + 1)
		self.assertIn("add_comment", specs.all_nodes(result["spec"]))
		history = api.get_history(self.automation)
		self.assertEqual(history[0]["source"], "canvas")
		self.assertEqual(history[0]["summary"], "added Add comment")

	def test_stale_revision_is_a_conflict(self):
		api.apply_ops(self.automation, self.revision, [{"op": "set_meta", "title": "First"}])
		result = api.apply_ops(self.automation, self.revision, [{"op": "set_meta", "title": "Second"}])
		self.assertEqual(result, {"ok": False, "conflict": True, "revision": self.revision + 1})
		self.assertEqual(frappe.db.get_value("Automation", self.automation, "title"), "First")

	def test_bad_ops_change_nothing(self):
		result = api.apply_ops(self.automation, self.revision, [{"op": "remove_node", "id": "ghost"}])
		self.assertFalse(result["ok"])
		self.assertIn("ghost", result["error"])
		self.assertEqual(frappe.db.get_value("Automation", self.automation, "draft_revision"), self.revision)

	def test_restore_an_earlier_revision(self):
		api.apply_ops(
			self.automation, self.revision, [{"op": "remove_node", "id": "welcome_email", "reconnect": True}]
		)
		first = api.get_history(self.automation)[0]
		api.apply_ops(self.automation, self.revision + 1, [{"op": "set_meta", "title": "Renamed"}])
		api.restore(self.automation, first["name"])
		doc = frappe.get_doc("Automation", self.automation)
		self.assertNotIn("welcome_email", specs.all_nodes(specs.load(doc.draft_spec)))
		self.assertEqual(api.get_history(self.automation)[0]["source"], "restore")

	def test_get_builder(self):
		data = api.get_builder(self.automation)
		self.assertEqual(data["automation"]["status"], "Draft")
		self.assertIn("logic.loop", data["catalog"])
		self.assertTrue(data["site"]["enabled"])
		api.activate(self.automation)
		self.assertTrue(api.get_builder(self.automation)["automation"]["draft_matches_active"])


class TestListAndImport(AutomationTestCase):
	def test_create_list_duplicate_export_import(self):
		created = api.create_automation(
			"Canvas draft", "trigger.document_event", {"doctype": "Supplier", "event": "after_insert"}
		)["name"]
		doc = frappe.get_doc("Automation", created)
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(specs.load(doc.draft_spec)["trigger"]["config"]["doctype"], "Supplier")
		self.assertIn(created, [row.name for row in api.list_automations()])

		copy = api.duplicate(created)["name"]
		self.assertEqual(frappe.db.get_value("Automation", copy, "title"), "Canvas draft (copy)")

		exported = api.export_spec(created)
		imported = api.import_spec(json.dumps(exported))["name"]
		self.assertEqual(
			specs.load(frappe.db.get_value("Automation", imported, "draft_spec"))["trigger"],
			exported["trigger"],
		)
		with self.assertRaises(frappe.ValidationError):
			api.import_spec(json.dumps({"hello": "world"}))

	def test_list_counts_recent_runs(self):
		# Create the supplier first: once active, the automation would also fire on its insert.
		supplier = make_supplier("_Test List Supplier")
		automation = install_example("s3_supplier_onboarding")

		def counts():
			row = next(r for r in api.list_automations() if r.name == automation)
			return row.runs_24h, row.failures_24h

		runs, failures = counts()
		engine.start_run(
			automation, {"event": "after_insert", "doctype": "Supplier", "name": supplier}, now=True
		)
		self.assertEqual(counts(), (runs + 1, failures))

	def test_references_follow_the_graph(self):
		automation = install_example("s2_overdue_invoice_reminders", activate=False)
		values = {r["value"] for r in api.get_references(automation, "notify_manager")}
		self.assertIn("nodes.each_invoice.item.customer", values)
		self.assertIn("nodes.customer.doc.account_manager", values)
		self.assertIn("nodes.overdue.rows", values)
		# remind is not on every path to notify_manager, so it is not offered.
		self.assertFalse(any(v.startswith("nodes.remind") for v in values))
		s3 = install_example("s3_supplier_onboarding", activate=False)
		self.assertIn("trigger.doc.supplier_name", {r["value"] for r in api.get_references(s3, "has_email")})

	def test_unchanged_ops_do_not_add_revisions(self):
		automation = install_example("s3_supplier_onboarding", activate=False)
		revision = frappe.db.get_value("Automation", automation, "draft_revision")
		position = specs.all_nodes(api.export_spec(automation))["has_email"]["position"]
		result = api.apply_ops(
			automation, revision, [{"op": "move_node", "id": "has_email", "position": position}]
		)
		self.assertTrue(result["ok"])
		self.assertEqual(result["revision"], revision)
		self.assertFalse(api.get_history(automation))
