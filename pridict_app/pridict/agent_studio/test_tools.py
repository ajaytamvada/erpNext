"""Agent tool tests against real ERPNext documents (rolled back after the class)."""

from __future__ import annotations

import frappe
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.stock.doctype.item.test_item import make_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from pridict.agent_studio import tools
from pridict.agent_studio.setup import ensure_agent_studio_setup

ITEM = "_Test Agent Alu Sheet"
WAREHOUSE = "_Test Warehouse - _TC"
NO_ACCESS_USER = "agent-no-access@example.com"


class TestAgentTools(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_agent_studio_setup()
		item = make_item(
			ITEM, {"item_name": "Agent Aluminium Sheet 2mm", "is_stock_item": 1, "lead_time_days": 10}
		)
		item.set("supplier_items", [{"supplier": "_Test Supplier"}, {"supplier": "_Test Supplier 1"}])
		item.save()
		make_stock_entry(item_code=ITEM, target=WAREHOUSE, qty=100, basic_rate=240)
		create_purchase_order(
			item_code=ITEM, warehouse=WAREHOUSE, qty=150, rate=250, supplier="_Test Supplier"
		)
		if not frappe.db.exists("User", NO_ACCESS_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": NO_ACCESS_USER,
					"first_name": "No Access",
					"send_welcome_email": 0,
				}
			).insert()

	def tearDown(self):
		frappe.set_user("Administrator")

	def run_ok(self, name, **arguments):
		outcome = tools.run_tool(name, arguments)
		self.assertTrue(outcome["ok"], outcome)
		return outcome["result"]

	def test_search_items(self):
		items = self.run_ok("search_items", query="Agent Aluminium")["items"]
		self.assertEqual(items[0]["item_code"], ITEM)

	def test_exact_item_code_ranks_first(self):
		# Many items contain "_Test Item"; the exact code must still be returned first.
		items = self.run_ok("search_items", query="_Test Item", limit=3)["items"]
		self.assertEqual(items[0]["item_code"], "_Test Item")

	def test_stock_balance(self):
		self.assertEqual(
			self.run_ok("get_stock_balance", item_code=ITEM, warehouse=WAREHOUSE)["actual_qty"], 100
		)

	def test_open_purchase_orders_respect_need_by_date(self):
		due = self.run_ok(
			"get_open_purchase_orders",
			item_code=ITEM,
			warehouse=WAREHOUSE,
			before_date=add_days(nowdate(), 5),
		)
		self.assertEqual([o["pending_qty"] for o in due["orders"]], [150])
		# The PO is scheduled for tomorrow, so it cannot cover a need dated today.
		too_late = self.run_ok(
			"get_open_purchase_orders", item_code=ITEM, warehouse=WAREHOUSE, before_date=nowdate()
		)
		self.assertEqual(too_late["orders"], [])

	def test_approved_suppliers_and_hold(self):
		frappe.db.set_value(
			"Supplier", "_Test Supplier 1", {"on_hold": 1, "hold_type": "All", "release_date": None}
		)
		suppliers = {
			s["supplier"]: s for s in self.run_ok("get_approved_suppliers", item_code=ITEM)["suppliers"]
		}
		self.assertEqual(set(suppliers), {"_Test Supplier", "_Test Supplier 1"})
		self.assertFalse(suppliers["_Test Supplier"]["on_hold"])
		self.assertTrue(suppliers["_Test Supplier 1"]["on_hold"])
		self.assertEqual(suppliers["_Test Supplier"]["lead_time_days"], 10)

	def test_price_history(self):
		history = self.run_ok("get_price_history", item_code=ITEM, days=30)
		self.assertAlmostEqual(history["avg_rate"], 250)
		self.assertEqual(history["by_supplier"][0]["supplier"], "_Test Supplier")

	def test_price_anomalies(self):
		high = self.run_ok("detect_price_anomalies", item_code=ITEM, proposed_rate=300)
		self.assertEqual(high["benchmark_rate"], 250)
		self.assertAlmostEqual(high["anomalies"][0]["variance_pct"], 20.0)
		self.assertEqual(
			self.run_ok("detect_price_anomalies", item_code=ITEM, proposed_rate=255)["anomalies"], []
		)

	def test_score_vendors(self):
		scores = {
			s["supplier"]: s
			for s in self.run_ok("score_vendors", suppliers=["_Test Supplier", "_Test Supplier 2"])["scores"]
		}
		self.assertIsNotNone(scores["_Test Supplier"]["score"])
		self.assertEqual(scores["_Test Supplier 2"]["tier"], "No history")

	def test_invalid_arguments_are_reported_not_raised(self):
		missing = tools.run_tool("get_stock_balance", {"item_code": ITEM})
		self.assertFalse(missing["ok"])
		self.assertIn("warehouse", missing["error"])
		extra = tools.run_tool("search_items", {"query": "x", "drop_table": True})
		self.assertIn("unknown field", extra["error"])
		too_many = tools.run_tool("search_items", {"query": "x", "limit": 500})
		self.assertIn("at most", too_many["error"])

	def test_blocked_disabled_and_write_tools_are_refused(self):
		self.assertIn("blocked", tools.run_tool("submit_purchase_order", {"purchase_order": "X"})["error"])
		self.assertIn("disabled", tools.run_tool("create_draft_purchase_order", {})["error"])
		refused = tools.run_tool(
			"create_draft_rfq",
			{
				"item_code": ITEM,
				"qty": 1,
				"schedule_date": nowdate(),
				"suppliers": ["_Test Supplier"],
				"approval_id": "x",
			},
		)
		self.assertIn("approved Agent Approval", refused["error"])

	def test_tool_specs_only_expose_enabled_read_tools(self):
		names = [
			s["name"] for s in tools.tool_specs(["search_items", "create_draft_rfq", "submit_purchase_order"])
		]
		self.assertEqual(names, ["search_items"])

	def test_tools_run_with_the_users_permissions(self):
		frappe.set_user(NO_ACCESS_USER)
		outcome = tools.run_tool(
			"get_open_purchase_orders",
			{"item_code": ITEM, "warehouse": WAREHOUSE, "before_date": add_days(nowdate(), 5)},
		)
		self.assertFalse(outcome["ok"])
		self.assertIn("permi", outcome["error"].lower())
		suppliers = tools.run_tool("get_approved_suppliers", {"item_code": ITEM})
		self.assertFalse(suppliers["ok"])
		self.assertIn("permi", suppliers["error"].lower())
