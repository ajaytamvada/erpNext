frappe.pages["schema-intelligence"].on_page_load = (wrapper) => {
	frappe.pridict_schema_intelligence = new PridictSchemaIntelligence(wrapper);
};

frappe.pages["schema-intelligence"].on_page_show = () => {
	frappe.pridict_schema_intelligence?.refresh();
};

class PridictSchemaIntelligence {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Schema Intelligence"),
			single_column: true,
		});
		this.snapshots = [];
		this.overview = null;
		this.detail = null;
		this.selectedSnapshotId = null;
		this.selectedDoctype = null;
		this.searchTerm = "";
		this.typeFilter = "all";
		this.isManager = frappe.user.has_role("System Manager");
		this.build();
	}

	build() {
		$(this.wrapper).addClass("pridict-schema-page");
		$(this.wrapper).find(".page-head").addClass("pridict-schema-page-head");
		this.$root = $('<div class="pridict-schema-intelligence" aria-live="polite"></div>').appendTo(
			this.page.main.empty()
		);
		if (this.isManager) {
			this.page.set_primary_action(__("Capture Snapshot"), () => this.captureSnapshot(), "camera");
			this.page.add_inner_button(__("Settings"), () => frappe.set_route("Form", "Schema Intelligence Settings"));
			this.page.add_inner_button(__("Manage Snapshot"), () => this.openSelectedSnapshot());
		}
		this.page.add_inner_button(__("Reviews"), () => frappe.set_route("List", "Schema Change Review"));
		this.page.add_inner_button(__("Create Review"), () => this.openCreateReview());
		this.page.add_inner_button(__("Compare Snapshots"), () => this.openComparison());
		this.renderLoading(__("Loading schema snapshots"));
	}

	async refresh(preferredSnapshotId = null) {
		this.renderLoading(__("Loading schema snapshots"));
		try {
			this.snapshots = await frappe.xcall("pridict.schema_intelligence.api.list_snapshots");
			if (!this.snapshots.length) {
				this.renderEmpty();
				return;
			}
			this.selectedSnapshotId =
				preferredSnapshotId ||
				this.selectedSnapshotId ||
				this.snapshots[0].snapshot_id;
			await this.loadOverview();
		} catch (error) {
			this.renderError(error);
		}
	}

	async loadOverview() {
		this.renderLoading(__("Loading snapshot details"));
		this.overview = await frappe.xcall(
			"pridict.schema_intelligence.api.get_snapshot_overview",
			{ snapshot_id: this.selectedSnapshotId }
		);
		this.selectedDoctype = this.pickSelectedDoctype();
		this.detail = null;
		this.render();
		if (this.selectedDoctype) {
			await this.loadDoctype(this.selectedDoctype);
		}
	}

	pickSelectedDoctype() {
		const names = new Set((this.overview?.doctypes || []).map((item) => item.name));
		if (this.selectedDoctype && names.has(this.selectedDoctype)) {
			return this.selectedDoctype;
		}
		return names.has("Sales Order") ? "Sales Order" : this.overview?.doctypes?.[0]?.name;
	}

	async captureSnapshot() {
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				__("Capture and persist a read-only snapshot of the current site's metadata?"),
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) {
			return;
		}

		this.page.btn_primary?.prop("disabled", true);
		frappe.show_alert({ message: __("Capturing schema metadata…"), indicator: "blue" });
		try {
			const snapshot = await frappe.xcall("pridict.schema_intelligence.api.capture_and_persist");
			frappe.show_alert({ message: __("Schema snapshot saved"), indicator: "green" }, 5);
			await this.refresh(snapshot.snapshot_id);
		} catch (error) {
			frappe.msgprint({
				title: __("Snapshot could not be completed"),
				message: this.errorMessage(error),
				indicator: "red",
			});
		} finally {
			this.page.btn_primary?.prop("disabled", false);
		}
	}

	renderLoading(message) {
		this.$root.html(`
			<div class="pridict-schema-state" role="status">
				<div class="pridict-executive-spinner"></div>
				<strong>${this.escape(message)}</strong>
				<span>${__("Reading private schema intelligence data.")}</span>
			</div>
		`);
	}

	renderEmpty() {
		this.$root.html(`
			<section class="pridict-schema-empty">
				<div class="pridict-schema-empty-icon">${frappe.utils.icon("branch", "xl")}</div>
				<span class="pridict-schema-eyebrow">${__("Schema Intelligence")}</span>
				<h2>${__("No schema snapshots yet")}</h2>
				<p>${__("Capture the current effective metadata to create the first protected baseline.")}</p>
				<button class="btn btn-primary" data-action="capture">${__("Capture first snapshot")}</button>
			</section>
		`);
		this.$root.find('[data-action="capture"]').on("click", () => this.captureSnapshot());
	}

	renderError(error) {
		this.$root.html(`
			<div class="pridict-schema-state pridict-schema-state-error" role="alert">
				<strong>${__("Schema Intelligence could not be loaded")}</strong>
				<span>${this.errorMessage(error)}</span>
				<button class="btn btn-primary" data-action="retry">${__("Try again")}</button>
			</div>
		`);
		this.$root.find('[data-action="retry"]').on("click", () => this.refresh());
	}

	render() {
		const summary = this.overview.summary;
		this.$root.html(`
			<div class="pridict-schema-shell">
				<section class="pridict-schema-hero">
					<div>
						<span class="pridict-schema-eyebrow">${__("Read-only metadata map")}</span>
						<h1>${__("Understand the structure behind your ERP")}</h1>
						<p>${__("Explore effective DocTypes, fields, permissions, and relationships without reading business records.")}</p>
					</div>
					<div class="pridict-schema-snapshot-picker">
						<label for="pridict-schema-snapshot">${__("Snapshot")}</label>
						<select id="pridict-schema-snapshot" class="form-control">
							${this.snapshots.map((item) => this.snapshotOption(item)).join("")}
						</select>
					</div>
				</section>
				${this.renderSummary(summary)}
				${this.renderGovernance()}
				${this.renderDiagnostics()}
				<section class="pridict-schema-browser">
					<aside class="pridict-schema-index">
						<div class="pridict-schema-index-head">
							<div>
								<span class="pridict-schema-eyebrow">${__("Schema catalog")}</span>
								<h2>${__("DocTypes")}</h2>
							</div>
							<span class="pridict-schema-count" data-doctype-count></span>
						</div>
						<div class="pridict-schema-filters">
							<input class="form-control" data-schema-search type="search" placeholder="${__("Search DocTypes")}" value="${this.escape(this.searchTerm)}">
							<select class="form-control" data-schema-type>
								${this.filterOption("all", __("All types"))}
								${this.filterOption("standard", __("Standard"))}
								${this.filterOption("custom", __("Custom"))}
								${this.filterOption("child", __("Child tables"))}
								${this.filterOption("single", __("Single DocTypes"))}
								${this.filterOption("virtual", __("Virtual DocTypes"))}
							</select>
						</div>
						<div class="pridict-schema-doctype-list" data-doctype-list></div>
					</aside>
					<main class="pridict-schema-detail" data-schema-detail>
						${this.renderDetailPlaceholder()}
					</main>
				</section>
			</div>
		`);
		this.bindControls();
		this.renderDoctypeList();
	}

	renderGovernance() {
		const snapshot = this.currentSnapshot();
		if (!snapshot) return "";
		return `
			<section class="pridict-schema-diagnostics">
				<div class="pridict-schema-diagnostics-head">
					<div>
						<span class="pridict-schema-eyebrow">${__("Governance")}</span>
						<h2>${this.escape(snapshot.label || __("Unlabelled snapshot"))}</h2>
					</div>
					<div class="pridict-schema-status-line">
						${snapshot.is_baseline ? `<span class="indicator-pill green">${__("Baseline")}</span>` : ""}
						<span class="indicator-pill gray">${this.escape(snapshot.lifecycle_state || __("Retained"))}</span>
						<span class="indicator-pill blue">${this.escape(snapshot.review_status || __("Unreviewed"))}</span>
					</div>
				</div>
			</section>
		`;
	}

	currentSnapshot() {
		return this.snapshots.find((item) => item.snapshot_id === this.selectedSnapshotId);
	}

	openSelectedSnapshot() {
		if (!this.selectedSnapshotId) return;
		frappe.set_route("Form", "Schema Snapshot Record", this.selectedSnapshotId);
	}

	async openCreateReview() {
		if (this.snapshots.length < 2) {
			frappe.msgprint(__("Capture at least two snapshots before creating a review."));
			return;
		}
		const options = this.snapshots.map((item) => item.snapshot_id).join("\n");
		const baseline = this.snapshots.find((item) => item.is_baseline)?.snapshot_id || this.snapshots[1].snapshot_id;
		const dialog = new frappe.ui.Dialog({
			title: __("Create schema change review"),
			fields: [
				{ fieldname: "baseline", fieldtype: "Select", label: __("Baseline snapshot"), options, default: baseline, reqd: 1 },
				{ fieldname: "candidate", fieldtype: "Select", label: __("Candidate snapshot"), options, default: this.snapshots[0].snapshot_id, reqd: 1 },
			],
			primary_action_label: __("Create Review"),
			primary_action: async (values) => {
				dialog.disable_primary_action();
				try {
					const review = await frappe.xcall("pridict.schema_intelligence.api.create_review", {
						baseline_snapshot_id: values.baseline,
						candidate_snapshot_id: values.candidate,
					});
					dialog.hide();
					frappe.set_route("Form", "Schema Change Review", review.name);
				} catch (error) {
					frappe.msgprint({ title: __("Review could not be created"), message: this.errorMessage(error), indicator: "red" });
					dialog.enable_primary_action();
				}
			},
		});
		dialog.show();
	}

	renderSummary(summary) {
		const cards = [
			[__("DocTypes"), summary.doctype_count, "table"],
			[__("Fields"), summary.field_count, "list"],
			[__("Relationships"), summary.relationship_count, "branch"],
			[__("Permissions"), summary.permission_count, "lock"],
		];
		return `
			<section class="pridict-schema-summary">
				${cards
					.map(
						([label, value, icon]) => `
							<article class="pridict-schema-stat">
								<span>${frappe.utils.icon(icon, "md")}</span>
								<strong>${this.escape(value)}</strong>
								<small>${this.escape(label)}</small>
							</article>
						`
					)
					.join("")}
				<article class="pridict-schema-stat pridict-schema-stat-wide">
					<div class="pridict-schema-status-line">
						<span class="indicator-pill ${summary.completeness === "complete" ? "green" : "red"}">
							${this.escape(summary.completeness)}
						</span>
						<span>${this.escape(this.formatDate(summary.captured_at))}</span>
					</div>
					<code title="${this.escape(summary.metadata_hash)}">${this.escape(summary.metadata_hash.slice(0, 16))}…</code>
					<small>${__("Semantic metadata hash")}</small>
				</article>
			</section>
		`;
	}

	renderDiagnostics() {
		const diagnostics = this.overview.diagnostics || [];
		if (!diagnostics.length) {
			return "";
		}
		return `
			<details class="pridict-schema-diagnostics">
				<summary>
					${frappe.utils.icon("alert-triangle", "sm")}
					${__("Diagnostics")}
					<span>${diagnostics.length}</span>
				</summary>
				<div>
					${diagnostics.map((item) => this.renderDiagnostic(item)).join("")}
				</div>
			</details>
		`;
	}

	renderDiagnostic(item) {
		const location = [item.doctype, item.fieldname].filter(Boolean).join(" · ");
		return `
			<div class="pridict-schema-diagnostic is-${this.escape(item.severity)}">
				<strong>${this.escape(item.code)}</strong>
				<span>${this.escape(item.message)}</span>
				${location ? `<small>${this.escape(location)}</small>` : ""}
			</div>
		`;
	}

	renderDoctypeList() {
		const query = this.searchTerm.trim().toLowerCase();
		const doctypes = (this.overview.doctypes || []).filter((item) => {
			const matchesSearch = !query || `${item.name} ${item.module || ""}`.toLowerCase().includes(query);
			return matchesSearch && this.matchesType(item);
		});
		this.$root.find("[data-doctype-count]").text(doctypes.length);
		this.$root.find("[data-doctype-list]").html(
			doctypes.length
				? doctypes.map((item) => this.renderDoctypeRow(item)).join("")
				: `<div class="pridict-schema-no-results">${__("No DocTypes match these filters.")}</div>`
		);
		this.$root.find("[data-doctype]").on("click", (event) => {
			this.loadDoctype(event.currentTarget.dataset.doctype);
		});
	}

	renderDoctypeRow(item) {
		const active = item.name === this.selectedDoctype ? "is-active" : "";
		const tags = [
			item.flags.custom ? __("Custom") : null,
			item.flags.istable ? __("Child") : null,
			item.flags.issingle ? __("Single") : null,
			item.flags.is_virtual ? __("Virtual") : null,
		].filter(Boolean);
		return `
			<button class="pridict-schema-doctype ${active}" data-doctype="${this.escape(item.name)}">
				<span class="pridict-schema-doctype-main">
					<strong>${this.escape(item.name)}</strong>
					<small>${this.escape(item.module || __("No module"))}</small>
				</span>
				<span class="pridict-schema-doctype-meta">
					<span>${item.field_count} ${__("fields")}</span>
					<span>${item.relationship_count} ${__("links")}</span>
					${tags.map((tag) => `<em>${this.escape(tag)}</em>`).join("")}
				</span>
			</button>
		`;
	}

	async loadDoctype(doctype) {
		this.selectedDoctype = doctype;
		this.renderDoctypeList();
		const $detail = this.$root.find("[data-schema-detail]");
		$detail.html(`<div class="pridict-schema-detail-loading">${__("Loading DocType metadata…")}</div>`);
		try {
			this.detail = await frappe.xcall("pridict.schema_intelligence.api.get_doctype_schema", {
				snapshot_id: this.selectedSnapshotId,
				doctype,
			});
			$detail.html(this.renderDetail());
			this.bindDetailTabs();
		} catch (error) {
			$detail.html(`<div class="pridict-schema-detail-error">${this.errorMessage(error)}</div>`);
		}
	}

	renderDetailPlaceholder() {
		return `<div class="pridict-schema-detail-loading">${__("Select a DocType to inspect it.")}</div>`;
	}

	renderDetail() {
		const doctype = this.detail.doctype;
		const relationships = this.detail.relationships || [];
		return `
			<header class="pridict-schema-detail-head">
				<div>
					<span class="pridict-schema-eyebrow">${this.escape(doctype.module || __("No module"))}</span>
					<h2>${this.escape(doctype.name)}</h2>
				</div>
				<div class="pridict-schema-tags">${this.renderFlagTags(doctype.flags)}</div>
			</header>
			<div class="pridict-schema-tabs" role="tablist">
				<button class="is-active" data-detail-tab="fields">${__("Fields")} <span>${doctype.fields.length}</span></button>
				<button data-detail-tab="relationships">${__("Relationships")} <span>${relationships.length}</span></button>
				<button data-detail-tab="permissions">${__("Permissions")} <span>${doctype.permissions.length}</span></button>
				<button data-detail-tab="metadata">${__("Metadata")}</button>
			</div>
			<div class="pridict-schema-tab-panel is-active" data-detail-panel="fields">
				${this.renderFields(doctype.fields)}
			</div>
			<div class="pridict-schema-tab-panel" data-detail-panel="relationships">
				<button class="btn btn-default btn-sm" data-action="explore-relationships">${__("Explore two-hop graph")}</button>
				${this.renderRelationshipGraph(doctype.name, relationships)}
				${this.renderRelationships(relationships)}
			</div>
			<div class="pridict-schema-tab-panel" data-detail-panel="permissions">
				${this.renderPermissions(doctype.permissions)}
			</div>
			<div class="pridict-schema-tab-panel" data-detail-panel="metadata">
				${this.renderMetadata(doctype)}
			</div>
		`;
	}

	renderFields(fields) {
		if (!fields.length) {
			return `<div class="pridict-schema-no-results">${__("No fields recorded.")}</div>`;
		}
		return `
			<div class="pridict-schema-table-wrap">
				<table class="pridict-schema-table">
					<thead><tr><th>${__("Field")}</th><th>${__("Type")}</th><th>${__("Options")}</th><th>${__("Flags")}</th><th>${__("Source")}</th></tr></thead>
					<tbody>
						${fields.map((field) => this.renderFieldRow(field)).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	renderFieldRow(field) {
		const flags = [
			field.required ? __("Required") : null,
			field.read_only ? __("Read only") : null,
			field.hidden ? __("Hidden") : null,
			field.virtual ? __("Virtual") : null,
			field.custom ? __("Custom") : null,
		].filter(Boolean);
		return `
			<tr>
				<td><strong>${this.escape(field.label || field.fieldname)}</strong><code>${this.escape(field.fieldname)}</code></td>
				<td><span class="pridict-schema-type">${this.escape(field.fieldtype)}</span></td>
				<td>${this.escape(this.displayValue(field.options))}</td>
				<td>${flags.length ? flags.map((flag) => `<span class="pridict-schema-tag">${this.escape(flag)}</span>`).join("") : "—"}</td>
				<td>${this.escape(field.provenance.map((item) => item.source_type).join(", "))}</td>
			</tr>
		`;
	}

	renderRelationshipGraph(doctype, relationships) {
		if (!relationships.length) {
			return `<div class="pridict-schema-no-results">${__("No outbound relationships.")}</div>`;
		}
		const visible = relationships.slice(0, 16);
		const height = Math.max(240, visible.length * 54 + 40);
		const rootY = height / 2;
		const rootId = this.escape(doctype);
		return `
			<div class="pridict-schema-graph" role="img" aria-label="${__("Relationship graph for {0}", [doctype])}">
				<svg viewBox="0 0 820 ${height}" preserveAspectRatio="xMinYMin meet">
					<g class="pridict-schema-graph-root">
						<rect x="24" y="${rootY - 24}" width="230" height="48" rx="12"></rect>
						<text x="139" y="${rootY + 5}" text-anchor="middle">${rootId}</text>
					</g>
					${visible.map((item, index) => this.renderGraphEdge(item, index, rootY)).join("")}
				</svg>
				${relationships.length > visible.length ? `<small>${__("Showing the first {0} of {1} relationships.", [visible.length, relationships.length])}</small>` : ""}
			</div>
		`;
	}

	renderGraphEdge(relationship, index, rootY) {
		const target = relationship.target_doctype || `${__("Dynamic via")} ${relationship.selector_field}`;
		const targetY = 32 + index * 54;
		return `
			<g class="pridict-schema-graph-edge">
				<path d="M254 ${rootY} C390 ${rootY}, 390 ${targetY}, 532 ${targetY}"></path>
				<text x="390" y="${Math.min(rootY, targetY) + Math.abs(rootY - targetY) / 2 - 5}" text-anchor="middle">${this.escape(relationship.source_field)}</text>
				<rect x="532" y="${targetY - 20}" width="260" height="40" rx="10"></rect>
				<text x="662" y="${targetY + 5}" text-anchor="middle">${this.escape(target)}</text>
			</g>
		`;
	}

	renderRelationships(relationships) {
		return `
			<div class="pridict-schema-relationship-list">
				${relationships
					.map(
						(item) => `
							<div>
								<span class="pridict-schema-type">${this.escape(item.relationship_type)}</span>
								<strong>${this.escape(item.source_field)}</strong>
								<span>${frappe.utils.icon("arrow-right", "xs")}</span>
								<code>${this.escape(item.target_doctype || item.selector_field || __("Dynamic"))}</code>
							</div>
						`
					)
					.join("")}
			</div>
		`;
	}

	renderPermissions(permissions) {
		if (!permissions.length) {
			return `<div class="pridict-schema-no-results">${__("No permission rows recorded.")}</div>`;
		}
		return `
			<div class="pridict-schema-permissions">
				${permissions
					.map((permission) => {
						const enabled = Object.entries(permission.permissions)
							.filter(([, value]) => value === true || value === 1)
							.map(([name]) => name);
						return `
							<article>
								<div><strong>${this.escape(permission.role)}</strong><span>${this.escape(permission.source)}</span></div>
								<small>${__("Permission level")} ${permission.permlevel}${permission.if_owner ? ` · ${__("If owner")}` : ""}</small>
								<p>${enabled.length ? enabled.map((item) => `<span class="pridict-schema-tag">${this.escape(item)}</span>`).join("") : "—"}</p>
							</article>
						`;
					})
					.join("")}
			</div>
		`;
	}

	renderMetadata(doctype) {
		return `
			<div class="pridict-schema-metadata-grid">
				<article><span>${__("Module")}</span><strong>${this.escape(doctype.module || "—")}</strong></article>
				<article><span>${__("Provenance")}</span><strong>${this.escape(doctype.provenance.map((item) => item.source_type).join(", "))}</strong></article>
			</div>
			<details class="pridict-schema-properties">
				<summary>${__("Normalized properties")}</summary>
				<pre>${this.escape(JSON.stringify(doctype.properties, null, 2))}</pre>
			</details>
		`;
	}

	renderFlagTags(flags) {
		const labels = {
			custom: __("Custom"),
			istable: __("Child table"),
			issingle: __("Single"),
			is_virtual: __("Virtual"),
			is_submittable: __("Submittable"),
		};
		const tags = Object.entries(labels)
			.filter(([name]) => flags[name])
			.map(([, label]) => `<span class="pridict-schema-tag">${this.escape(label)}</span>`);
		return tags.length ? tags.join("") : `<span class="pridict-schema-tag">${__("Standard")}</span>`;
	}

	bindControls() {
		this.$root.find("#pridict-schema-snapshot").on("change", async (event) => {
			this.selectedSnapshotId = event.currentTarget.value;
			await this.loadOverview();
		});
		this.$root.find("[data-schema-search]").on("input", (event) => {
			this.searchTerm = event.currentTarget.value;
			this.renderDoctypeList();
		});
		this.$root.find("[data-schema-type]").on("change", (event) => {
			this.typeFilter = event.currentTarget.value;
			this.renderDoctypeList();
		});
	}

	bindDetailTabs() {
		this.$root.find("[data-detail-tab]").on("click", (event) => {
			const tab = event.currentTarget.dataset.detailTab;
			this.$root.find("[data-detail-tab]").removeClass("is-active");
			this.$root.find("[data-detail-panel]").removeClass("is-active");
			$(event.currentTarget).addClass("is-active");
			this.$root.find(`[data-detail-panel="${tab}"]`).addClass("is-active");
		});
		this.$root.find('[data-action="explore-relationships"]').on("click", () => this.openRelationshipExplorer());
	}

	async openRelationshipExplorer() {
		const graph = await frappe.xcall("pridict.schema_intelligence.api.get_relationship_subgraph", {
			snapshot_id: this.selectedSnapshotId,
			root_doctype: this.selectedDoctype,
			hops: 2,
			direction: "both",
		});
		const dialog = new frappe.ui.Dialog({
			title: __("Relationship neighborhood"),
			size: "extra-large",
			fields: [{ fieldname: "content", fieldtype: "HTML" }],
			primary_action_label: __("Export JSON"),
			primary_action: async () => {
				const result = await frappe.xcall("pridict.schema_intelligence.api.export_subgraph", {
					snapshot_id: this.selectedSnapshotId,
					root_doctype: this.selectedDoctype,
					hops: 2,
					direction: "both",
					format: "json",
				});
				this.download(result);
			},
		});
		dialog.fields_dict.content.$wrapper.html(`
			<div class="pridict-schema-comparison">
				<div class="pridict-schema-comparison-status ${graph.truncated ? "is-changed" : "is-equivalent"}">
					<strong>${graph.nodes.length} ${__("nodes")} · ${graph.edges.length} ${__("edges")}</strong>
					<span>${graph.truncated ? __("Results reached the configured safety limit.") : __("Complete within configured limits.")}</span>
				</div>
				${this.renderRelationships(graph.edges)}
			</div>
		`);
		dialog.show();
	}

	async openComparison() {
		if (this.snapshots.length < 2) {
			frappe.msgprint(__("Capture at least two snapshots before comparing them."));
			return;
		}
		const options = this.snapshots.map((item) => item.snapshot_id).join("\n");
		const values = await new Promise((resolve) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Compare schema snapshots"),
				fields: [
					{
						fieldname: "before",
						fieldtype: "Select",
						label: __("Before snapshot"),
						options,
						default: this.snapshots[1].snapshot_id,
						reqd: 1,
					},
					{
						fieldname: "after",
						fieldtype: "Select",
						label: __("After snapshot"),
						options,
						default: this.snapshots[0].snapshot_id,
						reqd: 1,
					},
				],
				primary_action_label: __("Compare"),
				primary_action: (data) => {
					dialog.hide();
					resolve(data);
				},
			});
			dialog.$wrapper.on("hidden.bs.modal", () => resolve(null));
			dialog.show();
		});
		if (!values) {
			return;
		}
		const comparison = await frappe.xcall("pridict.schema_intelligence.api.compare_snapshots", {
			before_snapshot_id: values.before,
			after_snapshot_id: values.after,
		});
		this.showComparison(comparison);
	}

	showComparison(comparison) {
		const dialog = new frappe.ui.Dialog({
			title: __("Schema comparison"),
			size: "extra-large",
			fields: [{ fieldname: "content", fieldtype: "HTML" }],
		});
		dialog.fields_dict.content.$wrapper.html(this.renderComparison(comparison));
		dialog.show();
	}

	renderComparison(comparison) {
		const changedFields = Object.values(comparison.fields || {}).reduce(
			(total, item) => total + item.added.length + item.removed.length + item.changed.length,
			0
		);
		const changedPermissions = Object.values(comparison.permissions || {}).reduce(
			(total, item) => total + item.added.length + item.removed.length + item.changed.length,
			0
		);
		const cards = [
			[__("Added DocTypes"), comparison.added_doctypes.length],
			[__("Removed DocTypes"), comparison.removed_doctypes.length],
			[__("Changed Fields"), changedFields],
			[__("Relationship Changes"), this.changeCount(comparison.relationships)],
			[__("Permission Changes"), changedPermissions],
		];
		return `
			<div class="pridict-schema-comparison">
				<div class="pridict-schema-comparison-status ${comparison.equivalent ? "is-equivalent" : "is-changed"}">
					<strong>${comparison.equivalent ? __("No structural changes") : __("Structural changes detected")}</strong>
					<span>${this.escape(comparison.before_metadata_hash.slice(0, 12))} → ${this.escape(comparison.after_metadata_hash.slice(0, 12))}</span>
				</div>
				<div class="pridict-schema-comparison-grid">
					${cards.map(([label, value]) => `<article><strong>${value}</strong><span>${this.escape(label)}</span></article>`).join("")}
				</div>
				${this.renderComparisonSection(__("Added DocTypes"), comparison.added_doctypes)}
				${this.renderComparisonSection(__("Removed DocTypes"), comparison.removed_doctypes)}
				${this.renderComparisonMap(__("Field changes"), comparison.fields)}
				${this.renderComparisonSection(__("Field order changed"), comparison.field_order_changed)}
				${this.renderComparisonMap(__("Permission changes"), comparison.permissions)}
				${this.renderComparisonSection(__("Relationship changes"), [
					...(comparison.relationships.added || []).map((item) => `+ ${item}`),
					...(comparison.relationships.removed || []).map((item) => `− ${item}`),
					...(comparison.relationships.changed || []).map((item) => `~ ${item}`),
				])}
			</div>
		`;
	}

	renderComparisonMap(title, values) {
		const rows = Object.entries(values || {}).flatMap(([doctype, changes]) => [
			...changes.added.map((item) => `${doctype}: + ${item}`),
			...changes.removed.map((item) => `${doctype}: − ${item}`),
			...changes.changed.map((item) => `${doctype}: ~ ${item}`),
		]);
		return this.renderComparisonSection(title, rows);
	}

	renderComparisonSection(title, items) {
		if (!items?.length) {
			return "";
		}
		return `
			<section class="pridict-schema-comparison-section">
				<h4>${this.escape(title)}</h4>
				${items.map((item) => `<code>${this.escape(item)}</code>`).join("")}
			</section>
		`;
	}

	changeCount(changes) {
		return (changes.added || []).length + (changes.removed || []).length + (changes.changed || []).length;
	}

	matchesType(item) {
		if (this.typeFilter === "custom") return Boolean(item.flags.custom);
		if (this.typeFilter === "child") return Boolean(item.flags.istable);
		if (this.typeFilter === "single") return Boolean(item.flags.issingle);
		if (this.typeFilter === "virtual") return Boolean(item.flags.is_virtual);
		if (this.typeFilter === "standard") return !item.flags.custom;
		return true;
	}

	filterOption(value, label) {
		return `<option value="${value}" ${this.typeFilter === value ? "selected" : ""}>${this.escape(label)}</option>`;
	}

	snapshotOption(snapshot) {
		const selected = snapshot.snapshot_id === this.selectedSnapshotId ? "selected" : "";
		const governance = [snapshot.is_baseline ? __("Baseline") : null, snapshot.label].filter(Boolean).join(" · ");
		const label = `${governance ? `${governance} · ` : ""}${this.formatDate(snapshot.captured_at)} · ${snapshot.metadata_hash.slice(0, 10)}`;
		return `<option value="${this.escape(snapshot.snapshot_id)}" ${selected}>${this.escape(label)}</option>`;
	}

	displayValue(value) {
		if (value === null || value === undefined || value === "") {
			return "—";
		}
		return typeof value === "object" ? JSON.stringify(value) : String(value);
	}

	formatDate(value) {
		const date = new Date(value);
		return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
	}

	errorMessage(error) {
		return this.escape(error?.message || error?._server_messages || __("An unexpected error occurred."));
	}

	download(result) {
		const blob = new Blob([result.content], { type: result.content_type });
		const link = document.createElement("a");
		link.href = URL.createObjectURL(blob);
		link.download = result.filename;
		link.click();
		URL.revokeObjectURL(link.href);
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}
}
