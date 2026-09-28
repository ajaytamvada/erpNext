(() => {
	const namespace = (window.pridict = window.pridict || {});
	const purchasingDoctypes = new Map([
		["material-request", "Material Request"],
		["purchase-order", "Purchase Order"],
		["purchase-receipt", "Purchase Receipt"],
		["purchase-invoice", "Purchase Invoice"],
	]);
	const workspaceModules = new Map([
		["home", "overview"],
		["pridict-home", "overview"],
		["pridict-procurement", "procurement"],
		["buying", "procurement"],
		["accounting", "finance"],
		["pridict-finance", "finance"],
		["financial-reports", "finance"],
		["payables", "finance"],
		["receivables", "finance"],
		["selling", "sales"],
		["crm", "sales"],
		["stock", "inventory"],
		["assets", "assets"],
		["manufacturing", "manufacturing"],
		["projects", "projects"],
		["quality", "quality"],
		["support", "support"],
		["website", "website"],
		["erpnext-settings", "administration"],
		["pridict-administration", "administration"],
		["users", "administration"],
		["tools", "administration"],
		["build", "administration"],
		["integrations", "integrations"],
		["erpnext-integrations", "integrations"],
		["pridict-integrations", "integrations"],
		["schema-intelligence", "governance"],
	]);
	const salesDoctypes = new Map([
		["lead", "Lead"],
		["opportunity", "Opportunity"],
		["quotation", "Quotation"],
		["sales-order", "Sales Order"],
		["delivery-note", "Delivery Note"],
		["sales-invoice", "Sales Invoice"],
	]);
	const inventoryDoctypes = new Map([
		["item", "Item"],
		["warehouse", "Warehouse"],
		["stock-entry", "Stock Entry"],
		["pick-list", "Pick List"],
		["stock-reconciliation", "Stock Reconciliation"],
		["serial-no", "Serial No"],
		["batch", "Batch"],
	]);
	const inventoryReports = new Set(["stock-balance", "stock-ledger", "stock-ageing", "stock-projected-qty"]);
	const assetDoctypes = new Map([
		["asset", "Asset"],
		["asset-category", "Asset Category"],
		["asset-movement", "Asset Movement"],
		["asset-repair", "Asset Repair"],
		["asset-maintenance", "Asset Maintenance"],
		["asset-depreciation-schedule", "Asset Depreciation Schedule"],
	]);
	const assetReports = new Set(["fixed-asset-register", "asset-activity", "asset-maintenance"]);
	const manufacturingDoctypes = new Map([["bom", "BOM"], ["production-plan", "Production Plan"], ["work-order", "Work Order"], ["job-card", "Job Card"], ["operation", "Operation"], ["workstation", "Workstation"]]);
	const manufacturingReports = new Set(["production-analytics", "production-planning-report", "work-order-summary", "job-card-summary", "bom-stock-report", "process-loss-report"]);
	const projectDoctypes = new Map([["project", "Project"], ["task", "Task"], ["timesheet", "Timesheet"], ["activity-type", "Activity Type"]]);
	const projectReports = new Set(["project-summary", "project-billing-summary", "delayed-tasks-summary", "daily-timesheet-summary", "employee-billing-summary", "project-wise-stock-tracking"]);
	const qualityDoctypes = new Map([["quality-inspection", "Quality Inspection"], ["quality-goal", "Quality Goal"], ["quality-review", "Quality Review"], ["quality-action", "Quality Action"], ["non-conformance", "Non Conformance"]]);
	const supportDoctypes = new Map([["issue", "Issue"], ["service-level-agreement", "Service Level Agreement"], ["warranty-claim", "Warranty Claim"]]);
	const supportReports = new Set(["issue-analytics", "issue-summary", "first-response-time-for-issues", "support-hour-distribution"]);
	const administrationDoctypes = new Map([
		["user", "User"], ["role", "Role"], ["role-profile", "Role Profile"], ["user-permission", "User Permission"],
		["workflow", "Workflow"], ["workflow-state", "Workflow State"], ["workflow-action", "Workflow Action"],
		["notification", "Notification"], ["email-account", "Email Account"], ["email-template", "Email Template"],
		["auto-email-report", "Auto Email Report"], ["data-import", "Data Import"], ["data-export", "Data Export"],
		["print-format", "Print Format"], ["print-settings", "Print Settings"], ["system-settings", "System Settings"],
		["global-defaults", "Global Defaults"], ["website-settings", "Website Settings"], ["employee", "Employee"],
	]);
	const integrationDoctypes = new Map([
		["webhook", "Webhook"], ["social-login-key", "Social Login Key"], ["ldap-settings", "LDAP Settings"],
		["oauth-client", "OAuth Client"], ["oauth-provider-settings", "OAuth Provider Settings"], ["sms-settings", "SMS Settings"],
		["slack-webhook-url", "Slack Webhook URL"], ["google-settings", "Google Settings"], ["google-contacts", "Google Contacts"],
		["google-calendar", "Google Calendar"], ["google-drive", "Google Drive"], ["dropbox-settings", "Dropbox Settings"],
		["s3-backup-settings", "S3 Backup Settings"], ["plaid-settings", "Plaid Settings"],
	]);
	const financeDoctypes = new Map([
		["payment-entry", "Payment Entry"],
		["journal-entry", "Journal Entry"],
		["account", "Account"],
		["cost-center", "Cost Center"],
	]);
	const financeReports = new Set([
		"profit-and-loss-statement",
		"balance-sheet",
		"cash-flow",
		"general-ledger",
		"accounts-receivable",
		"accounts-payable",
	]);

	function normalize(value) {
		return String(value || "")
			.trim()
			.toLowerCase()
			.replaceAll("_", "-")
			.replaceAll(" ", "-");
	}

	const secondaryDoctypeGroups = {
		finance: ["Accounting Dimension", "Accounting Period", "Accounts Settings", "Bank", "Bank Account", "Bank Clearance", "Bank Reconciliation Tool", "Budget", "Chart of Accounts Importer", "Company", "Cost Center Allocation", "Currency", "Currency Exchange", "Exchange Rate Revaluation", "Finance Book", "Fiscal Year", "Item Tax Template", "Journal Entry Template", "Lower Deduction Certificate", "Mode of Payment", "Monthly Distribution", "Opening Invoice Creation Tool", "Payment Term", "Period Closing Voucher", "Purchase Taxes and Charges Template", "Sales Taxes and Charges Template", "Share Transfer", "Shareholder", "Subscription", "Subscription Plan", "Subscription Settings", "Tax Category", "Tax Rule", "Tax Withholding Category", "Payment Reconciliation", "Dunning", "Dunning Type", "Payment Gateway Account", "Payment Request"],
		procurement: ["Import Supplier Invoice", "Request for Quotation", "Supplier", "Supplier Group", "Supplier Quotation", "Supplier Scorecard", "Supplier Scorecard Criteria", "Supplier Scorecard Standing", "Supplier Scorecard Variable"],
		sales: ["Address", "Appointment", "Blanket Order", "Campaign", "Communication", "Contact", "Contract", "Coupon Code", "CRM Settings", "Customer", "Customer Group", "Email Campaign", "Email Group", "Lead Source", "Loyalty Point Entry", "Loyalty Program", "Maintenance Schedule", "Maintenance Visit", "Newsletter", "POS Closing Entry", "POS Opening Entry", "POS Profile", "POS Settings", "Promotional Scheme", "Prospect", "Sales Partner", "Sales Person", "Sales Stage", "Selling Settings", "SMS Center", "SMS Log", "Terms and Conditions", "Territory"],
		inventory: ["Brand", "Customs Tariff Number", "Delivery Trip", "Installation Note", "Item Alternative", "Item Attribute", "Item Group", "Item Manufacturer", "Item Price", "Item Variant Settings", "Landed Cost Voucher", "Packing Slip", "Price List", "Pricing Rule", "Product Bundle", "Quality Inspection Template", "Quick Stock Balance", "Shipping Rule", "Stock Settings", "UOM", "UOM Conversion Factor"],
		assets: ["Asset Capitalization", "Asset Maintenance Log", "Asset Maintenance Team", "Asset Value Adjustment", "Location"],
		manufacturing: ["BOM Update Tool", "Downtime Entry", "Manufacturing Settings", "Routing", "Workstation Type"],
		projects: ["Activity Cost", "Project Template", "Project Type", "Project Update", "Projects Settings"],
		quality: ["Quality Feedback", "Quality Feedback Template", "Quality Meeting", "Quality Procedure"],
		support: ["Issue Priority", "Issue Type", "Support Settings"],
		administration: ["About Us Settings", "Bulk Update", "Buying Settings", "Contact Us Settings", "Deleted Document", "Domain Settings", "Email Domain", "Letter Head", "Notification Settings", "Print Style", "Website Script", "Website Theme"],
	};
	const secondaryReportGroups = {
		finance: ["Bank Reconciliation Statement", "Budget Variance Report", "Share Balance", "Share Ledger", "Consolidated Financial Statement", "Customer Credit Balance", "Customer Ledger Summary", "Gross Profit", "Item-wise Purchase Register", "Payment Period Based On Invoice Date", "Profitability Analysis", "Purchase Invoice Trends", "Purchase Register", "Sales Invoice Trends", "Sales Partners Commission", "Sales Payment Summary", "Supplier Ledger Summary", "Trial Balance", "Trial Balance for Party", "UAE VAT 201", "Accounts Payable Summary", "Accounts Receivable Summary"],
		procurement: ["Address And Contacts", "Item-wise Purchase History", "Items To Be Requested", "Material Requests for which Supplier Quotations are not created", "Procurement Tracker", "Purchase Analytics", "Purchase Order Analysis", "Purchase Order Trends", "Purchase Receipt Trends", "Received Items To Be Billed", "Requested Items to Order and Receive", "Subcontracted Item To Be Received", "Subcontracted Raw Materials To Be Transferred", "Supplier Quotation Comparison", "Supplier-Wise Sales Analytics"],
		sales: ["Campaign Efficiency", "Customer Acquisition and Loyalty", "Customers Without Any Sales Transactions", "Delivered Items To Be Billed", "Delivery Note Trends", "First Response Time for Opportunity", "Inactive Customers", "Item-wise Sales History", "Item-wise Sales Register", "Lead Details", "Lead Owner Efficiency", "Opportunity Summary by Sales Stage", "Pending SO Items For Purchase Request", "Prospects Engaged But Not Converted", "Quotation Trends", "Sales Analytics", "Sales Order Analysis", "Sales Order Trends", "Sales Partner Target Variance based on Item Group", "Sales Person Target Variance Based On Item Group", "Sales Person-wise Transaction Summary", "Sales Pipeline Analytics", "Sales Register", "Territory Target Variance Based On Item Group"],
		inventory: ["Available Stock for Packing Items", "Batch Item Expiry Status", "Batch-Wise Balance History", "Item Price Stock", "Item Prices", "Item Shortage Report", "Item Variant Details", "Itemwise Recommended Reorder Level", "Requested Items To Be Transferred", "Serial No Service Contract Expiry", "Serial No Status", "Serial No Warranty Expiry", "Stock Analytics", "Warehouse Wise Stock Balance"],
		assets: ["Asset Depreciation Ledger", "Asset Depreciations and Balances"],
		manufacturing: ["BOM Operations Time", "BOM Search", "Downtime Analysis", "Quality Inspection Summary", "Work Order Consumed Materials"],
	};
	const secondaryDoctypes = new Map(Object.entries(secondaryDoctypeGroups).flatMap(([module, names]) => names.map((name) => [normalize(name), { name, module }])));
	const secondaryReports = new Map(Object.entries(secondaryReportGroups).flatMap(([module, names]) => names.map((name) => [normalize(name), module])));
	const specialPages = new Map([["sales-funnel", "sales"], ["bom-comparison-tool", "manufacturing"], ["backups", "administration"], ["print-format-builder", "administration"]]);

	function getRouteParts() {
		const route = window.frappe?.get_route?.();
		if (Array.isArray(route) && route.length) {
			return route.map((part) => String(part || ""));
		}
		return window.location.pathname
			.replace(/^\/app\/?/, "")
			.split("/")
			.filter(Boolean)
			.map((part) => decodeURIComponent(part));
	}

	function getRouteSlug(parts) {
		if (!parts.length) {
			return "";
		}
		if (["List", "Form", "Tree"].includes(parts[0]) && parts[1]) {
			return normalize(parts[1]);
		}
		if (parts[0] === "query-report" && parts[1]) {
			return normalize(parts[1]);
		}
		return normalize(parts[0]);
	}

	function classify() {
		const parts = getRouteParts();
		const first = parts[0] || "";
		const slug = getRouteSlug(parts);
		const doctype = purchasingDoctypes.get(slug) || salesDoctypes.get(slug) || inventoryDoctypes.get(slug) || assetDoctypes.get(slug) || manufacturingDoctypes.get(slug) || projectDoctypes.get(slug) || qualityDoctypes.get(slug) || supportDoctypes.get(slug) || administrationDoctypes.get(slug) || integrationDoctypes.get(slug) || financeDoctypes.get(slug) || secondaryDoctypes.get(slug)?.name || (["List", "Form", "Tree"].includes(first) ? parts[1] : null);
		let surface = "page";
		if (first === "List") surface = "list";
		else if (first === "Form") surface = "form";
		else if (first === "Tree") surface = "tree";
		else if (first === "query-report" || first === "Report") surface = "report";
		else if (workspaceModules.has(slug) && !slug.startsWith("pridict-")) surface = "workspace";

		let module = workspaceModules.get(slug) || null;
		if (purchasingDoctypes.has(slug)) module = "procurement";
		if (salesDoctypes.has(slug)) module = "sales";
		if (inventoryDoctypes.has(slug) || inventoryReports.has(slug)) module = "inventory";
		if (assetDoctypes.has(slug) || assetReports.has(slug)) module = "assets";
		if (manufacturingDoctypes.has(slug) || manufacturingReports.has(slug)) module = "manufacturing";
		if (projectDoctypes.has(slug) || projectReports.has(slug)) module = "projects";
		if (qualityDoctypes.has(slug) || slug === "review") module = "quality";
		if (supportDoctypes.has(slug) || supportReports.has(slug)) module = "support";
		if (administrationDoctypes.has(slug)) module = "administration";
		if (integrationDoctypes.has(slug)) module = "integrations";
		if (financeDoctypes.has(slug) || financeReports.has(slug)) module = "finance";
		if (secondaryDoctypes.has(slug)) module = secondaryDoctypes.get(slug).module;
		if (secondaryReports.has(slug)) module = secondaryReports.get(slug);
		if (specialPages.has(slug)) module = specialPages.get(slug);
		if (!module && doctype && ["Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice"].includes(doctype)) {
			module = "procurement";
		}

		return {
			parts,
			slug,
			doctype,
			module: module || "overview",
			surface,
			isPurchasing: module === "procurement",
			isSales: module === "sales",
			isInventory: module === "inventory",
			isAssets: module === "assets",
			isManufacturing: module === "manufacturing",
			isProjects: module === "projects",
			isQuality: module === "quality",
			isSupport: module === "support",
			isAdministration: module === "administration",
			isIntegrations: module === "integrations",
			isFinance: module === "finance",
			view: parts[2] || null,
		};
	}

	function onRouteChange(callback) {
		let scheduled;
		const run = () => {
			window.clearTimeout(scheduled);
			scheduled = window.setTimeout(() => callback(classify()), 40);
		};
		window.addEventListener("popstate", run);
		window.addEventListener("hashchange", run);
		if (window.frappe?.router?.on) {
			window.frappe.router.on("change", run);
		}
		run();
		return run;
	}

	namespace.routeContext = { classify, normalize, onRouteChange, purchasingDoctypes, salesDoctypes, inventoryDoctypes, inventoryReports, assetDoctypes, assetReports, manufacturingDoctypes, manufacturingReports, projectDoctypes, projectReports, qualityDoctypes, supportDoctypes, supportReports, administrationDoctypes, integrationDoctypes, secondaryDoctypes, secondaryReports, specialPages, financeDoctypes, financeReports };
})();
