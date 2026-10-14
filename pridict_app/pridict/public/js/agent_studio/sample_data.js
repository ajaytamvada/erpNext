// Agent Studio sample data.
// Every page in Agent Studio renders from this file until the backend DocTypes and
// LangGraph runtime exist. All records describe one consistent scenario: a buyer asks
// the Procurement Sourcing Agent to source 500 kg of aluminium sheet by 30 October.
(() => {
	const namespace = (window.pridict = window.pridict || {});
	namespace.agentStudio = namespace.agentStudio || {};

	namespace.agentStudio.sampleData = {
		scenario: {
			request: "Source 500 kg of aluminium sheet (2 mm, 5052) for Stores - PRD by 30 October.",
			item_code: "ALU-SHEET-2MM",
			item_name: "Aluminium Sheet 2mm (5052)",
			uom: "Kg",
			warehouse: "Stores - PRD",
			company: "Pridict Manufacturing Pvt Ltd",
			required_qty: 500,
			need_by: "2026-10-30",
			stock_qty: 100,
			open_po: { name: "PUR-ORD-2026-00118", supplier: "Hindalco Distribution", qty: 150, schedule_date: "2026-10-24" },
			net_shortage: 250,
			avg_price_90d: 262,
		},

		providers: [
			{ name: "Anthropic", kind: "anthropic", endpoint: "https://api.anthropic.com", credential: "secret://pridict/anthropic_api_key", status: "Connected", latency_ms: 820, models: 2 },
			{ name: "OpenAI", kind: "openai", endpoint: "https://api.openai.com/v1", credential: "secret://pridict/openai_api_key", status: "Connected", latency_ms: 760, models: 1 },
			{ name: "Google", kind: "google", endpoint: "https://generativelanguage.googleapis.com", credential: "secret://pridict/google_api_key", status: "Not configured", latency_ms: null, models: 0 },
			{ name: "On-premise (OpenAI-compatible)", kind: "custom", endpoint: "http://llm-gateway.internal:8000/v1", credential: "secret://pridict/internal_gateway_token", status: "Connected", latency_ms: 1430, models: 1 },
		],

		modelConfigs: [
			{ name: "procurement-reasoning", provider: "Anthropic", model_id: "claude-sonnet-5-5", temperature: 0.1, max_tokens: 4096, timeout_s: 60, retries: 2, fallback: "procurement-fallback", status: "Active", used_by: 1 },
			{ name: "procurement-fallback", provider: "OpenAI", model_id: "gpt-4.1-mini", temperature: 0.1, max_tokens: 4096, timeout_s: 60, retries: 1, fallback: "", status: "Active", used_by: 0 },
			{ name: "fast-extraction", provider: "Anthropic", model_id: "claude-haiku-5-5", temperature: 0, max_tokens: 1024, timeout_s: 20, retries: 2, fallback: "", status: "Active", used_by: 1 },
			{ name: "private-data-local", provider: "On-premise (OpenAI-compatible)", model_id: "llama-3.1-70b-instruct", temperature: 0.2, max_tokens: 2048, timeout_s: 90, retries: 1, fallback: "", status: "Testing", used_by: 0 },
		],

		agents: [
			{
				name: "Procurement Sourcing Agent",
				module: "Procurement",
				type: "Bounded agent",
				status: "Active",
				version: "v1.2",
				owner: "purchase.manager@pridict.local",
				model_config: "procurement-reasoning",
				mode: "recommend",
				temperature: 0.1,
				max_steps: 8,
				max_runtime_s: 180,
				token_budget: 40000,
				approval_required: true,
				tools: ["search_items", "get_warehouses", "get_stock_balance", "get_open_purchase_orders", "get_approved_suppliers", "get_price_history", "get_supplier_quotations", "score_vendors", "detect_price_anomalies", "create_draft_rfq"],
				instructions:
					"You help buyers decide whether and how to source a material.\n" +
					"1. Extract item, quantity, UOM, warehouse and need-by date from the request.\n" +
					"2. Never compute stock or shortage yourself; use the numbers returned by tools.\n" +
					"3. Only consider suppliers returned by get_approved_suppliers.\n" +
					"4. Explain every recommendation with the evidence you used.\n" +
					"5. You cannot approve or submit documents. Propose; a human decides.",
				output_schema: {
					shortage_qty: "number (from calc_shortage)",
					recommended_action: "'no_purchase' | 'create_rfq' | 'ask_buyer'",
					suppliers: "[{ supplier, reason, last_price, lead_time_days, score }]",
					recommended_supplier: "string",
					estimated_value: "number",
					explanation: "string (plain language)",
				},
				history: [
					{ version: "v1.2", date: "2026-10-08", author: "purchase.manager@pridict.local", note: "Added detect_price_anomalies tool; lowered temperature 0.2 -> 0.1" },
					{ version: "v1.1", date: "2026-10-01", author: "purchase.manager@pridict.local", note: "Step limit 12 -> 8 after evaluation runs" },
					{ version: "v1.0", date: "2026-09-24", author: "admin@pridict.local", note: "First published version (read-only mode)" },
				],
			},
			{ name: "Invoice Matching Agent", module: "Finance", type: "Bounded agent", status: "Draft", version: "v0.3", owner: "accounts.manager@pridict.local", model_config: "fast-extraction", mode: "readonly", max_steps: 6, approval_required: true, tools: [] },
			{ name: "Supplier Onboarding Assistant", module: "Procurement", type: "Assistant", status: "Planned", version: "-", owner: "purchase.manager@pridict.local", model_config: "-", mode: "readonly", max_steps: 4, approval_required: true, tools: [] },
		],

		// kind: llm | tool | rule | router | human | end
		workflow: {
			name: "Procurement Sourcing",
			version: "v1.2 (published)",
			nodes: [
				{ id: "parse_requirement", label: "Parse requirement", kind: "llm", desc: "The LLM reads the buyer's sentence and fills a structured form: item, quantity, unit, warehouse, need-by date.", next: [["", "resolve_records"]] },
				{ id: "resolve_records", label: "Resolve ERPNext records", kind: "tool", desc: "Looks up the real Item and Warehouse records so later steps work with exact codes, not guesses.", tools: ["search_items", "get_warehouses"], next: [["", "validate_inputs"]] },
				{ id: "validate_inputs", label: "Validate inputs & permissions", kind: "rule", desc: "Plain code checks that every required field exists and that the user may purchase for this company and warehouse.", next: [["valid", "read_supply"], ["missing data", "ask_buyer"]] },
				{ id: "read_supply", label: "Read stock & open supply", kind: "tool", desc: "Reads current stock (Bin) and open Purchase Orders that will arrive before the need-by date.", tools: ["get_stock_balance", "get_open_purchase_orders"], next: [["", "calc_shortage"]] },
				{ id: "calc_shortage", label: "Calculate net shortage", kind: "rule", desc: "Required − stock − usable open orders. Done in Python, never by the LLM.", next: [["", "shortage_router"]] },
				{ id: "shortage_router", label: "Shortage exists?", kind: "router", desc: "A conditional edge: chooses the next node based on the calculated shortage.", next: [["no", "explain_no_purchase"], ["yes", "find_suppliers"]] },
				{ id: "explain_no_purchase", label: "Explain: no purchase needed", kind: "llm", desc: "Writes a short explanation showing that existing stock and orders already cover the need.", next: [["", "END"]] },
				{ id: "find_suppliers", label: "Find eligible suppliers", kind: "tool", desc: "Gets approved suppliers for the item and scores them using the existing vendor scoring engine.", tools: ["get_approved_suppliers", "score_vendors"], next: [["enough data", "analyze_sourcing"], ["not enough", "ask_buyer"]] },
				{ id: "ask_buyer", label: "Ask buyer for missing info", kind: "human", desc: "Pauses the run and asks the buyer a question. The run resumes from here when they answer.", next: [["answered", "resolve_records"]] },
				{ id: "analyze_sourcing", label: "Analyze sourcing options", kind: "llm", desc: "Compares price history, open quotations and price anomalies, then weighs price against lead time and reliability.", tools: ["get_price_history", "get_supplier_quotations", "detect_price_anomalies"], next: [["", "prepare_recommendation"]] },
				{ id: "prepare_recommendation", label: "Prepare recommendation", kind: "llm", desc: "Produces the structured recommendation (output schema) with evidence and alternatives.", next: [["", "human_review"]] },
				{ id: "human_review", label: "Human review", kind: "human", desc: "Interrupt: the run is saved (checkpoint) and appears in the Approval Inbox. Nothing is written to ERPNext yet.", next: [["approved", "revalidate"], ["rejected", "record_rejection"]] },
				{ id: "record_rejection", label: "Record rejection", kind: "rule", desc: "Stores who rejected and why, so the agent can be improved later.", next: [["", "END"]] },
				{ id: "revalidate", label: "Re-validate policies & records", kind: "rule", desc: "Data may have changed while waiting. Re-checks stock, prices, limits and the approver's permission.", next: [["pass", "create_draft"], ["fail", "human_review"]] },
				{ id: "create_draft", label: "Create draft RFQ", kind: "tool", desc: "Creates a Request for Quotation in Draft status. It is never submitted by the agent.", tools: ["create_draft_rfq"], next: [["", "verify_audit"]] },
				{ id: "verify_audit", label: "Verify result & audit", kind: "rule", desc: "Reads the created document back, confirms it matches the approved proposal, and writes the audit event.", next: [["", "END"]] },
			],
		},

		tools: [
			{ name: "search_items", access: "Read", target: "Item", scope: "Item: read", timeout_s: 5, calls_7d: 46, error_pct: 0, status: "Enabled",
				input: { query: "string", limit: "int (max 10)" }, output: { items: "[{ item_code, item_name, stock_uom, item_group }]" } },
			{ name: "get_warehouses", access: "Read", target: "Warehouse", scope: "Warehouse: read (company-filtered)", timeout_s: 5, calls_7d: 44, error_pct: 0, status: "Enabled",
				input: { company: "string" }, output: { warehouses: "[{ name, is_group }]" } },
			{ name: "get_stock_balance", access: "Read", target: "Bin", scope: "Bin: read", timeout_s: 5, calls_7d: 41, error_pct: 0, status: "Enabled",
				input: { item_code: "string", warehouse: "string" }, output: { actual_qty: "number", reserved_qty: "number", projected_qty: "number" } },
			{ name: "get_open_purchase_orders", access: "Read", target: "Purchase Order", scope: "Purchase Order: read", timeout_s: 8, calls_7d: 41, error_pct: 2.4, status: "Enabled",
				input: { item_code: "string", warehouse: "string", before_date: "date" }, output: { orders: "[{ name, supplier, pending_qty, schedule_date }]" } },
			{ name: "get_approved_suppliers", access: "Read", target: "Supplier, Item Supplier", scope: "Supplier: read", timeout_s: 5, calls_7d: 33, error_pct: 0, status: "Enabled",
				input: { item_code: "string" }, output: { suppliers: "[{ supplier, on_hold, lead_time_days }]" } },
			{ name: "get_price_history", access: "Read", target: "Purchase Order Item", scope: "Purchase Order: read", timeout_s: 8, calls_7d: 31, error_pct: 0, status: "Enabled",
				input: { item_code: "string", days: "int (max 365)" }, output: { prices: "[{ supplier, rate, date }]", avg_rate: "number" } },
			{ name: "get_supplier_quotations", access: "Read", target: "Supplier Quotation", scope: "Supplier Quotation: read", timeout_s: 8, calls_7d: 29, error_pct: 0, status: "Enabled",
				input: { item_code: "string", valid_on: "date" }, output: { quotations: "[{ name, supplier, rate, valid_till }]" } },
			{ name: "score_vendors", access: "Read", target: "pridict.decision_intelligence.vendor_scoring", scope: "Purchase Order: read", timeout_s: 10, calls_7d: 33, error_pct: 0, status: "Enabled",
				input: { suppliers: "[string]" }, output: { scores: "[{ supplier, score, tier }]" } },
			{ name: "detect_price_anomalies", access: "Read", target: "pridict.decision_intelligence.anomaly_detector", scope: "Purchase Order: read", timeout_s: 10, calls_7d: 29, error_pct: 0, status: "Enabled",
				input: { item_code: "string", proposed_rate: "number" }, output: { anomalies: "[{ title, severity, variance_pct }]" } },
			{ name: "create_draft_rfq", access: "Write (draft)", target: "Request for Quotation", scope: "RFQ: create (docstatus 0 only)", timeout_s: 15, calls_7d: 9, error_pct: 0, status: "Approval required",
				input: { item_code: "string", qty: "number", schedule_date: "date", suppliers: "[string]", approval_id: "string" }, output: { rfq: "string (document name)" } },
			{ name: "create_draft_purchase_order", access: "Write (draft)", target: "Purchase Order", scope: "Purchase Order: create (docstatus 0 only)", timeout_s: 15, calls_7d: 0, error_pct: 0, status: "Disabled",
				input: { supplier: "string", items: "[{ item_code, qty, rate }]", approval_id: "string" }, output: { purchase_order: "string" } },
			{ name: "submit_purchase_order", access: "Write (submit)", target: "Purchase Order", scope: "Purchase Order: submit", timeout_s: 15, calls_7d: 0, error_pct: 0, status: "Blocked for agents",
				input: { purchase_order: "string" }, output: { status: "string" } },
		],

		policies: [
			{ group: "Suppliers", rules: [
				{ name: "Approved suppliers only", value: "Supplier must be listed in Item Supplier and not on hold", severity: "Block" },
				{ name: "Minimum vendor score", value: "Score ≥ 60 (from vendor scoring engine)", severity: "Block" },
				{ name: "Watchlist suppliers", value: "Allowed, but flagged to the approver", severity: "Warn" },
			] },
			{ group: "Scope", rules: [
				{ name: "Permitted companies", value: "Pridict Manufacturing Pvt Ltd", severity: "Block" },
				{ name: "Permitted warehouses", value: "Stores - PRD, Raw Material - PRD", severity: "Block" },
			] },
			{ group: "Data requirements", rules: [
				{ name: "Required fields", value: "Item, quantity, UOM, warehouse, need-by date", severity: "Ask buyer" },
				{ name: "Need-by date", value: "Must be today or later", severity: "Ask buyer" },
			] },
			{ group: "Money & quantity limits", rules: [
				{ name: "Single approver limit", value: "Estimated value ≤ ₹5,00,000 → Purchase Manager", severity: "Approval" },
				{ name: "Dual approval", value: "₹5,00,000 – ₹25,00,000 → Purchase Manager + Finance Manager", severity: "Approval" },
				{ name: "Hard ceiling", value: "Above ₹25,00,000 → agent may not prepare the document", severity: "Block" },
				{ name: "Price variance tolerance", value: "±10% vs 90-day average rate", severity: "Warn" },
				{ name: "Quantity sanity check", value: "≤ 3× average monthly consumption", severity: "Warn" },
			] },
			{ group: "Prohibited for agents", rules: [
				{ name: "Submit or cancel documents", value: "Agents can only create drafts (docstatus 0)", severity: "Block" },
				{ name: "Change master data", value: "No edits to Supplier, Item, Price List", severity: "Block" },
				{ name: "Self-approval", value: "Agent cannot approve its own proposal", severity: "Block" },
			] },
		],

		policyCheck: [
			{ rule: "Approved suppliers only", result: "PASS", detail: "3 of 4 candidate suppliers approved; Coastal Alloys excluded (not in Item Supplier)" },
			{ rule: "Minimum vendor score", result: "PASS", detail: "Lowest included score: 64 (Shree Aluminium Traders)" },
			{ rule: "Watchlist suppliers", result: "WARN", detail: "Shree Aluminium Traders is on watchlist (2 late deliveries in 90 days)" },
			{ rule: "Single approver limit", result: "PASS", detail: "Estimated ₹64,500 ≤ ₹5,00,000 → one Purchase Manager approval" },
			{ rule: "Price variance tolerance", result: "PASS", detail: "Recommended ₹258/kg is −1.5% vs 90-day average ₹262/kg" },
			{ rule: "Quantity sanity check", result: "PASS", detail: "250 kg ≤ 3 × 180 kg monthly consumption" },
			{ rule: "Submit or cancel documents", result: "PASS", detail: "Proposed action creates a Draft RFQ only" },
		],

		suppliers: [
			{ supplier: "Bharat Metals & Alloys", score: 78, tier: "Preferred", last_price: 258, quote: "SQ-2026-00031 @ ₹255 (valid till 2026-10-20)", lead_time_days: 10, note: "Best price/score balance" },
			{ supplier: "Hindalco Distribution", score: 86, tier: "Preferred", last_price: 265, quote: "-", lead_time_days: 7, note: "Most reliable, already supplying open PO" },
			{ supplier: "Shree Aluminium Traders", score: 64, tier: "Watchlist", last_price: 249, quote: "-", lead_time_days: 14, note: "Cheapest, but 2 late deliveries" },
		],

		runs: [
			{ name: "RUN-2026-0042", workflow: "Procurement Sourcing v1.2", user: "buyer1@pridict.local", started: "2026-10-13 10:42", duration_s: 23.8, status: "Awaiting approval", tokens: 18420, cost_usd: 0.071, outcome: "Recommend RFQ to 3 suppliers for 250 kg" },
			{ name: "RUN-2026-0041", workflow: "Procurement Sourcing v1.2", user: "buyer2@pridict.local", started: "2026-10-13 09:15", duration_s: 9.1, status: "Completed", tokens: 6230, cost_usd: 0.022, outcome: "No purchase needed (stock covers demand)" },
			{ name: "RUN-2026-0040", workflow: "Procurement Sourcing v1.2", user: "buyer1@pridict.local", started: "2026-10-12 16:03", duration_s: 31.2, status: "Completed", tokens: 21010, cost_usd: 0.083, outcome: "Draft RFQ PUR-RFQ-2026-00027 created" },
			{ name: "RUN-2026-0039", workflow: "Procurement Sourcing v1.2", user: "buyer3@pridict.local", started: "2026-10-12 11:47", duration_s: 4.2, status: "Waiting for buyer", tokens: 2950, cost_usd: 0.009, outcome: "Asked: which warehouse?" },
			{ name: "RUN-2026-0038", workflow: "Procurement Sourcing v1.1", user: "buyer2@pridict.local", started: "2026-10-11 14:30", duration_s: 27.5, status: "Rejected", tokens: 19880, cost_usd: 0.077, outcome: "Approver rejected: supplier on watchlist" },
			{ name: "RUN-2026-0037", workflow: "Procurement Sourcing v1.1", user: "buyer1@pridict.local", started: "2026-10-11 10:02", duration_s: 60.0, status: "Failed", tokens: 8100, cost_usd: 0.031, outcome: "Timeout in get_open_purchase_orders (retried 2×)" },
		],

		trace: [
			{ node: "parse_requirement", kind: "llm", ms: 1840, tokens: 1210, summary: "Extracted { item: 'aluminium sheet 2mm 5052', qty: 500, uom: 'Kg', warehouse: 'Stores - PRD', need_by: '2026-10-30' }" },
			{ node: "resolve_records", kind: "tool", ms: 310, tokens: 0, summary: "search_items → ALU-SHEET-2MM; get_warehouses → Stores - PRD ✓" },
			{ node: "validate_inputs", kind: "rule", ms: 12, tokens: 0, summary: "All required fields present; buyer1 may purchase for Pridict Manufacturing Pvt Ltd ✓" },
			{ node: "read_supply", kind: "tool", ms: 420, tokens: 0, summary: "get_stock_balance → 100 Kg; get_open_purchase_orders → PUR-ORD-2026-00118 (150 Kg, due 2026-10-24)" },
			{ node: "calc_shortage", kind: "rule", ms: 3, tokens: 0, summary: "500 − 100 − 150 = 250 Kg shortage" },
			{ node: "shortage_router", kind: "router", ms: 1, tokens: 0, summary: "shortage > 0 → find_suppliers" },
			{ node: "find_suppliers", kind: "tool", ms: 690, tokens: 0, summary: "4 candidates; 3 approved (Coastal Alloys excluded); scores 86 / 78 / 64" },
			{ node: "analyze_sourcing", kind: "llm", ms: 9800, tokens: 11240, summary: "Compared 90-day prices (avg ₹262/kg), 1 valid quotation, no price anomalies" },
			{ node: "prepare_recommendation", kind: "llm", ms: 10400, tokens: 5970, summary: "Recommend RFQ to all 3; preferred: Bharat Metals & Alloys (₹258/kg, 10 days)" },
			{ node: "human_review", kind: "human", ms: 0, tokens: 0, summary: "Checkpoint saved. Interrupt raised → APR-2026-0019 in Approval Inbox" },
		],

		evaluations: [
			{ case: "Shortage exists (500 need, 100 stock, 150 on order)", expected: "Shortage 250, RFQ recommended, waits for approval", result: "PASS" },
			{ case: "No shortage (stock 600)", expected: "Explains no purchase needed; no approval request", result: "PASS" },
			{ case: "Open PO arrives after need-by date", expected: "Open PO ignored; shortage 400", result: "PASS" },
			{ case: "No eligible supplier", expected: "Asks buyer; does not invent a supplier", result: "PASS" },
			{ case: "Price 25% above average", expected: "Price variance warning shown to approver", result: "PASS" },
			{ case: "Missing warehouse in request", expected: "Asks buyer which warehouse", result: "PASS" },
			{ case: "Approver rejects", expected: "Run ends; no document created; reason stored", result: "PASS" },
			{ case: "Value above ₹25,00,000", expected: "Blocked; no draft prepared", result: "FAIL", note: "Agent prepared draft before ceiling check — fix: run limit check before prepare_recommendation" },
		],

		approvals: [
			{ name: "APR-2026-0019", run: "RUN-2026-0042", agent: "Procurement Sourcing Agent", requested_by: "buyer1@pridict.local", created: "2026-10-13 10:42", action: "Create Draft RFQ", value: 64500, risk: "Low", status: "Pending" },
			{ name: "APR-2026-0018", run: "RUN-2026-0036", agent: "Procurement Sourcing Agent", requested_by: "buyer2@pridict.local", created: "2026-10-10 15:20", action: "Create Draft RFQ", value: 412000, risk: "Medium", status: "Pending" },
			{ name: "APR-2026-0017", run: "RUN-2026-0038", agent: "Procurement Sourcing Agent", requested_by: "buyer2@pridict.local", created: "2026-10-11 14:31", action: "Create Draft RFQ", value: 98000, risk: "Medium", status: "Rejected" },
			{ name: "APR-2026-0016", run: "RUN-2026-0040", agent: "Procurement Sourcing Agent", requested_by: "buyer1@pridict.local", created: "2026-10-12 16:04", action: "Create Draft RFQ", value: 118500, risk: "Low", status: "Approved" },
		],
	};
})();
