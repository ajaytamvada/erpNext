"""Code-defined defaults for Agent Studio.

Tools and workflow graphs are owned by code: their contracts change only with a deploy.
Policies and the procurement agent are seeded once and then owned by administrators.
"""

from __future__ import annotations

PROCUREMENT_AGENT = "Procurement Sourcing Agent"
PROCUREMENT_WORKFLOW = "procurement_sourcing"
# Tools that create master data once the buyer confirms in chat (no Agent Approval needed).
MASTER_DATA_TOOLS = ["create_item", "create_supplier", "link_item_supplier"]


def _obj(properties: dict, required: list[str] | None = None) -> dict:
	return {
		"type": "object",
		"properties": properties,
		"required": required or list(properties),
		"additionalProperties": False,
	}


STR = {"type": "string"}
NUM = {"type": "number"}
DATE = {"type": "string", "format": "date"}


def _int(maximum: int) -> dict:
	return {"type": "integer", "minimum": 1, "maximum": maximum}


def _list(item: dict) -> dict:
	return {"type": "array", "items": item}


# Status here is the default for a fresh install; administrators may disable a tool,
# but "Blocked for agents" is enforced by code and re-applied on every sync.
TOOLS: list[dict] = [
	{
		"tool_name": "search_items",
		"access": "Read",
		"status": "Enabled",
		"target": "Item",
		"scope": "Item: read",
		"timeout_s": 5,
		"description": "Find Item records whose code or name matches a search phrase.",
		"input_schema": _obj({"query": STR, "limit": _int(10)}, ["query"]),
		"output_schema": _obj(
			{"items": _list(_obj({"item_code": STR, "item_name": STR, "stock_uom": STR, "item_group": STR}))}
		),
	},
	{
		"tool_name": "get_warehouses",
		"access": "Read",
		"status": "Enabled",
		"target": "Warehouse",
		"scope": "Warehouse: read (company-filtered)",
		"timeout_s": 5,
		"description": "List non-group warehouses of a company.",
		"input_schema": _obj({"company": STR}),
		"output_schema": _obj({"warehouses": _list(_obj({"name": STR, "is_group": {"type": "boolean"}}))}),
	},
	{
		"tool_name": "get_stock_balance",
		"access": "Read",
		"status": "Enabled",
		"target": "Bin",
		"scope": "Bin: read",
		"timeout_s": 5,
		"description": "Current actual, reserved and projected quantity of an item in a warehouse.",
		"input_schema": _obj({"item_code": STR, "warehouse": STR}),
		"output_schema": _obj({"actual_qty": NUM, "reserved_qty": NUM, "projected_qty": NUM}),
	},
	{
		"tool_name": "get_open_purchase_orders",
		"access": "Read",
		"status": "Enabled",
		"target": "Purchase Order",
		"scope": "Purchase Order: read",
		"timeout_s": 8,
		"description": "Submitted purchase orders with quantity still to be received, arriving on or before a date.",
		"input_schema": _obj({"item_code": STR, "warehouse": STR, "before_date": DATE}),
		"output_schema": _obj(
			{"orders": _list(_obj({"name": STR, "supplier": STR, "pending_qty": NUM, "schedule_date": DATE}))}
		),
	},
	{
		"tool_name": "get_approved_suppliers",
		"access": "Read",
		"status": "Enabled",
		"target": "Supplier, Item Supplier",
		"scope": "Supplier: read",
		"timeout_s": 5,
		"description": "Suppliers listed for the item in Item Supplier, with hold status and lead time.",
		"input_schema": _obj({"item_code": STR}),
		"output_schema": _obj(
			{
				"suppliers": _list(
					_obj({"supplier": STR, "on_hold": {"type": "boolean"}, "lead_time_days": NUM})
				)
			}
		),
	},
	{
		"tool_name": "get_price_history",
		"access": "Read",
		"status": "Enabled",
		"target": "Purchase Order Item",
		"scope": "Purchase Order: read",
		"timeout_s": 8,
		"description": "Purchase rates paid for the item over the last N days, with the average.",
		"input_schema": _obj({"item_code": STR, "days": _int(365)}),
		"output_schema": _obj(
			{
				"prices": _list(_obj({"supplier": STR, "rate": NUM, "date": DATE})),
				"avg_rate": NUM,
				"by_supplier": _list(_obj({"supplier": STR, "last_rate": NUM, "last_date": DATE})),
				"line_count": NUM,
			}
		),
	},
	{
		"tool_name": "get_supplier_quotations",
		"access": "Read",
		"status": "Enabled",
		"target": "Supplier Quotation",
		"scope": "Supplier Quotation: read",
		"timeout_s": 8,
		"description": "Submitted supplier quotations for the item that are still valid on a date.",
		"input_schema": _obj({"item_code": STR, "valid_on": DATE}),
		"output_schema": _obj(
			{"quotations": _list(_obj({"name": STR, "supplier": STR, "rate": NUM, "valid_till": DATE}))}
		),
	},
	{
		"tool_name": "score_vendors",
		"access": "Read",
		"status": "Enabled",
		"target": "pridict.decision_intelligence.vendor_scoring",
		"scope": "Purchase Order: read",
		"timeout_s": 10,
		"description": "Score suppliers with the Decision Intelligence vendor scoring engine.",
		"input_schema": _obj({"suppliers": _list(STR)}),
		"output_schema": _obj(
			{
				"scores": _list(
					_obj(
						{
							"supplier": STR,
							"score": NUM,
							"tier": STR,
							"orders_365d": NUM,
							"on_time_pct": NUM,
							"risk_flags": _list(STR),
						}
					)
				)
			}
		),
	},
	{
		"tool_name": "detect_price_anomalies",
		"access": "Read",
		"status": "Enabled",
		"target": "pridict.decision_intelligence.anomaly_detector",
		"scope": "Purchase Order: read",
		"timeout_s": 10,
		"description": "Flag a proposed rate that deviates from recent purchase history.",
		"input_schema": _obj({"item_code": STR, "proposed_rate": NUM}),
		"output_schema": _obj(
			{
				"anomalies": _list(_obj({"title": STR, "severity": STR, "variance_pct": NUM})),
				"benchmark_rate": NUM,
			}
		),
	},
	{
		"tool_name": "create_draft_rfq",
		"access": "Write (draft)",
		"status": "Approval required",
		"target": "Request for Quotation",
		"scope": "RFQ: create (docstatus 0 only)",
		"timeout_s": 15,
		"description": "Create a Request for Quotation in Draft. Only runs after an approved Agent Approval.",
		"input_schema": _obj(
			{"item_code": STR, "qty": NUM, "schedule_date": DATE, "suppliers": _list(STR), "approval_id": STR}
		),
		"output_schema": _obj({"rfq": STR}),
	},
	{
		"tool_name": "create_item",
		"access": "Write (master data)",
		"status": "Enabled",
		"target": "Item",
		"scope": "Item: create (after the buyer confirms in chat)",
		"timeout_s": 10,
		"description": "Create a new Item the buyer asked for and confirmed. Never edits existing items.",
		"input_schema": _obj(
			{
				"item_name": STR,
				"item_group": STR,
				"stock_uom": STR,
				"is_stock_item": {"type": "boolean"},
				"description": STR,
			},
			["item_name", "item_group", "stock_uom", "is_stock_item"],
		),
		"output_schema": _obj({"item_code": STR, "item_name": STR, "stock_uom": STR}),
	},
	{
		"tool_name": "create_supplier",
		"access": "Write (master data)",
		"status": "Enabled",
		"target": "Supplier, Contact",
		"scope": "Supplier: create (after the buyer confirms in chat)",
		"timeout_s": 10,
		"description": "Create a new Supplier the buyer named and confirmed, with a contact if an email is given.",
		"input_schema": _obj({"supplier_name": STR, "email": STR}, ["supplier_name"]),
		"output_schema": _obj({"supplier": STR, "contact": STR}),
	},
	{
		"tool_name": "link_item_supplier",
		"access": "Write (master data)",
		"status": "Enabled",
		"target": "Item Supplier",
		"scope": "Item: add a row to the supplier list (after the buyer confirms in chat)",
		"timeout_s": 10,
		"description": "Add a supplier the buyer chose to the item's approved supplier list.",
		"input_schema": _obj({"item_code": STR, "supplier": STR}),
		"output_schema": _obj({"added": {"type": "boolean"}}),
	},
	{
		"tool_name": "create_draft_purchase_order",
		"access": "Write (draft)",
		"status": "Disabled",
		"target": "Purchase Order",
		"scope": "Purchase Order: create (docstatus 0 only)",
		"timeout_s": 15,
		"description": "Create a Purchase Order in Draft. Not enabled in version 1.",
		"input_schema": _obj(
			{
				"supplier": STR,
				"items": _list(_obj({"item_code": STR, "qty": NUM, "rate": NUM})),
				"approval_id": STR,
			}
		),
		"output_schema": _obj({"purchase_order": STR}),
	},
	{
		"tool_name": "submit_purchase_order",
		"access": "Write (submit)",
		"status": "Blocked for agents",
		"target": "Purchase Order",
		"scope": "Purchase Order: submit",
		"timeout_s": 15,
		"description": "Listed so the boundary is visible. Agents can never submit documents.",
		"input_schema": _obj({"purchase_order": STR}),
		"output_schema": _obj({"status": STR}),
	},
]

POLICIES: list[dict] = [
	{
		"policy_group": "Suppliers",
		"policy_name": "Approved suppliers only",
		"rule_key": "approved_suppliers_only",
		"severity": "Block",
		"description": "Supplier must be listed in Item Supplier and not on hold",
	},
	{
		"policy_group": "Suppliers",
		"policy_name": "Minimum vendor score",
		"rule_key": "min_vendor_score",
		"severity": "Block",
		"description": "Score ≥ 60 (from vendor scoring engine)",
		"parameters": {"min_score": 60},
	},
	{
		"policy_group": "Suppliers",
		"policy_name": "Watchlist suppliers",
		"rule_key": "watchlist_suppliers",
		"severity": "Warn",
		"description": "Allowed, but flagged to the approver",
	},
	{
		"policy_group": "Scope",
		"policy_name": "Permitted companies",
		"rule_key": "permitted_companies",
		"severity": "Block",
		"description": "Only companies listed in parameters (empty = any company the user may access)",
		"parameters": {"companies": []},
	},
	{
		"policy_group": "Scope",
		"policy_name": "Permitted warehouses",
		"rule_key": "permitted_warehouses",
		"severity": "Block",
		"description": "Only warehouses listed in parameters (empty = any warehouse the user may access)",
		"parameters": {"warehouses": []},
	},
	{
		"policy_group": "Data requirements",
		"policy_name": "Required fields",
		"rule_key": "required_fields",
		"severity": "Ask buyer",
		"description": "Item, quantity, UOM, warehouse, need-by date",
		"parameters": {"fields": ["item_code", "qty", "uom", "warehouse", "need_by"]},
	},
	{
		"policy_group": "Data requirements",
		"policy_name": "Need-by date",
		"rule_key": "need_by_not_past",
		"severity": "Ask buyer",
		"description": "Must be today or later",
	},
	{
		"policy_group": "Data requirements",
		"policy_name": "Create missing items and suppliers",
		"rule_key": "create_missing_master_data",
		"severity": "Ask buyer",
		"description": "When the item or a supplier does not exist, the assistant offers to create it and does so only after the buyer confirms in chat",
	},
	{
		"policy_group": "Money & quantity limits",
		"policy_name": "Single approver limit",
		"rule_key": "single_approver_limit",
		"severity": "Approval",
		"description": "Estimated value ≤ ₹5,00,000 → Purchase Manager",
		"parameters": {"max_value": 500000, "roles": ["Purchase Manager"]},
	},
	{
		"policy_group": "Money & quantity limits",
		"policy_name": "Dual approval",
		"rule_key": "dual_approval",
		"severity": "Approval",
		"description": "₹5,00,000 – ₹25,00,000 → Purchase Manager + Finance Manager",
		"parameters": {
			"min_value": 500000,
			"max_value": 2500000,
			"roles": ["Purchase Manager", "Accounts Manager"],
		},
	},
	{
		"policy_group": "Money & quantity limits",
		"policy_name": "Hard ceiling",
		"rule_key": "hard_ceiling",
		"severity": "Block",
		"description": "Above ₹25,00,000 → agent may not prepare the document",
		"parameters": {"max_value": 2500000},
	},
	{
		"policy_group": "Money & quantity limits",
		"policy_name": "Price variance tolerance",
		"rule_key": "price_variance",
		"severity": "Warn",
		"description": "±10% vs 90-day average rate",
		"parameters": {"tolerance_pct": 10, "days": 90},
	},
	{
		"policy_group": "Money & quantity limits",
		"policy_name": "Quantity sanity check",
		"rule_key": "quantity_sanity",
		"severity": "Warn",
		"description": "≤ 3× average monthly consumption",
		"parameters": {"max_multiple": 3},
	},
	{
		"policy_group": "Prohibited for agents",
		"policy_name": "Submit or cancel documents",
		"rule_key": "no_submit",
		"severity": "Block",
		"description": "Agents can only create drafts (docstatus 0)",
	},
	{
		"policy_group": "Prohibited for agents",
		"policy_name": "Change master data",
		"rule_key": "no_master_edits",
		"severity": "Block",
		"description": "No edits to existing Supplier, Item or Price List records (adding a supplier the buyer confirmed to an item's supplier list is allowed)",
	},
	{
		"policy_group": "Prohibited for agents",
		"policy_name": "Self-approval",
		"rule_key": "no_self_approval",
		"severity": "Block",
		"description": "Agent cannot approve its own proposal, and the requester cannot approve their own run",
	},
]

PROCUREMENT_AGENT_DEFAULTS: dict = {
	"agent_name": PROCUREMENT_AGENT,
	"agent_module": "Procurement",
	"agent_type": "Bounded agent",
	"status": "Draft",
	"version": "v1.0",
	"workflow_key": PROCUREMENT_WORKFLOW,
	"mode": "recommend",
	"approval_required": 1,
	"max_steps": 16,
	"max_runtime_s": 180,
	"token_budget": 60000,
	"tools": [
		"search_items",
		"get_warehouses",
		"get_stock_balance",
		"get_open_purchase_orders",
		"get_approved_suppliers",
		"get_price_history",
		"get_supplier_quotations",
		"score_vendors",
		"detect_price_anomalies",
		"create_draft_rfq",
		*MASTER_DATA_TOOLS,
	],
	"instructions": (
		"You help buyers decide whether and how to source a material.\n"
		"1. Extract item, quantity, UOM, warehouse and need-by date from the request.\n"
		"2. Never compute stock or shortage yourself; use the numbers returned by tools.\n"
		"3. Only consider suppliers returned by get_approved_suppliers.\n"
		"4. Explain every recommendation with the evidence you used.\n"
		"5. You cannot approve or submit documents. Propose; a human decides.\n"
		"6. When an item or supplier is missing, offer to create it; never create one the buyer has not confirmed.\n"
		"7. Talk to the buyer in short, friendly, plain sentences, without internal terms."
	),
	"output_schema": _obj(
		{
			"shortage_qty": NUM,
			"recommended_action": {"type": "string", "enum": ["no_purchase", "create_rfq", "ask_buyer"]},
			"suppliers": _list(
				_obj({"supplier": STR, "reason": STR, "last_price": NUM, "lead_time_days": NUM, "score": NUM})
			),
			"recommended_supplier": STR,
			"estimated_value": NUM,
			"explanation": STR,
		}
	),
	"change_note": "Seeded by Agent Studio setup",
}

# Graph definitions. The LangGraph builder (Phase 4) compiles from these, and the Workflow
# Designer page renders them, so the picture and the runtime cannot drift apart.
# kind: llm | tool | rule | router | human ; "next" is a list of (condition, target) pairs.
WORKFLOWS: dict[str, dict] = {
	PROCUREMENT_WORKFLOW: {
		"name": "Procurement Sourcing",
		"version": "v2",
		"entry": "parse_requirement",
		"nodes": [
			{
				"id": "parse_requirement",
				"label": "Parse requirement",
				"kind": "llm",
				"desc": "The LLM reads the buyer's sentence and fills a structured form: item, quantity, unit, warehouse, need-by date.",
				"next": [["", "resolve_records"]],
			},
			{
				"id": "resolve_records",
				"label": "Resolve ERPNext records",
				"kind": "tool",
				"desc": "Looks up the real Item and Warehouse records so later steps work with exact codes, not guesses.",
				"tools": ["search_items", "get_warehouses"],
				"next": [["found", "validate_inputs"], ["new item", "propose_item"]],
			},
			{
				"id": "propose_item",
				"label": "Propose a new item",
				"kind": "llm",
				"desc": "The item is not in ERPNext. Looks for similar items and drafts a new Item (name, group, unit) for the buyer to confirm.",
				"tools": ["search_items"],
				"next": [["", "confirm_item"]],
			},
			{
				"id": "confirm_item",
				"label": "Buyer confirms the item",
				"kind": "human",
				"desc": "Asks the buyer to create the drafted item, pick a similar existing one, or change the details.",
				"next": [
					["create", "create_item"],
					["use existing", "resolve_records"],
					["change", "confirm_item"],
					["stop", "end_conversation"],
				],
			},
			{
				"id": "create_item",
				"label": "Create the item",
				"kind": "tool",
				"desc": "Creates the confirmed Item, recording that the assistant created it for the buyer.",
				"tools": ["create_item"],
				"next": [["", "resolve_records"]],
			},
			{
				"id": "validate_inputs",
				"label": "Validate inputs & permissions",
				"kind": "rule",
				"desc": "Plain code checks that every required field exists and that the user may purchase for this company and warehouse.",
				"next": [["valid", "read_supply"], ["missing data", "ask_buyer"]],
			},
			{
				"id": "read_supply",
				"label": "Read stock & open supply",
				"kind": "tool",
				"desc": "Reads current stock (Bin) and open Purchase Orders that will arrive before the need-by date.",
				"tools": ["get_stock_balance", "get_open_purchase_orders"],
				"next": [["", "calc_shortage"]],
			},
			{
				"id": "calc_shortage",
				"label": "Calculate net shortage",
				"kind": "rule",
				"desc": "Required − stock − usable open orders. Done in Python, never by the LLM.",
				"next": [["", "shortage_router"]],
			},
			{
				"id": "shortage_router",
				"label": "Shortage exists?",
				"kind": "router",
				"desc": "A conditional edge: chooses the next node based on the calculated shortage.",
				"next": [["no", "explain_no_purchase"], ["yes", "find_suppliers"]],
			},
			{
				"id": "explain_no_purchase",
				"label": "Explain: no purchase needed",
				"kind": "llm",
				"desc": "Writes a short explanation showing that existing stock and orders already cover the need.",
				"next": [["", "END"]],
			},
			{
				"id": "find_suppliers",
				"label": "Find eligible suppliers",
				"kind": "tool",
				"desc": "Gets approved suppliers for the item and scores them using the existing vendor scoring engine.",
				"tools": ["get_approved_suppliers", "score_vendors"],
				"next": [
					["enough data", "analyze_sourcing"],
					["no supplier", "confirm_supplier"],
					["not enough", "ask_buyer"],
				],
			},
			{
				"id": "confirm_supplier",
				"label": "Buyer chooses suppliers",
				"kind": "human",
				"desc": "Asks the buyer which supplier to use. Existing suppliers are matched by name; new ones are created only after the buyer confirms.",
				"next": [
					["ready", "setup_suppliers"],
					["again", "confirm_supplier"],
					["stop", "end_conversation"],
				],
			},
			{
				"id": "setup_suppliers",
				"label": "Create & link suppliers",
				"kind": "tool",
				"desc": "Creates any new suppliers the buyer confirmed and adds them to the item's supplier list.",
				"tools": ["create_supplier", "link_item_supplier"],
				"next": [["", "find_suppliers"]],
			},
			{
				"id": "end_conversation",
				"label": "Stop at buyer's request",
				"kind": "rule",
				"desc": "The buyer chose not to continue. Nothing more is created.",
				"next": [["", "END"]],
			},
			{
				"id": "ask_buyer",
				"label": "Ask buyer for missing info",
				"kind": "human",
				"desc": "Pauses the run and asks the buyer a question. The run resumes from here when they answer.",
				"next": [["answered", "resolve_records"]],
			},
			{
				"id": "analyze_sourcing",
				"label": "Analyze sourcing options",
				"kind": "llm",
				"desc": "Compares price history, open quotations and price anomalies, then weighs price against lead time and reliability.",
				"tools": ["get_price_history", "get_supplier_quotations", "detect_price_anomalies"],
				"next": [["", "check_limits"]],
			},
			{
				"id": "check_limits",
				"label": "Check value limits",
				"kind": "rule",
				"desc": "Estimates the order value and applies the money limits before any recommendation is prepared.",
				"next": [["within limits", "prepare_recommendation"], ["above ceiling", "explain_blocked"]],
			},
			{
				"id": "explain_blocked",
				"label": "Explain: blocked by policy",
				"kind": "llm",
				"desc": "Explains which limit stopped the run so the buyer can raise it through the normal process.",
				"next": [["", "END"]],
			},
			{
				"id": "prepare_recommendation",
				"label": "Prepare recommendation",
				"kind": "llm",
				"desc": "Produces the structured recommendation (output schema) with evidence and alternatives.",
				"next": [["", "human_review"]],
			},
			{
				"id": "human_review",
				"label": "Human review",
				"kind": "human",
				"desc": "Interrupt: the run is saved (checkpoint) and appears in the Approval Inbox. Nothing is written to ERPNext yet.",
				"next": [["approved", "revalidate"], ["rejected", "record_rejection"]],
			},
			{
				"id": "record_rejection",
				"label": "Record rejection",
				"kind": "rule",
				"desc": "Stores who rejected and why, so the agent can be improved later.",
				"next": [["", "END"]],
			},
			{
				"id": "revalidate",
				"label": "Re-validate policies & records",
				"kind": "rule",
				"desc": "Data may have changed while waiting. Re-checks stock, prices, limits and the approver's permission.",
				"next": [["pass", "create_draft"], ["fail", "human_review"]],
			},
			{
				"id": "create_draft",
				"label": "Create draft RFQ",
				"kind": "tool",
				"desc": "Creates a Request for Quotation in Draft status. It is never submitted by the agent.",
				"tools": ["create_draft_rfq"],
				"next": [["", "verify_audit"]],
			},
			{
				"id": "verify_audit",
				"label": "Verify result & audit",
				"kind": "rule",
				"desc": "Reads the created document back, confirms it matches the approved proposal, and writes the audit event.",
				"next": [["", "END"]],
			},
		],
	},
}
