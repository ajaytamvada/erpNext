// Shared building blocks for the Agent Studio pages.
(() => {
	const namespace = (window.pridict = window.pridict || {});
	const studio = (namespace.agentStudio = namespace.agentStudio || {});

	studio.pages = [
		{ route: "agent-models", label: "Models & Providers", icon: "fa-plug" },
		{ route: "agent-registry", label: "Agents", icon: "fa-user-circle" },
		{ route: "agent-workflows", label: "Workflow Designer", icon: "fa-sitemap" },
		{ route: "agent-tools", label: "Tools & Connectors", icon: "fa-wrench" },
		{ route: "agent-policies", label: "Policies & Guardrails", icon: "fa-shield" },
		{ route: "agent-runs", label: "Runs & Traces", icon: "fa-history" },
		{ route: "agent-approvals", label: "Approval Inbox", icon: "fa-check-square-o" },
	];

	studio.kindLabels = {
		llm: "LLM step",
		tool: "Tool call",
		rule: "Rule (code)",
		router: "Router",
		human: "Human pause",
		end: "End",
	};

	studio.escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	studio.t = (value) => studio.escape(__(value));

	studio.inr = (value) => {
		try {
			return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
		} catch (_) {
			return `INR ${Number(value || 0).toLocaleString()}`;
		}
	};

	const badgeClasses = {
		active: "as-badge-good", connected: "as-badge-good", enabled: "as-badge-good", completed: "as-badge-good", approved: "as-badge-good", pass: "as-badge-good", low: "as-badge-good",
		testing: "as-badge-warn", draft: "as-badge-warn", "awaiting approval": "as-badge-warn", "waiting for buyer": "as-badge-warn", pending: "as-badge-warn", warn: "as-badge-warn", medium: "as-badge-warn", "approval required": "as-badge-warn", approval: "as-badge-warn", "ask buyer": "as-badge-info",
		recommended: "as-badge-good", preferred: "as-badge-info", watchlist: "as-badge-warn", "changes requested": "as-badge-warn",
		read: "as-badge-info", "write (draft)": "as-badge-warn", "write (submit)": "as-badge-bad",
		queued: "as-badge-info", running: "as-badge-info", interrupted: "as-badge-warn", cancelled: "as-badge-muted", expired: "as-badge-muted", "not tested": "as-badge-muted",
		failed: "as-badge-bad", rejected: "as-badge-bad", fail: "as-badge-bad", block: "as-badge-bad", high: "as-badge-bad", "blocked for agents": "as-badge-bad",
	};

	studio.badge = (label) => {
		const cls = badgeClasses[String(label).toLowerCase()] || "as-badge-muted";
		return `<span class="as-badge ${cls}">${studio.t(label)}</span>`;
	};

	studio.kindBadge = (kind) => `<span class="as-kind as-kind-${studio.escape(kind)}">${studio.t(studio.kindLabels[kind] || kind)}</span>`;

	studio.metric = (title, value, sub = "") => `
		<div class="as-metric">
			<span class="as-metric-title">${studio.t(title)}</span>
			<span class="as-metric-value">${value}</span>
			${sub ? `<span class="as-metric-sub">${sub}</span>` : ""}
		</div>`;

	studio.json = (obj) => `<pre class="as-code">${studio.escape(JSON.stringify(obj, null, 2))}</pre>`;

	studio.call = (method, args = {}) => frappe.xcall(`pridict.agent_studio.api.${method}`, args);

	studio.empty = (title, detail = "") => `
		<div class="as-empty">
			<strong>${studio.t(title)}</strong>
			${detail ? `<p>${studio.t(detail)}</p>` : ""}
		</div>`;

	studio.datetime = (value) => (value ? frappe.datetime.str_to_user(value) : "—");

	// Elements with data-open-doctype (and optional data-open-name) open the standard
	// Desk form; without a name they start a new document.
	studio.formLink = (label, doctype, name = "", cls = "btn btn-default btn-sm") =>
		`<button type="button" class="${cls}" data-open-doctype="${studio.escape(doctype)}" data-open-name="${studio.escape(name)}">${studio.t(label)}</button>`;

	// Base class: builds the Frappe page and the Agent Studio sub-navigation, then loads
	// data from the server. Subclasses implement fetch() (returns the page data),
	// render() (returns HTML) and an optional bind(body) for event handlers.
	studio.StudioPage = class StudioPage {
		constructor(wrapper, { route, title, eyebrow, intro }) {
			this.route = route;
			this.data = null;
			this.page = frappe.ui.make_app_page({ parent: wrapper, title: __(title), single_column: true });
			const main = this.page.main.get ? this.page.main.get(0) : this.page.main;
			main.innerHTML = "";
			this.root = document.createElement("div");
			this.root.className = "as-screen";
			main.appendChild(this.root);
			this.header = `
				<header class="as-intro">
					<div>
						<span class="as-eyebrow">${studio.t(eyebrow)}</span>
						<h1>${studio.t(title)}</h1>
						<p>${studio.t(intro)}</p>
					</div>
				</header>
				<nav class="as-subnav" aria-label="${studio.t("Agent Studio sections")}">
					${studio.pages.map((p) => `
						<button type="button" class="as-subnav-link ${p.route === route ? "is-active" : ""}" data-route="${p.route}" ${p.route === route ? 'aria-current="page"' : ""}>
							<i class="fa ${p.icon}" aria-hidden="true"></i> ${studio.t(p.label)}
						</button>`).join("")}
				</nav>`;
			this.root.addEventListener("click", (event) => {
				const link = event.target.closest(".as-subnav-link[data-route]");
				if (link) frappe.set_route(link.dataset.route);
				const open = event.target.closest("[data-open-doctype]");
				if (open) {
					const { openDoctype, openName } = open.dataset;
					openName ? frappe.set_route("Form", openDoctype, openName) : frappe.new_doc(openDoctype);
				}
			});
			// Data changes while the user edits a form, so reload when they come back.
			$(wrapper).on("show", () => this.data && this.reload());
		}

		async reload() {
			if (!this.data) this.root.innerHTML = this.header + `<div class="as-body">${studio.empty("Loading…")}</div>`;
			try {
				this.data = await this.fetch();
			} catch (error) {
				console.error(error);
				this.root.innerHTML = this.header + `<div class="as-body">${studio.empty("Could not load this page.", "Check that you have access to Agent Studio, then reload.")}</div>`;
				return;
			}
			this.refresh();
		}

		refresh() {
			this.root.innerHTML = this.header + `<div class="as-body">${this.render()}</div>`;
			this.bind?.(this.root.querySelector(".as-body"));
		}

		notify(message, indicator = "blue") {
			frappe.show_alert({ message: __(message), indicator });
		}
	};
})();
