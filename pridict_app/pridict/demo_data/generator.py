"""Seed a site with a year of coherent manufacturing and procurement history.

Usage (fresh site, setup wizard not yet run):

	bench --site <site> execute pridict.demo_data.generator.seed --kwargs '{"scale": "medium"}'

The generator simulates the business day by day: customers order finished goods,
production consumes raw material against BOMs, reorder levels raise Material Requests,
buyers source through RFQs or direct POs, and suppliers deliver, invoice and get paid
according to their reliability profile. Because every document is posted in date order,
stock and accounts stay consistent and no reposting is needed.

A few procurement exceptions are planted on purpose so the Pridict analytics have
something to find: price spikes, maverick (direct) purchases, split POs, same-day
delivery dates, POs without a cost center, late and rejected deliveries, and unpaid
invoices.
"""

import heapq
import traceback
import random
import re
from collections import defaultdict
from datetime import date, timedelta

import frappe
from frappe.utils import add_months, cint, flt, getdate, today

from pridict.demo_data import catalog as C

SCALES = {
	"small": {"months": 3, "demand": 0.5},
	"medium": {"months": 12, "demand": 1.0},
	"large": {"months": 24, "demand": 1.6},
}
WHOLE_UOMS = {"Nos", "Unit", "Pair"}

# Event priorities within a day: stock arrives before it is consumed, and
# planning runs after the day's movements.
P_RECEIPT, P_PRODUCE, P_DELIVER, P_INVOICE, P_PAY, P_ORDER, P_PLAN = range(7)


def seed(scale="medium", user_password=None, rng_seed=2026):
	"""Create the demo company, masters and transaction history on the current site."""
	if scale not in SCALES:
		frappe.throw(f"scale must be one of {', '.join(SCALES)}")
	if frappe.db.exists("Company", C.COMPANY["company_name"]) and frappe.db.exists(
		"Purchase Order", {"company": C.COMPANY["company_name"]}
	):
		frappe.throw("Demo data already exists on this site. Seed a fresh site instead.")
	frappe.flags.mute_emails = True
	seeder = Seeder(SCALES[scale], user_password, rng_seed)
	seeder.setup_company()
	seeder.create_masters()
	seeder.run_history()
	frappe.db.commit()
	seeder.report()


class Seeder:
	def __init__(self, scale, user_password, rng_seed):
		self.scale = scale
		self.password = user_password
		self.rng = random.Random(rng_seed)
		self.today = getdate(today())
		start = getdate(add_months(self.today, -scale["months"]))
		self.start = start - timedelta(days=start.weekday())
		self.company = C.COMPANY["company_name"]
		self.abbr = C.COMPANY["abbr"]
		self.events = []
		self.seq = 0
		self.minute = defaultdict(int)
		self.counts = defaultdict(int)
		self.errors = []
		self.items = {i["code"]: i for i in C.ITEMS}
		self.fg = {code: {"name": name, "rate": rate, "bom": bom} for code, name, rate, bom in C.FINISHED_GOODS}
		self.suppliers = {s[0]: {"group": s[1], "state": s[2], "supplies": s[3], **s[4]} for s in C.SUPPLIERS}
		self.customers = {c[0]: {"group": c[1], "territory": c[2], "state": c[3], "terms": c[4], "late": c[5]} for c in C.CUSTOMERS}
		self.users = {u[2]: f"{u[2]}@{C.COMPANY['domain']}" for u in C.USERS}
		self.open_sos = []
		self.bill_no = 0
		self.savepoints = 0
		self.actor = "Administrator"

	# ------------------------------------------------------------------ helpers

	def wh(self, name):
		return f"{name} - {self.abbr}"

	def cc(self, name):
		return f"{name} - {self.abbr}"

	def qty(self, item_code, value):
		uom = self.items[item_code]["uom"] if item_code in self.items else "Nos"
		if uom in WHOLE_UOMS:
			return max(1, int(round(value)))
		return max(0.5, round(value, 1) if value < 50 else round(value))

	def stamp(self, d):
		"""Unique, increasing posting time per day so same-day entries keep their order."""
		self.minute[d] += 1
		m = self.minute[d]
		return f"{9 + m // 60 % 12:02d}:{m % 60:02d}:00"

	def schedule(self, d, priority, fn, *args, **kwargs):
		if d > self.today:
			return
		self.seq += 1
		heapq.heappush(self.events, (d, priority, self.seq, fn, args, kwargs))

	def as_user(self, key):
		# Documents are created as Administrator and attributed to the business user, so
		# role restrictions on helper lookups (addresses, price lists) don't block the seed.
		self.actor = self.users.get(key, "Administrator") if self.password else "Administrator"

	def finish(self, doc, d, posting_time=None):
		"""Submit, then backdate creation so list views and analytics see the business date."""
		doc.flags.ignore_permissions = True
		# _submit skips queue_action, which defers large documents to a background worker.
		doc._submit()
		ts = f"{d} {posting_time or '10:00:00'}"
		owner = doc.flags.demo_owner or "Administrator"
		frappe.db.sql(f"update `tab{doc.doctype}` set creation=%s, modified=%s, owner=%s, modified_by=%s where name=%s",
			(ts, ts, owner, owner, doc.name))
		self.counts[doc.doctype] += 1
		return doc

	def insert(self, doc):
		# Frappe resets owner to the session user on insert; finish() writes this back.
		doc.flags.demo_owner = self.actor
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc

	def run_safely(self, label, fn, *args, **kwargs):
		self.savepoints += 1
		savepoint = f"demo_event_{self.savepoints}"
		frappe.db.savepoint(savepoint)
		try:
			return fn(*args, **kwargs)
		except Exception as exc:
			frappe.db.rollback(save_point=savepoint)
			messages = [frappe.parse_json(m).get("message", m) if isinstance(m, str) else m.get("message")
				for m in (frappe.local.message_log or [])]
			frappe.local.message_log = []
			frame = traceback.extract_tb(exc.__traceback__)[-1]
			detail = str(exc) or "; ".join(str(m) for m in messages if m)
			self.errors.append(f"{label}: {type(exc).__name__}: {detail[:200]} @{frame.name}:{frame.lineno}")
			return None
		finally:
			self.actor = "Administrator"

	def bins(self, warehouse):
		rows = frappe.db.sql(
			"select item_code, actual_qty, projected_qty from tabBin where warehouse=%s", warehouse, as_dict=True
		)
		return {r.item_code: r for r in rows}

	def taxes(self, doctype, state):
		kind = "In-State" if state == C.COMPANY["state"] else "Inter-State"
		template = f"GST 18% {kind} - {self.abbr}"
		from erpnext.controllers.accounts_controller import get_taxes_and_charges

		return template, get_taxes_and_charges(doctype, template)

	# ------------------------------------------------------------------ company

	def setup_company(self):
		if not frappe.db.exists("Company", self.company):
			if frappe.is_setup_complete():
				# Existing site: add the demo company next to whatever is already there.
				self.insert(frappe.get_doc({
					"doctype": "Company", "company_name": self.company, "abbr": self.abbr,
					"country": C.COMPANY["country"], "default_currency": C.COMPANY["currency"],
					"create_chart_of_accounts_based_on": "Standard Template", "chart_of_accounts": "Standard",
				}))
			else:
				from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

				fy_start = date(self.today.year if self.today.month >= 4 else self.today.year - 1, 4, 1)
				setup_complete({
					"currency": C.COMPANY["currency"],
					"full_name": "Administrator",
					"company_name": self.company,
					"company_abbr": self.abbr,
					"timezone": C.COMPANY["timezone"],
					"country": C.COMPANY["country"],
					"industry": "Manufacturing",
					"fy_start_date": str(fy_start),
					"fy_end_date": str(date(fy_start.year + 1, 3, 31)),
					"language": "English",
					"company_tagline": "Pumps, gearboxes and hydraulic systems",
					"chart_of_accounts": "Standard",
				})
			frappe.db.commit()
		frappe.set_user("Administrator")
		frappe.local.lang = "en"
		self.ensure_fiscal_years()
		if not frappe.db.get_single_value("Global Defaults", "default_company"):
			frappe.db.set_default("company", self.company)
			frappe.db.set_single_value("Global Defaults", "default_company", self.company)

	def ensure_fiscal_years(self):
		year = (self.start - timedelta(days=1)).year
		first = date(year if self.start.month >= 4 else year - 1, 4, 1)
		while first <= self.today:
			name = f"{first.year}-{first.year + 1}"
			end = date(first.year + 1, 3, 31)
			covered = frappe.db.sql(
				"select name from `tabFiscal Year` where year_start_date<=%s and year_end_date>=%s", (first, first)
			)
			if not covered:
				self.insert(frappe.get_doc({
					"doctype": "Fiscal Year", "year": name, "year_start_date": first, "year_end_date": end,
					"companies": [{"company": self.company}],
				}))
			else:
				# A fiscal year limited to other companies would reject our postings.
				fy = frappe.get_doc("Fiscal Year", covered[0][0])
				if fy.companies and self.company not in {r.company for r in fy.companies}:
					fy.append("companies", {"company": self.company})
					fy.flags.ignore_permissions = True
					fy.save()
			first = date(first.year + 1, 4, 1)

	# ------------------------------------------------------------------ masters

	def create_masters(self):
		self.uoms_and_roles()
		self.org_structure()
		self.accounts_and_taxes()
		self.payment_terms()
		self.groups()
		self.create_items()
		self.create_parties()
		self.create_users()
		self.plan_demand()
		frappe.db.commit()

	def uoms_and_roles(self):
		for uom in ("Kg", "Meter", "Litre", "Box"):
			frappe.db.set_value("UOM", uom, "must_be_whole_number", 0)
		if not frappe.db.exists("Role", "Director"):
			self.insert(frappe.get_doc({"doctype": "Role", "role_name": "Director", "desk_access": 1}))

	def org_structure(self):
		parent_wh = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 1}, "name")
		for name in C.WAREHOUSES:
			if not frappe.db.exists("Warehouse", self.wh(name)):
				self.insert(frappe.get_doc({
					"doctype": "Warehouse", "warehouse_name": name, "company": self.company, "parent_warehouse": parent_wh,
				}))
		root_cc = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 1}, "name")
		for name in C.COST_CENTERS:
			if not frappe.db.exists("Cost Center", self.cc(name)):
				self.insert(frappe.get_doc({
					"doctype": "Cost Center", "cost_center_name": name, "company": self.company,
					"parent_cost_center": root_cc,
				}))

	def account(self, name, parent_like, account_type=None):
		full = f"{name} - {self.abbr}"
		if not frappe.db.exists("Account", full):
			parent = frappe.db.get_value("Account", {"company": self.company, "account_name": parent_like, "is_group": 1}, "name")
			self.insert(frappe.get_doc({
				"doctype": "Account", "account_name": name, "company": self.company, "parent_account": parent,
				"account_type": account_type, "account_currency": C.COMPANY["currency"],
			}))
		return full

	def accounts_and_taxes(self):
		bank = self.account("HDFC Bank Current Account", "Bank Accounts", "Bank")
		frappe.db.set_value("Company", self.company, "default_bank_account", bank)
		acc = {k: self.account(k, "Duties and Taxes", "Tax") for k in (
			"Input CGST", "Input SGST", "Input IGST", "Output CGST", "Output SGST", "Output IGST")}
		for doctype, side in (("Purchase Taxes and Charges Template", "Input"), ("Sales Taxes and Charges Template", "Output")):
			for kind, rows in (
				("In-State", [(f"{side} CGST", 9), (f"{side} SGST", 9)]),
				("Inter-State", [(f"{side} IGST", 18)]),
			):
				title = f"GST 18% {kind}"
				if frappe.db.exists(doctype, f"{title} - {self.abbr}"):
					continue
				taxes = []
				for head, rate in rows:
					row = {"charge_type": "On Net Total", "account_head": acc[head], "rate": rate,
						"description": f"{head.split()[1]} @ {rate}%"}
					if doctype.startswith("Purchase"):
						row.update({"category": "Total", "add_deduct_tax": "Add"})
					taxes.append(row)
				self.insert(frappe.get_doc({
					"doctype": doctype, "title": title, "company": self.company,
					"is_default": 1 if kind == "In-State" else 0, "taxes": taxes,
				}))

	def payment_terms(self):
		for name, days in C.PAYMENT_TERMS.items():
			if not frappe.db.exists("Payment Term", name):
				self.insert(frappe.get_doc({
					"doctype": "Payment Term", "payment_term_name": name, "invoice_portion": 100,
					"due_date_based_on": "Day(s) after invoice date", "credit_days": days,
				}))
			if not frappe.db.exists("Payment Terms Template", name):
				self.insert(frappe.get_doc({
					"doctype": "Payment Terms Template", "template_name": name,
					"terms": [{"payment_term": name, "invoice_portion": 100,
						"due_date_based_on": "Day(s) after invoice date", "credit_days": days}],
				}))

	def groups(self):
		for name, parent in C.ITEM_GROUPS:
			if not frappe.db.exists("Item Group", name):
				self.insert(frappe.get_doc({
					"doctype": "Item Group", "item_group_name": name, "parent_item_group": parent,
					"is_group": 1 if any(p == name for _, p in C.ITEM_GROUPS) else 0,
				}))
		for name in C.SUPPLIER_GROUPS:
			if not frappe.db.exists("Supplier Group", name):
				self.insert(frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": name,
					"parent_supplier_group": "All Supplier Groups"}))
		for name in ("Commercial", "Distributor", "Government"):
			if not frappe.db.exists("Customer Group", name):
				self.insert(frappe.get_doc({"doctype": "Customer Group", "customer_group_name": name,
					"parent_customer_group": "All Customer Groups"}))
		if not frappe.db.exists("Territory", "India"):
			self.insert(frappe.get_doc({"doctype": "Territory", "territory_name": "India", "is_group": 1,
				"parent_territory": "All Territories"}))
		frappe.db.set_value("Territory", "India", "is_group", 1)
		for name in ("North India", "South India", "East India", "West India"):
			if not frappe.db.exists("Territory", name):
				self.insert(frappe.get_doc({"doctype": "Territory", "territory_name": name, "parent_territory": "India"}))

	def create_items(self):
		bom_inputs = {code for fg in self.fg.values() for code in fg["bom"]}
		for it in C.ITEMS:
			if frappe.db.exists("Item", it["code"]):
				continue
			stock = it["group"] != "Services"
			self.insert(frappe.get_doc({
				"doctype": "Item", "item_code": it["code"], "item_name": it["name"], "description": it["name"],
				"item_group": it["group"], "stock_uom": it["uom"], "is_stock_item": 1 if stock else 0,
				"include_item_in_manufacturing": 1 if it["code"] in bom_inputs else 0,
				"is_purchase_item": 1, "is_sales_item": 0, "valuation_rate": it["rate"] if stock else 0,
				"lead_time_days": it["lead"],
				# Always set: a blank warehouse is filled from the site default, which may belong to another company.
				"item_defaults": [{"company": self.company, "default_warehouse": self.wh("Stores")}],
			}))
		for code, fg in self.fg.items():
			if frappe.db.exists("Item", code):
				continue
			self.insert(frappe.get_doc({
				"doctype": "Item", "item_code": code, "item_name": fg["name"], "description": fg["name"],
				"item_group": "Finished Goods", "stock_uom": "Nos", "is_stock_item": 1, "is_purchase_item": 0,
				"is_sales_item": 1, "valuation_rate": round(fg["rate"] * 0.62),
				"item_defaults": [{"company": self.company, "default_warehouse": self.wh("Finished Goods")}],
			}))
		for it in C.ITEMS:
			self.item_price(it["code"], "Standard Buying", it["rate"])
		for code, fg in self.fg.items():
			self.item_price(code, "Standard Selling", fg["rate"])

	def item_price(self, item_code, price_list, rate):
		if not frappe.db.exists("Item Price", {"item_code": item_code, "price_list": price_list}):
			self.insert(frappe.get_doc({"doctype": "Item Price", "item_code": item_code, "price_list": price_list,
				"price_list_rate": rate}))

	def create_parties(self):
		state_codes = {"Maharashtra": "27", "Gujarat": "24", "Karnataka": "29", "Tamil Nadu": "33", "Punjab": "03",
			"Andhra Pradesh": "37", "Uttar Pradesh": "09", "West Bengal": "19", "Rajasthan": "08", "Telangana": "36",
			"Haryana": "06", "Odisha": "21", "Delhi": "07", "Goa": "30"}
		cities = {"Maharashtra": ["Pune", "Mumbai", "Nashik", "Kolhapur", "Aurangabad"], "Gujarat": ["Ahmedabad", "Rajkot", "Vadodara"],
			"Karnataka": ["Bengaluru", "Mysuru"], "Tamil Nadu": ["Chennai", "Coimbatore"], "Punjab": ["Ludhiana"],
			"Andhra Pradesh": ["Visakhapatnam"], "Uttar Pradesh": ["Kanpur", "Lucknow"], "West Bengal": ["Kolkata"],
			"Rajasthan": ["Jaipur"], "Telangana": ["Hyderabad"], "Haryana": ["Gurugram"], "Odisha": ["Bhubaneswar"],
			"Delhi": ["New Delhi"], "Goa": ["Vasco da Gama"]}
		first_names = ["Amit", "Sunita", "Rajesh", "Pooja", "Manoj", "Deepa", "Sanjay", "Meera", "Ashok", "Lata", "Nitin", "Rekha"]
		last_names = ["Shah", "Patel", "Reddy", "Kumar", "Gupta", "Pawar", "Menon", "Singh", "Jain", "Bose", "Naik", "Verma"]

		def gstin(state):
			letters = "".join(self.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(5))
			return f"{state_codes[state]}{letters}{self.rng.randint(1000, 9999)}{self.rng.choice('ABCDEFGH')}1Z{self.rng.randint(1, 9)}"

		def address_and_contact(doctype, name, state, email_prefix):
			slug = re.sub(r"[^a-z0-9]+", "", name.lower())[:24]
			self.insert(frappe.get_doc({
				"doctype": "Address", "address_title": name, "address_type": "Billing",
				"address_line1": f"Plot {self.rng.randint(3, 180)}, {self.rng.choice(['MIDC', 'Industrial Estate', 'GIDC', 'Phase II'])}",
				"city": self.rng.choice(cities[state]), "state": state, "country": "India",
				"pincode": str(self.rng.randint(110001, 799999)), "email_id": f"{email_prefix}@{slug}.example",
				"phone": f"+91 9{self.rng.randint(100000000, 999999999)}",
				"is_primary_address": 1, "links": [{"link_doctype": doctype, "link_name": name}],
			}))
			self.insert(frappe.get_doc({
				"doctype": "Contact", "first_name": self.rng.choice(first_names), "last_name": self.rng.choice(last_names),
				"email_ids": [{"email_id": f"{email_prefix}@{slug}.example", "is_primary": 1}],
				"phone_nos": [{"phone": f"+91 9{self.rng.randint(100000000, 999999999)}", "is_primary_mobile_no": 1}],
				"is_primary_contact": 1, "links": [{"link_doctype": doctype, "link_name": name}],
			}))

		for name, s in self.suppliers.items():
			if frappe.db.exists("Supplier", name):
				continue
			self.insert(frappe.get_doc({
				"doctype": "Supplier", "supplier_name": name, "supplier_group": s["group"], "supplier_type": "Company",
				"country": "India", "default_currency": "INR", "tax_id": gstin(s["state"]),
				"payment_terms": s["terms"],
			}))
			address_and_contact("Supplier", name, s["state"], "sales")
		for name, c in self.customers.items():
			if frappe.db.exists("Customer", name):
				continue
			self.insert(frappe.get_doc({
				"doctype": "Customer", "customer_name": name, "customer_group": c["group"], "customer_type": "Company",
				"territory": c["territory"], "default_currency": "INR", "tax_id": gstin(c["state"]),
				"payment_terms": c["terms"],
			}))
			address_and_contact("Customer", name, c["state"], "purchase")

		# Which suppliers can supply each item: by item group, or by item code for services.
		self.item_suppliers = {}
		for code, it in self.items.items():
			capable = [n for n, s in self.suppliers.items() if it["group"] in s["supplies"] or code in s["supplies"]]
			capable = [n for n in capable if n != "Express Industrial Traders"] or capable
			self.rng.shuffle(capable)
			self.item_suppliers[code] = capable
		for code, names in self.item_suppliers.items():
			if names:
				frappe.db.set_value("Item Default", {"parent": code, "company": self.company}, "default_supplier", names[0])

	def create_users(self):
		if not self.password:
			return
		for first, last, key, roles in C.USERS:
			email = self.users[key]
			if frappe.db.exists("User", email):
				continue
			user = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "user_type": "System User", "new_password": self.password,
				"roles": [{"role": r} for r in roles],
			})
			user.flags.no_welcome_mail = True
			self.insert(user)
			frappe.defaults.set_user_default("company", self.company, email)

	def plan_demand(self):
		demand = self.scale["demand"]
		self.fg_weekly = {code: w * demand for code, w in C.FG_WEEKLY_DEMAND.items()}
		weekly = defaultdict(float)
		for fg_code, fg in self.fg.items():
			for code, per in fg["bom"].items():
				weekly[code] += per * self.fg_weekly[fg_code]
		self.indirect_weekly = {}
		for code, it in self.items.items():
			if it["group"] == "Services":
				continue
			if it["group"] in C.INDIRECT_MONTHLY:
				lo, hi = C.INDIRECT_MONTHLY[it["group"]]
				monthly = self.rng.uniform(lo, hi) * (1 if it["rate"] < 5000 else 0.3)
			elif weekly[code] == 0:
				monthly = self.rng.uniform(1, 6)  # maintenance usage of components not in any BOM
			else:
				monthly = 0
			self.indirect_weekly[code] = monthly * demand / 4.33
		self.weekly_use = {code: weekly[code] + self.indirect_weekly.get(code, 0)
			for code, it in self.items.items() if it["group"] != "Services"}
		self.reorder = {}
		for code, use in self.weekly_use.items():
			lead_weeks = self.items[code]["lead"] / 7
			level = use * (lead_weeks + 1.5)
			cheap = use * self.items[code]["rate"] < 5000
			order = use * (self.rng.uniform(13, 20) if cheap else self.rng.uniform(6, 10))
			self.reorder[code] = (self.qty(code, level), self.qty(code, order))
			doc = frappe.get_doc("Item", code)
			if not doc.reorder_levels:
				doc.append("reorder_levels", {"warehouse": self.wh("Stores"), "warehouse_reorder_level": self.reorder[code][0],
					"warehouse_reorder_qty": self.reorder[code][1], "material_request_type": "Purchase"})
				doc.flags.ignore_permissions = True
				doc.save()

	# ------------------------------------------------------------------ history

	def run_history(self):
		opening = self.start - timedelta(days=1)
		self.opening_stock(opening)
		self.create_boms()
		frappe.db.commit()

		d = self.start
		while d <= self.today:
			if d.weekday() == 0:
				self.schedule(d, P_ORDER, self.plan_week_sales, d)
				self.schedule(d, P_PRODUCE, self.produce, d)
				self.schedule(d, P_PLAN, self.mrp, d)
				self.schedule(d, P_RECEIPT, self.indirect_consumption, d)
			if d.weekday() < 6:
				self.schedule(d, P_DELIVER, self.deliver, d)
			if d.day == 1:
				self.schedule(d, P_ORDER, self.monthly_services, d)
			d += timedelta(days=1)
		self.plant_exceptions()

		last_day = None
		while self.events:
			d, _, _, fn, args, kwargs = heapq.heappop(self.events)
			if last_day and d != last_day:
				frappe.db.commit()
				if d.day == 1:
					print(f"{d}: {dict(self.counts)} errors={len(self.errors)}", flush=True)
			last_day = d
			self.run_safely(f"{d} {fn.__name__}", fn, *args, **kwargs)
		frappe.db.commit()

	def opening_stock(self, d):
		if frappe.db.exists("Stock Reconciliation", {"company": self.company, "purpose": "Opening Stock", "docstatus": 1}):
			return
		temp = frappe.db.get_value("Account", {"company": self.company, "account_type": "Temporary", "is_group": 0}, "name")
		rows = []
		for code, use in self.weekly_use.items():
			if use <= 0:
				continue
			rows.append({"item_code": code, "warehouse": self.wh("Stores"), "qty": self.qty(code, use * self.rng.uniform(5, 8)),
				"valuation_rate": self.items[code]["rate"]})
		for code, weekly in self.fg_weekly.items():
			rows.append({"item_code": code, "warehouse": self.wh("Finished Goods"), "qty": self.qty(code, weekly * 1.5),
				"valuation_rate": round(self.fg[code]["rate"] * 0.62)})
		doc = frappe.get_doc({
			"doctype": "Stock Reconciliation", "company": self.company, "purpose": "Opening Stock",
			"posting_date": d, "posting_time": "08:00:00", "set_posting_time": 1, "expense_account": temp,
			"cost_center": frappe.db.get_value("Company", self.company, "cost_center"), "items": rows,
		})
		self.insert(doc)
		self.finish(doc, d, "08:00:00")

	def create_boms(self):
		for code, fg in self.fg.items():
			if frappe.db.exists("BOM", {"item": code, "is_default": 1, "docstatus": 1}):
				continue
			doc = frappe.get_doc({
				"doctype": "BOM", "item": code, "company": self.company, "quantity": 1, "is_active": 1, "is_default": 1,
				"rm_cost_as_per": "Valuation Rate", "currency": "INR",
				"items": [{"item_code": c, "qty": q} for c, q in fg["bom"].items()],
			})
			self.insert(doc)
			doc.submit()
			self.counts["BOM"] += 1
		self.boms = {code: frappe.db.get_value("BOM", {"item": code, "is_default": 1, "docstatus": 1}) for code in self.fg}

	# -- sales

	def plan_week_sales(self, monday):
		lines = []
		for code, weekly in self.fg_weekly.items():
			season = 1 + 0.25 * ((monday.month in (3, 4, 5)) - (monday.month in (7, 8)))  # pre-monsoon pump season
			qty = max(0, int(round(self.rng.gauss(weekly * season, weekly * 0.35))))
			if qty and self.rng.random() < 0.3 and qty > 1:
				first = qty // 2
				lines += [(code, first), (code, qty - first)]
			elif qty:
				lines.append((code, qty))
		self.rng.shuffle(lines)
		while lines:
			n = self.rng.randint(2, 5)
			order, lines = lines[:n], lines[n:]
			day = monday + timedelta(days=self.rng.randint(0, 4))
			customer = self.rng.choice(list(self.customers))
			self.schedule(day, P_ORDER, self.sales_order, day, customer, order)

	def sales_order(self, d, customer, lines):
		self.as_user("arjun.nair")
		c = self.customers[customer]
		template, taxes = self.taxes("Sales Taxes and Charges Template", c["state"])
		merged = defaultdict(int)
		for code, q in lines:
			merged[code] += q
		delivery = d + timedelta(days=self.rng.randint(7, 21))
		doc = frappe.get_doc({
			"doctype": "Sales Order", "customer": customer, "company": self.company, "transaction_date": d,
			"delivery_date": delivery, "set_warehouse": self.wh("Finished Goods"), "order_type": "Sales",
			"payment_terms_template": c["terms"], "taxes_and_charges": template, "taxes": taxes,
			"po_no": f"{''.join(w[0] for w in customer.split()[:3]).upper()}/PO/{self.rng.randint(1000, 9999)}",
			"cost_center": self.cc("Sales and Marketing"),
			"items": [{"item_code": code, "qty": q, "rate": round(self.fg[code]["rate"] * self.rng.uniform(0.94, 1.03)),
				"delivery_date": delivery, "warehouse": self.wh("Finished Goods")} for code, q in merged.items()],
		})
		self.insert(doc)
		self.finish(doc, d, self.stamp(d))
		self.open_sos.append(doc.name)

	def deliver(self, d):
		if not self.open_sos:
			return
		stock = {k: v.actual_qty for k, v in self.bins(self.wh("Finished Goods")).items()}
		for so_name in list(self.open_sos):
			so = frappe.get_doc("Sales Order", so_name)
			if so.status in ("Completed", "Closed", "Cancelled"):
				self.open_sos.remove(so_name)
				continue
			if getdate(so.delivery_date) > d + timedelta(days=4):
				continue
			pending = {i.item_code: i.qty - i.delivered_qty for i in so.items}
			if any(stock.get(code, 0) < q for code, q in pending.items() if q > 0):
				continue
			for code, q in pending.items():
				stock[code] = stock.get(code, 0) - q
			self.open_sos.remove(so_name)
			self.run_safely(f"{d} delivery {so_name}", self.delivery_note, d, so_name)

	def delivery_note(self, d, so_name):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		self.as_user("suresh.patil")
		dn = make_delivery_note(so_name)
		t = self.stamp(d)
		dn.update({"posting_date": d, "posting_time": t, "set_posting_time": 1,
			"lr_no": f"LR{self.rng.randint(100000, 999999)}", "transporter_name": None})
		self.insert(dn)
		self.finish(dn, d, t)
		inv_day = d + timedelta(days=self.rng.randint(0, 2))
		self.schedule(inv_day, P_INVOICE, self.sales_invoice, inv_day, dn.name)

	def sales_invoice(self, d, dn_name):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		self.as_user("neha.iyer")
		si = make_sales_invoice(dn_name)
		t = self.stamp(d)
		si.update({"posting_date": d, "posting_time": t, "set_posting_time": 1, "due_date": None})
		si.set("payment_schedule", [])
		self.insert(si)
		self.finish(si, d, t)
		customer = self.customers[si.customer]
		if self.rng.random() < 0.05:
			return  # disputed, stays outstanding
		pay = getdate(si.due_date) + timedelta(days=self.rng.randint(-5, customer["late"]))
		pay = max(pay, d)
		self.schedule(pay, P_PAY, self.payment, pay, "Sales Invoice", si.name)

	# -- production and consumption

	def produce(self, d):
		fg_stock = {k: v.actual_qty for k, v in self.bins(self.wh("Finished Goods")).items()}
		raw = {k: v.actual_qty for k, v in self.bins(self.wh("Stores")).items()}
		backlog = defaultdict(float)
		for row in frappe.db.sql("""select soi.item_code, sum(soi.qty - soi.delivered_qty) qty
			from `tabSales Order Item` soi join `tabSales Order` so on so.name = soi.parent
			where so.docstatus = 1 and so.status not in ('Completed', 'Closed') and so.company=%s
			group by soi.item_code""", self.company, as_dict=True):
			backlog[row.item_code] = row.qty
		for code in sorted(self.fg, key=lambda c: -(backlog[c] - fg_stock.get(c, 0))):
			need = backlog[code] + self.fg_weekly[code] * 1.2 - fg_stock.get(code, 0)
			if need < 1:
				continue
			bom = self.fg[code]["bom"]
			can = min(raw.get(c, 0) / q for c, q in bom.items())
			make = int(min(need, can))
			if make < 1:
				continue
			for c, q in bom.items():
				raw[c] = raw.get(c, 0) - q * make
			self.run_safely(f"{d} manufacture {code}", self.manufacture, d, code, make)

	def manufacture(self, d, code, qty):
		self.as_user("kavita.rao")
		se = frappe.new_doc("Stock Entry")
		t = self.stamp(d)
		se.update({"stock_entry_type": "Manufacture", "purpose": "Manufacture", "company": self.company,
			"from_bom": 1, "bom_no": self.boms[code], "fg_completed_qty": qty, "use_multi_level_bom": 0,
			"from_warehouse": self.wh("Stores"), "to_warehouse": self.wh("Finished Goods"),
			"posting_date": d, "posting_time": t, "set_posting_time": 1})
		se.get_items()
		self.insert(se)
		self.finish(se, d, t)

	def indirect_consumption(self, d):
		stock = {k: v.actual_qty for k, v in self.bins(self.wh("Stores")).items()}
		by_cc = defaultdict(list)
		for code, weekly in self.indirect_weekly.items():
			if weekly <= 0:
				continue
			q = self.qty(code, weekly * self.rng.uniform(0.6, 1.4))
			if self.items[code]["uom"] in WHOLE_UOMS and weekly < 1 and self.rng.random() > weekly:
				continue
			q = min(q, stock.get(code, 0))
			if q <= 0:
				continue
			group = self.items[code]["group"]
			cc = {"IT Equipment": "IT", "Office Supplies": "Administration", "Packaging": "Sales and Marketing",
				"Consumable": "Production"}.get(group, "Maintenance")
			by_cc[cc].append((code, q))
		for cc, rows in by_cc.items():
			self.run_safely(f"{d} issue {cc}", self.material_issue, d, cc, rows)

	def material_issue(self, d, cc, rows):
		self.as_user("suresh.patil")
		t = self.stamp(d)
		se = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "purpose": "Material Issue",
			"company": self.company, "posting_date": d, "posting_time": t, "set_posting_time": 1,
			"from_warehouse": self.wh("Stores"), "remarks": f"Issued to {cc}",
			"items": [{"item_code": c, "qty": q, "s_warehouse": self.wh("Stores"), "cost_center": self.cc(cc)} for c, q in rows],
		})
		self.insert(se)
		self.finish(se, d, t)

	# -- procurement

	def mrp(self, d):
		bins = self.bins(self.wh("Stores"))
		lines = []
		for code, (level, order) in self.reorder.items():
			b = bins.get(code)
			projected = b.projected_qty if b else 0
			if projected < level:
				shortfall = level - projected
				lines.append((code, self.qty(code, max(order, shortfall))))
		if lines:
			self.material_request(d, lines)

	def material_request(self, d, lines, purpose_note=None):
		self.as_user("suresh.patil")
		required_by = d + timedelta(days=max(self.items[c]["lead"] for c, _ in lines) + 3)
		t = self.stamp(d)
		mr = frappe.get_doc({
			"doctype": "Material Request", "material_request_type": "Purchase", "company": self.company,
			"transaction_date": d, "schedule_date": required_by, "set_warehouse": self.wh("Stores"),
			"items": [{"item_code": c, "qty": q, "schedule_date": d + timedelta(days=self.items[c]["lead"] + 3),
				"warehouse": self.wh("Stores"), "cost_center": self.cc("Production")} for c, q in lines],
		})
		self.insert(mr)
		self.finish(mr, d, t)
		# Expensive or multi-source lines go out for quotation; routine ones are ordered directly.
		rfq_rows, direct = [], defaultdict(list)
		for row in mr.items:
			value = row.qty * self.items[row.item_code]["rate"]
			suppliers = self.item_suppliers.get(row.item_code) or []
			if len(suppliers) >= 2 and (value > 60000 or self.rng.random() < 0.3):
				rfq_rows.append(row)
			elif suppliers:
				direct[self.pick_supplier(row.item_code)].append(row)
		for supplier, rows in direct.items():
			day = d + timedelta(days=self.rng.randint(1, 2))
			self.schedule(day, P_ORDER, self.po_from_rows, day, supplier,
				[{"item_code": r.item_code, "qty": r.qty, "material_request": mr.name, "material_request_item": r.name} for r in rows])
		by_group = defaultdict(list)
		for row in rfq_rows:
			by_group[self.items[row.item_code]["group"]].append(row)
		for group, rows in by_group.items():
			day = d + timedelta(days=self.rng.randint(1, 2))
			self.schedule(day, P_ORDER, self.rfq, day, mr.name, [r.name for r in rows])

	def pick_supplier(self, code):
		names = self.item_suppliers[code]
		if len(names) == 1 or self.rng.random() < 0.8:
			return names[0]
		return self.rng.choice(names[1:])

	def price(self, supplier, code, d):
		base = self.items[code]["rate"] * self.suppliers[supplier]["price"]
		months = (d - self.start).days / 30
		drift = 0.006 if self.items[code]["group"] in ("Steel", "Non-Ferrous Metals", "Castings") else 0.002
		return round(base * (1 + drift * months) * self.rng.uniform(0.97, 1.03), 2)

	def rfq(self, d, mr_name, row_names):
		self.as_user(self.rng.choice(["priya.kulkarni", "rahul.deshmukh"]))
		rows = [frappe.get_doc("Material Request Item", n) for n in row_names]
		capable = set(self.item_suppliers[rows[0].item_code])
		for r in rows[1:]:
			capable &= set(self.item_suppliers[r.item_code])
		capable = sorted(capable) or self.item_suppliers[rows[0].item_code]
		invited = self.rng.sample(capable, min(len(capable), self.rng.randint(2, 3)))
		t = self.stamp(d)
		rfq = frappe.get_doc({
			"doctype": "Request for Quotation", "company": self.company, "transaction_date": d,
			"schedule_date": max(r.schedule_date for r in rows),
			"message_for_supplier": "Please share your best price and delivery schedule for the items below.",
			"suppliers": [{"supplier": s, "send_email": 0} for s in invited],
			"items": [{"item_code": r.item_code, "item_name": r.item_name, "description": r.description, "qty": r.qty,
				"uom": r.uom, "stock_uom": r.stock_uom, "conversion_factor": 1, "schedule_date": r.schedule_date,
				"warehouse": r.warehouse, "material_request": mr_name, "material_request_item": r.name} for r in rows],
		})
		self.insert(rfq)
		self.finish(rfq, d, t)
		quote_day = d + timedelta(days=self.rng.randint(2, 4))
		self.schedule(quote_day, P_ORDER, self.quotations, quote_day, rfq.name)

	def quotations(self, d, rfq_name):
		rfq = frappe.get_doc("Request for Quotation", rfq_name)
		quotes = []
		responders = [s.supplier for s in rfq.suppliers if self.rng.random() < 0.85] or [rfq.suppliers[0].supplier]
		for supplier in responders:
			self.as_user("priya.kulkarni")
			t = self.stamp(d)
			sq = frappe.get_doc({
				"doctype": "Supplier Quotation", "supplier": supplier, "company": self.company, "transaction_date": d,
				"valid_till": d + timedelta(days=30), "quotation_number": f"Q-{self.rng.randint(10000, 99999)}",
				"items": [{"item_code": i.item_code, "qty": i.qty, "uom": i.uom, "conversion_factor": 1,
					"rate": self.price(supplier, i.item_code, d), "warehouse": i.warehouse,
					"request_for_quotation": rfq.name, "request_for_quotation_item": i.name,
					"material_request": i.material_request, "material_request_item": i.material_request_item,
					"lead_time_days": self.items[i.item_code]["lead"]} for i in rfq.items],
			})
			self.insert(sq)
			self.finish(sq, d, t)
			quotes.append(sq)
		self.actor = "Administrator"
		# Usually the cheapest wins; sometimes the buyer sticks with the incumbent.
		quotes.sort(key=lambda q: q.grand_total)
		winner = quotes[0] if self.rng.random() < 0.85 or len(quotes) == 1 else quotes[1]
		award = d + timedelta(days=self.rng.randint(1, 3))
		rows = [{"item_code": i.item_code, "qty": i.qty, "rate": i.rate, "supplier_quotation": winner.name,
			"supplier_quotation_item": i.name, "material_request": i.material_request,
			"material_request_item": i.material_request_item} for i in winner.items]
		self.schedule(award, P_ORDER, self.po_from_rows, award, winner.supplier, rows)

	def po_from_rows(self, d, supplier, rows, **opts):
		s = self.suppliers[supplier]
		template, taxes = self.taxes("Purchase Taxes and Charges Template", s["state"])
		items = []
		for r in rows:
			rate = r.get("rate") or self.price(supplier, r["item_code"], d)
			if opts.get("spike") or (not r.get("supplier_quotation") and self.rng.random() < 0.04):
				rate = round(rate * self.rng.uniform(1.15, 1.35), 2)
			lead = self.items[r["item_code"]]["lead"]
			sched = d if opts.get("same_day") else d + timedelta(days=lead)
			items.append({**r, "rate": rate, "schedule_date": sched, "expected_delivery_date": sched,
				"warehouse": self.wh("Stores")})
		total = sum(i["qty"] * i["rate"] for i in items) * 1.18
		if opts.get("user"):
			user = opts["user"]
		elif total > 150000:
			user = "vikram.joshi" if self.rng.random() < 0.85 else "anjali.mehta"
		else:
			user = self.rng.choice(["priya.kulkarni", "rahul.deshmukh", "anjali.mehta"])
		self.as_user(user)
		no_cc = opts.get("no_cost_center") or self.rng.random() < 0.05
		t = self.stamp(d)
		po = frappe.get_doc({
			"doctype": "Purchase Order", "supplier": supplier, "company": self.company, "transaction_date": d,
			"schedule_date": min(i["schedule_date"] for i in items), "payment_terms_template": s["terms"],
			"taxes_and_charges": template, "taxes": taxes, "cost_center": None if no_cc else self.cc(opts.get("cost_center", "Production")),
			"items": items,
		})
		if opts.get("same_day"):
			po.schedule_date = d
		self.insert(po)
		self.finish(po, d, t)
		self.plan_receipt(po)
		return po

	def plan_receipt(self, po):
		s = self.suppliers[po.supplier]
		services = all(self.items[i.item_code]["group"] == "Services" for i in po.items)
		due = getdate(po.schedule_date)
		if services:
			bill = due + timedelta(days=self.rng.randint(0, 5))
			self.schedule(bill, P_INVOICE, self.invoice_from_po, bill, po.name)
			return
		if self.rng.random() < s["on_time"]:
			arrive = due - timedelta(days=self.rng.randint(0, 2))
		else:
			arrive = due + timedelta(days=self.rng.randint(1, max(1, s["delay"])))
		arrive = max(arrive, getdate(po.transaction_date))
		partial = self.rng.random() < 0.12
		self.schedule(arrive, P_RECEIPT, self.receipt, arrive, po.name, 0.6 + self.rng.random() * 0.3 if partial else 1)
		if partial:
			later = arrive + timedelta(days=self.rng.randint(5, 12))
			self.schedule(later, P_RECEIPT, self.receipt, later, po.name, 1)

	def receipt(self, d, po_name, fraction):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

		po = frappe.get_doc("Purchase Order", po_name)
		if po.status in ("Closed", "Completed") or po.per_received >= 99.9:
			return
		s = self.suppliers[po.supplier]
		self.as_user("suresh.patil")
		pr = make_purchase_receipt(po_name)
		t = self.stamp(d)
		pr.update({"posting_date": d, "posting_time": t, "set_posting_time": 1,
			"supplier_delivery_note": f"DC-{self.rng.randint(1000, 99999)}", "rejected_warehouse": self.wh("Rejected Stores")})
		for item in pr.items:
			received = self.qty(item.item_code, item.qty * fraction) if fraction < 1 else item.qty
			received = min(received, item.qty)
			rejected = 0
			if s["reject"] and self.rng.random() < 0.35:
				raw = received * self.rng.uniform(0, s["reject"] * 3)
				smallest = 1 if self.items[item.item_code]["uom"] in WHOLE_UOMS else 0.5
				rejected = self.qty(item.item_code, raw) if raw >= smallest else 0
				rejected = rejected if rejected < received else 0
			item.received_qty = received
			item.rejected_qty = rejected
			item.qty = received - rejected
			item.rejected_warehouse = self.wh("Rejected Stores") if rejected else None
		self.insert(pr)
		self.finish(pr, d, t)
		bill = d + timedelta(days=self.rng.randint(0, 4))
		self.schedule(bill, P_INVOICE, self.invoice_from_pr, bill, pr.name)

	def next_bill_no(self, supplier):
		self.bill_no += 1
		prefix = "".join(w[0] for w in supplier.split()[:3]).upper()
		return f"{prefix}/{self.rng.randint(25, 26)}-{self.rng.randint(26, 27)}/{self.bill_no:05d}"

	def invoice_from_pr(self, d, pr_name):
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

		self.purchase_invoice(d, make_purchase_invoice(pr_name))

	def invoice_from_po(self, d, po_name):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		self.purchase_invoice(d, make_purchase_invoice(po_name))

	def purchase_invoice(self, d, pi):
		self.as_user("neha.iyer")
		t = self.stamp(d)
		pi.update({"posting_date": d, "posting_time": t, "set_posting_time": 1, "bill_no": self.next_bill_no(pi.supplier),
			"bill_date": d - timedelta(days=self.rng.randint(0, 3)), "due_date": None})
		pi.set("payment_schedule", [])
		self.insert(pi)
		self.finish(pi, d, t)
		if self.rng.random() < 0.04:
			return  # held for a dispute, stays outstanding
		pay = getdate(pi.due_date) + timedelta(days=self.rng.randint(-6, 10))
		pay = max(pay, d)
		self.schedule(pay, P_PAY, self.payment, pay, "Purchase Invoice", pi.name)

	def payment(self, d, doctype, name):
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		if not flt(frappe.db.get_value(doctype, name, "outstanding_amount")):
			return
		self.as_user("neha.iyer")
		pe = get_payment_entry(doctype, name)
		t = self.stamp(d)
		pe.update({"posting_date": d, "mode_of_payment": "Wire Transfer",
			"reference_no": f"UTR{self.rng.randint(10**11, 10**12 - 1)}", "reference_date": d})
		self.insert(pe)
		self.finish(pe, d, t)

	def monthly_services(self, d):
		plan = [("CleanPro Facility Services", "SRV-HK", "Administration"),
			("Guardian Security Services", "SRV-SECURITY", "Administration"),
			("MachineCare AMC Services", "SRV-ELEC-MAINT", "Maintenance"),
			("SwiftMove Logistics", "SRV-FREIGHT", "Sales and Marketing")]
		if d.month in (1, 4, 7, 10):
			plan.append(("MachineCare AMC Services", "SRV-AMC-CNC", "Maintenance"))
		if d.month % 2 == 0:
			plan.append(("Accurate Calibration Labs", "SRV-CALIB", "Production"))
		for supplier, code, cc in plan:
			qty = self.rng.randint(2, 5) if code == "SRV-FREIGHT" else 1
			self.run_safely(f"{d} service {code}", self.po_from_rows, d, supplier,
				[{"item_code": code, "qty": qty, "rate": self.price(supplier, code, d)}],
				**{"cost_center": cc, "user": "anjali.mehta"})

	def plant_exceptions(self):
		"""One-off events that the Pridict rules and anomaly detectors should flag."""
		span = (self.today - self.start).days
		at = lambda frac: self.start + timedelta(days=int(span * frac))  # noqa: E731
		# Capex-scale services: annual software renewal and a press overhaul (> 5 lakh).
		self.schedule(at(0.35), P_ORDER, self.po_from_rows, at(0.35), "Designsoft Technologies",
			[{"item_code": "SRV-SOFTWARE", "qty": 1}], **{"cost_center": "IT", "user": "vikram.joshi"})
		self.schedule(at(0.6), P_ORDER, self.po_from_rows, at(0.6), "MachineCare AMC Services",
			[{"item_code": "SRV-PRESS-OH", "qty": 1}], **{"cost_center": "Maintenance", "user": "vikram.joshi"})
		# Split purchases: two orders to one supplier within 48h, each under 1.5 lakh, together above it.
		for frac, supplier, code in ((0.22, "Om Sai Electric Motors", "ELE-MTR-5HP"),
				(0.5, "Hydrotech Engineers", "HYD-DCV-4"), (0.83, "Shree Ganesh Steels", "RM-SS316-40")):
			d1 = at(frac)
			unit = self.price(supplier, code, d1) * 1.18
			q = self.qty(code, 120000 / unit)
			for offset in (0, self.rng.randint(1, 2)):
				day = d1 + timedelta(days=offset)
				self.schedule(day, P_ORDER, self.po_from_rows, day, supplier, [{"item_code": code, "qty": q}],
					**{"user": "rahul.deshmukh"})
		# Maverick spend: urgent direct buys from a high-priced trader, no MR or quotation.
		for i in range(max(4, span // 30 * 2)):
			day = self.start + timedelta(days=self.rng.randint(14, span))
			code = self.rng.choice([c for c, it in self.items.items()
				if it["group"] in ("Fasteners", "Electrical", "Bearings", "Consumable")])
			q = self.qty(code, max(1, self.weekly_use.get(code, 2) * self.rng.uniform(1, 3)))
			self.schedule(day, P_ORDER, self.po_from_rows, day, "Express Industrial Traders",
				[{"item_code": code, "qty": q}], **{"user": self.rng.choice(["priya.kulkarni", "rahul.deshmukh"]),
				"same_day": i % 3 == 0, "no_cost_center": i % 4 == 0})
		# IT refresh with a price spike on one line.
		day = at(0.7)
		self.schedule(day, P_ORDER, self.po_from_rows, day, "Laptop World Pune",
			[{"item_code": "IT-LAP-14", "qty": 6}, {"item_code": "IT-MON-24", "qty": 6}],
			**{"cost_center": "IT", "spike": True, "user": "priya.kulkarni"})

	# ------------------------------------------------------------------ report

	def report(self):
		print("Seeded:", dict(self.counts))
		print(f"Errors: {len(self.errors)}")
		for e in self.errors[:40]:
			print(" -", e)
