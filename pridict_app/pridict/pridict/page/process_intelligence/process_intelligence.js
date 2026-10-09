frappe.pages["process-intelligence"].on_page_load = async (wrapper) => {
	await frappe.require("/assets/pridict/css/process_intelligence.css");
	wrapper.process_intelligence = new PurchasingProcessIntelligence(wrapper);
};

frappe.pages["purchasing-analysis"] = {
	on_page_load: () => {
		frappe.set_route("process-intelligence");
	},
};

class PurchasingProcessIntelligence {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Process Intelligence"), single_column: true });
		this.$root = $('<div class="pi-screen"></div>').appendTo(this.page.main.empty());
		this.request = 0;
		this.journeyPage = 0;
		this.loadOptions();
	}

	escape(value) { return frappe.utils.escape_html(String(value ?? "")); }
	text(value) { return this.escape(__(value)); }
	human(value) { return this.escape(String(value || "Unknown").replaceAll("_", " ").toLowerCase()); }

	async loadOptions() {
		this.$root.html(`<p role="status">${this.text("Loading company access…")}</p>`);
		try {
			this.options = await frappe.xcall("pridict.process_intelligence.purchasing_screen.get_options");
			if (!this.options.companies.length) {
				this.$root.html(`<section class="pi-panel" role="status"><h2>${this.text("No company access")}</h2><p>${this.text("Ask your administrator for company and purchasing document read access.")}</p></section>`);
				return;
			}
			this.build();
		} catch (_) {
			this.$root.html(`<section class="pi-panel" role="alert"><h2>${this.text("Process Intelligence is unavailable")}</h2><p>${this.text("Sign in with the Process Analyst or System Manager role and company read access.")}</p><button class="btn btn-default pi-retry">${this.text("Retry")}</button></section>`);
			this.$root.find(".pi-retry").on("click", () => this.loadOptions());
		}
	}

	build() {
		const company = this.options.companies.includes(this.options.default_company) ? this.options.default_company : this.options.companies[0];
		this.$root.html(`
			<header class="pi-intro"><div><span class="pi-eyebrow">${this.text("Purchasing analysis")}</span><h1>${this.text("Follow the evidence behind each purchase")}</h1><p>${this.text("Explore recorded document relationships, current states and available history.")}</p></div><div class="d-flex align-items-center gap-2"><a href="/app/decision-intelligence" class="btn btn-default btn-sm"><i class="fa fa-gavel mr-1"></i> ${this.text("Decision Intelligence")}</a><span class="pi-badge">${this.text("Read-only analysis")}</span></div></header>
			<form class="pi-panel pi-filters" aria-label="${this.text("Analysis scope")}">
				<label>${this.text("Company")}<select name="company" required class="form-control">${this.options.companies.map((name) => `<option ${name === company ? "selected" : ""} value="${this.escape(name)}">${this.escape(name)}</option>`).join("")}</select></label>
				<label>${this.text("Created from")}<input name="start_date" type="date" required class="form-control" value="${this.options.today.slice(0, 7)}-01"></label>
				<label>${this.text("Created through")}<input name="end_date" type="date" required class="form-control" value="${this.options.today}"></label>
				<button class="btn btn-primary" type="submit">${this.text("Analyze purchasing")}</button>
				<p class="pi-filter-note">${this.text("Inclusive document creation dates")}, ${this.escape(this.options.timezone)}. ${this.text("Posting dates and completion dates are different.")} ${this.text("Up to")} ${this.options.record_limit} ${this.text("records per document or evidence type; only data you can read.")}</p>
			</form><div class="pi-results" aria-live="polite"></div>`);
		this.$results = this.$root.find(".pi-results");
		this.$root.find("form").on("submit", (event) => { event.preventDefault(); this.analyze(); });
		this.$root.find("form input, form select").on("change", () => {
			this.request++;
			this.data = null;
			this.showPrompt();
		});
		this.showPrompt();
	}

	showPrompt() {
		this.$results.html(`<section class="pi-panel pi-empty"><h2>${this.text("Choose a scope to begin")}</h2><p>${this.text("Run analysis to see observed facts, the purchasing graph and individual transaction journeys.")}</p></section>`);
	}

	async analyze() {
		const form = this.$root.find("form")[0];
		if (!form.reportValidity()) return;
		const args = Object.fromEntries(new FormData(form));
		if (args.start_date > args.end_date) {
			this.$results.html(`<p class="pi-notice" role="alert">${this.text("Created from must be on or before Created through.")}</p>`);
			return;
		}
		const request = ++this.request;
		this.data = null;
		this.$root.find("form :input").prop("disabled", true);
		this.$results.html(`<section class="pi-panel pi-empty" role="status"><h2>${this.text("Analyzing permitted purchasing records…")}</h2><p>${this.text("Collecting recorded links and available history.")}</p></section>`);
		try {
			const data = await frappe.xcall("pridict.process_intelligence.purchasing_screen.get_analysis", args);
			if (request !== this.request) return;
			this.data = data;
			this.selected = data.reconstruction.instances[0]?.instance_id;
			this.search = "";
			this.journeyPage = 0;
			this.render();
		} catch (_) {
			if (request === this.request) this.$results.html(`<section class="pi-panel" role="alert"><h2>${this.text("Analysis could not be loaded")}</h2><p>${this.text("Check your company access and date range, then run analysis again. No business records were changed.")}</p></section>`);
		} finally {
			this.$root.find("form :input").prop("disabled", false);
		}
	}

	documentLink(id) {
		const doc = this.data.documents[id];
		if (!doc) return `<span class="pi-unavailable">${this.text("Outside visible scope")}</span>`;
		return `<a href="${this.escape(doc.url)}" target="_blank" rel="noopener noreferrer" title="${this.text("Open supporting document in a new tab")}">${this.escape(doc.name)} <span aria-hidden="true">↗</span></a>`;
	}

	render() {
		const r = this.data.reconstruction;
		const m = r.metrics;
		const count = Object.values(m.document_volume).reduce((sum, value) => sum + value, 0);
		this.$results.html(`
			<div class="pi-result-heading"><h2>${this.text("Analysis results")}</h2><span>${this.escape(this.data.scope.company)} · ${this.escape(r.start_date)} — ${this.escape(r.end_date)}</span></div>
			<p class="pi-muted">${this.text("Observed at")} ${this.escape(r.collected_at)}. ${this.text("Counts describe visible records in this scope; they do not establish business completion.")}</p>
			<section aria-label="${this.text("Observed facts")}" class="pi-metrics">${[
				[count, "Documents observed"], [m.correlation_edge_count, "Explicit links"],
				[m.process_instance_count, "Transaction journeys"], [m.unlinked_document_count, "Documents without links"],
			].map(([value, label]) => `<div class="pi-panel"><span class="pi-eyebrow">${this.text("Observed fact")}</span><strong>${value}</strong><span>${this.text(label)}</span></div>`).join("")}</section>
			${!count ? `<section class="pi-panel pi-empty"><h2>${this.text("No visible purchasing documents in this scope")}</h2><p>${this.text("Try another creation-date range or company. A zero count does not prove that no purchasing activity exists outside your permissions or selected dates.")}</p></section>` : ""}
			<section class="pi-panel"><div class="pi-section-heading"><div><span class="pi-eyebrow">${this.text("Observed relationships")}</span><h2>${this.text("Purchasing process graph")}</h2></div><span class="pi-badge">${this.text("Arrows = explicit references")}</span></div><p class="pi-muted">${this.text("Nodes show document types and visible counts. Arrows follow stored references, not elapsed time or an assumed workflow. Zero means no document observed here.")}</p><div class="pi-graph" tabindex="0" aria-label="${this.text("Purchasing process graph; scroll horizontally on small screens")}">${this.graph()}</div><details><summary>${this.text("Read graph connections as a table")}</summary>${this.graphTable()}</details></section>
			<section class="pi-panel"><div class="pi-section-heading"><div><span class="pi-eyebrow">${this.text("Supporting evidence")}</span><h2>${this.text("Individual transaction journeys")}</h2></div><label class="pi-search-label">${this.text("Find document")}<input type="search" class="form-control pi-search" placeholder="${this.text("Document number or type")}"></label></div><p class="pi-muted">${this.text("A journey groups documents joined by explicit links. It does not certify a completed purchase or approval.")}</p><div class="pi-journeys"></div><div class="pi-journey-detail"></div></section>
			<div class="pi-evidence-grid"><section class="pi-panel pi-missing"><span class="pi-eyebrow">${this.text("Missing evidence / scope limits")}</span><h2>${this.text("What this analysis cannot establish")}</h2>${this.gaps()}</section>
			<section class="pi-panel"><span class="pi-eyebrow">${this.text("Unsupported metrics")}</span><h2>${this.text("Not available from this evidence")}</h2><dl class="pi-unsupported">${["Process cycle time", "Approval time", "Waiting time", "Handoff count"].map((label) => `<div><dt>${this.text(label)}</dt><dd>${this.text("Data not available")}</dd></div>`).join("")}</dl><p class="pi-muted">${this.text("Creation, modification and current status observations are not auditable completion or approval timestamps. These metrics are not calculated.")}</p></section></div>`);
		this.$results.find(".pi-search").on("input", (event) => {
			this.search = event.target.value.toLowerCase(); this.journeyPage = 0; this.renderJourneys();
		});
		this.renderJourneys();
	}

	stages() { return ["Material Request", "Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Payment Entry"]; }

	connections() {
		const groups = new Map();
		for (const edge of this.data.graph.edges) {
			const key = [edge.source_doctype, edge.target_doctype, edge.relation_type].join("|");
			const group = groups.get(key) || { ...edge, count: 0, boundary: 0 };
			group.count++;
			if (!edge.source_in_scope || !edge.target_in_scope) group.boundary++;
			groups.set(key, group);
		}
		return [...groups.values()];
	}

	graph() {
		const stages = this.stages();
		const volume = this.data.reconstruction.metrics.document_volume;
		const x = (type) => 84 + stages.indexOf(type) * 163;
		const paths = this.connections().map((edge) => {
			const a = x(edge.source_doctype), b = x(edge.target_doctype);
			const y = 170;
			const rise = 36 + Math.abs(b - a) * 0.14;
			const path = a === b ? `M ${a - 25},${y} C ${a - 90},65 ${a + 90},65 ${a + 25},${y}` : `M ${a + 24},${y} C ${a + 24},${y - rise} ${b - 24},${y - rise} ${b - 24},${y}`;
			return `<path d="${path}" class="pi-edge ${edge.boundary ? "pi-edge-boundary" : ""}" marker-end="url(#pi-arrow)"><title>${this.escape(edge.source_doctype)} → ${this.escape(edge.target_doctype)}: ${edge.count} ${this.human(edge.relation_type)}</title></path>`;
		}).join("");
		const nodes = stages.map((type) => {
			const words = type === "Request for Quotation" ? ["Request for", "Quotation"] : type.split(" ");
			return `<g class="${volume[type] ? "pi-node" : "pi-node pi-node-empty"}"><rect x="${x(type) - 72}" y="175" width="144" height="98" rx="12"/><text x="${x(type)}" y="199" class="pi-node-label">${this.text(words.slice(0, -1).join(" "))}</text><text x="${x(type)}" y="217" class="pi-node-label">${this.text(words.at(-1))}</text><text x="${x(type)}" y="254" class="pi-node-count">${volume[type] || 0}</text></g>`;
		}).join("");
		return `<svg viewBox="0 0 1140 292" role="img" aria-label="${this.text("Observed purchasing references; equivalent connections are listed in the table below")}"><defs><marker id="pi-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>${paths}${nodes}</svg>`;
	}

	graphTable() {
		const rows = this.connections();
		if (!rows.length) return `<p>${this.text("No explicit links observed.")}</p>`;
		return `<div class="pi-table-scroll"><table class="pi-table"><thead><tr><th>${this.text("Source")}</th><th>${this.text("Target")}</th><th>${this.text("Evidence")}</th><th>${this.text("Links")}</th><th>${this.text("Outside visible scope")}</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${this.text(row.source_doctype)}</td><td>${this.text(row.target_doctype)}</td><td>${this.human(row.relation_type)}</td><td>${row.count}</td><td>${row.boundary}</td></tr>`).join("")}</tbody></table></div>`;
	}

	gaps() {
		const r = this.data.reconstruction;
		const messages = [__("Records outside your company, creation dates or read permissions are excluded. Referenced documents outside this scope have no document link.")];
		if (this.data.scope.excluded_types.length) messages.push(__("No read access to: ") + this.data.scope.excluded_types.join(", "));
		const versions = r.events.filter((event) => event.event_type === "DOCUMENT_STATE_CHANGED").length;
		messages.push(versions ? __("Only recorded Version changes are shown; history may be incomplete.") : __("No visible Version state changes were found. Current states are observations, not transition history."));
		messages.push(...r.gaps.map((gap) => gap.replaceAll("DATA_NOT_AVAILABLE", "Data not available").replaceAll("_", " ")));
		return `<ul>${messages.map((message) => `<li>${this.escape(message)}</li>`).join("")}</ul>`;
	}

	renderJourneys() {
		const r = this.data.reconstruction;
		const matches = r.instances.filter((journey) => journey.document_ids.some((id) => {
			const doc = this.data.documents[id];
			return `${doc?.name} ${doc?.doctype}`.toLowerCase().includes(this.search);
		}));
		const pageSize = 10;
		this.journeyPage = Math.max(0, Math.min(this.journeyPage, Math.ceil(matches.length / pageSize) - 1));
		const page = matches.slice(this.journeyPage * pageSize, (this.journeyPage + 1) * pageSize);
		if (!page.some((item) => item.instance_id === this.selected)) this.selected = page[0]?.instance_id;
		this.$results.find(".pi-journeys").html(`${page.length ? `<div class="pi-journey-list">${page.map((item) => {
			const names = item.document_ids.map((id) => this.data.documents[id]?.name).filter(Boolean);
			return `<button type="button" class="pi-journey-button ${item.instance_id === this.selected ? "is-selected" : ""}" aria-pressed="${item.instance_id === this.selected}" data-journey="${item.instance_id}"><strong>${this.text("Journey")} ${r.instances.indexOf(item) + 1} · ${item.document_ids.length} ${this.text("documents")} · ${item.edge_ids.length} ${this.text("links")}</strong><span>${this.escape(names.join(" · "))}</span></button>`;
		}).join("")}</div>` : `<p>${this.text("No matching journeys.")}</p>`}<div class="pi-pagination"><button class="btn btn-default pi-prev" ${this.journeyPage === 0 ? "disabled" : ""}>${this.text("Previous")}</button><span>${matches.length ? this.journeyPage * pageSize + 1 : 0}–${Math.min((this.journeyPage + 1) * pageSize, matches.length)} / ${matches.length}</span><button class="btn btn-default pi-next" ${(this.journeyPage + 1) * pageSize >= matches.length ? "disabled" : ""}>${this.text("Next")}</button></div>`);
		this.$results.find("[data-journey]").on("click", (event) => {
			this.selected = event.currentTarget.dataset.journey;
			this.renderJourneys();
			this.$results.find('.pi-journey-button[aria-pressed="true"]')[0]?.focus();
		});
		this.$results.find(".pi-prev").on("click", () => this.changeJourneyPage(-1));
		this.$results.find(".pi-next").on("click", () => this.changeJourneyPage(1));
		this.renderJourney(matches.find((item) => item.instance_id === this.selected));
	}

	changeJourneyPage(direction) {
		this.journeyPage += direction;
		this.renderJourneys();
		const selector = direction > 0 ? ".pi-next:not(:disabled)" : ".pi-prev:not(:disabled)";
		const target = this.$results.find(selector)[0] || this.$results.find('.pi-journey-button[aria-pressed="true"]')[0];
		target?.focus();
	}

	renderJourney(journey) {
		const $detail = this.$results.find(".pi-journey-detail");
		if (!journey) { $detail.empty(); return; }
		const r = this.data.reconstruction;
		const ids = new Set(journey.document_ids);
		const events = r.events.filter((event) => ids.has(event.document_id));
		const created = events.filter((event) => event.event_type === "DOCUMENT_CREATED").sort((a, b) => String(a.occurred_at).localeCompare(String(b.occurred_at)));
		const edges = r.edges.filter((edge) => ids.has(edge.source_document_id) || ids.has(edge.target_document_id));
		$detail.html(`<div class="pi-section-heading"><h3>${this.text("Journey")} ${r.instances.indexOf(journey) + 1} — ${this.text("documents and evidence")}</h3><span class="pi-badge">${this.text("Business completion: unknown")}</span></div><p class="pi-muted">${this.text("Ordered by document creation. Open a document to inspect its items, references and native timeline.")}</p><ol class="pi-timeline">${created.map((event) => {
			const state = events.find((item) => item.document_id === event.document_id && item.event_type === "CURRENT_DOCUMENT_STATE_OBSERVED");
			return `<li><div><strong>${this.text(event.document_type)}</strong> ${this.documentLink(event.document_id)}</div><div class="pi-muted">${this.text("Created")} ${this.escape(event.occurred_at || "Unknown")} (${this.escape(this.data.scope.timezone)})</div><div>${this.text("Observed current state:")} ${this.escape(state?.details.status || ["Draft", "Submitted", "Cancelled"][state?.details.docstatus] || "Unknown")} <span class="pi-muted">· ${this.text("Docstatus")} ${state?.details.docstatus ?? "?"}</span></div></li>`;
		}).join("")}</ol><h4>${this.text("Stored document connections")}</h4>${edges.length ? `<div class="pi-table-scroll"><table class="pi-table"><thead><tr><th>${this.text("Source document")}</th><th>${this.text("Supporting document")}</th><th>${this.text("Recorded evidence")}</th></tr></thead><tbody>${edges.map((edge) => `<tr><td>${this.text(edge.source_doctype)}<br>${this.documentLink(edge.source_document_id)}</td><td>${this.text(edge.target_doctype)}<br>${this.documentLink(edge.target_document_id)}</td><td>${this.human(edge.relation_type)}${edge.quantity != null ? `<br>${this.text("Referenced quantity:")} ${edge.quantity}` : ""}${edge.allocated_amount != null ? `<br>${this.text("Payment allocation recorded; inspect payment for amount and currency.")}` : ""}<br><small>${edge.source_in_scope && edge.target_in_scope ? this.text("Both documents observed") : this.text("Evidence boundary: a document is outside visible scope")}</small></td></tr>`).join("")}</tbody></table></div>` : `<p>${this.text("No explicit document connections were found for this journey.")}</p>`}<details class="pi-history"><summary>${this.text("Available state-change and workflow evidence")}</summary>${this.history(events)}</details>`);
	}

	history(events) {
		const history = events.filter((event) => !["DOCUMENT_CREATED", "CURRENT_DOCUMENT_STATE_OBSERVED"].includes(event.event_type)).sort((a, b) => String(a.occurred_at).localeCompare(String(b.occurred_at)));
		if (!history.length) return `<p>${this.text("No visible historical state-change or workflow records were found. Approval and completion times remain unknown.")}</p>`;
		return `<ul>${history.map((event) => `<li>${this.documentLink(event.document_id)} · ${this.human(event.event_type)} · ${this.escape(event.occurred_at)}<br><span class="pi-muted">${this.escape(event.timestamp_semantics)}</span><br>${this.escape(JSON.stringify(event.details))}</li>`).join("")}</ul>`;
	}
}
