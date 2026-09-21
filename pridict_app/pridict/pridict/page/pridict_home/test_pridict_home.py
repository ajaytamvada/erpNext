import frappe
from erpnext.accounts.report.profit_and_loss_statement import profit_and_loss_statement
from erpnext.accounts.utils import get_fiscal_year
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

from pridict.pridict.page.pridict_home import pridict_home


RESTRICTED_USER = "test1@example.com"
PERMITTED_COMPANY = "_Test Company"
RESTRICTED_COMPANY = "_Test Company 1"


class TestPridictHome(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def set_restricted_user(self):
		user = frappe.get_doc("User", RESTRICTED_USER)
		user.add_roles("Accounts User", "Sales User")
		frappe.clear_cache(user=RESTRICTED_USER)
		frappe.set_user(RESTRICTED_USER)

	def test_dashboard_returns_only_permitted_companies(self):
		result = pridict_home.get_dashboard()
		self.assertTrue(result.get("companies"))
		self.assertIn(result["filters"]["company"], {company.name for company in result["companies"]})

	def test_guest_cannot_load_dashboard(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			pridict_home.get_dashboard()

	def test_restricted_user_only_sees_allowed_company(self):
		self.set_restricted_user()
		result = pridict_home.get_dashboard(company=PERMITTED_COMPANY)

		self.assertEqual([company.name for company in result["companies"]], [PERMITTED_COMPANY])
		self.assertEqual(result["filters"]["company"], PERMITTED_COMPANY)

	def test_restricted_user_cannot_request_another_company(self):
		self.set_restricted_user()

		with (
			patch.object(pridict_home, "_get_financials") as get_financials,
			patch.object(pridict_home, "_get_pipeline") as get_pipeline,
			patch.object(pridict_home, "_get_overdue_receivables") as get_overdue_receivables,
			patch.object(pridict_home, "_get_tasks") as get_tasks,
			patch.object(pridict_home, "_get_recent_activity") as get_recent_activity,
		):
			with self.assertRaises(frappe.PermissionError):
				pridict_home.get_dashboard(company=RESTRICTED_COMPANY)

		get_financials.assert_not_called()
		get_pipeline.assert_not_called()
		get_overdue_receivables.assert_not_called()
		get_tasks.assert_not_called()
		get_recent_activity.assert_not_called()

	def test_financial_metrics_match_profit_and_loss_report(self):
		result = pridict_home.get_dashboard(company=PERMITTED_COMPANY)
		filters = result["filters"]
		from_fiscal_year = get_fiscal_year(filters["from_date"], company=PERMITTED_COMPANY)[0]
		to_fiscal_year = get_fiscal_year(filters["to_date"], company=PERMITTED_COMPANY)[0]
		report_filters = frappe._dict(
			company=PERMITTED_COMPANY,
			filter_based_on="Date Range",
			period_start_date=filters["from_date"],
			period_end_date=filters["to_date"],
			from_fiscal_year=from_fiscal_year,
			to_fiscal_year=to_fiscal_year,
			periodicity="Monthly",
			accumulated_values=0,
			include_default_book_entries=1,
			presentation_currency=filters["currency"],
		)
		_columns, _data, _message, _chart, report_summary, _primitive_summary = (
			profit_and_loss_statement.execute(report_filters)
		)

		self.assertEqual(result["metrics"]["revenue"], report_summary[0].get("value"))
		self.assertEqual(result["metrics"]["expenses"], report_summary[2].get("value"))
