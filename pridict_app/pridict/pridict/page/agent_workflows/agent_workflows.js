frappe.pages["agent-workflows"].on_page_load = async (wrapper) => {
	await frappe.require([
		"/assets/pridict/css/agent_studio.css",
		"/assets/pridict/js/agent_studio/sample_data.js",
		"/assets/pridict/js/agent_studio/common.js",
	]);
	const studio = window.pridict.agentStudio;
	const { t, escape, badge, kindBadge } = studio;

	const checks = [
		["Every node is reachable from the entry point", "PASS"],
		["Every path ends at END or a human pause", "PASS"],
		["Write tools are only reachable after a human approval node", "PASS"],
		["Router edges cover every possible outcome", "PASS"],
		["Loops are bounded by the agent's step limit (8)", "PASS"],
	];

	class AgentWorkflowsPage extends studio.StudioPage {
		constructor(wrapper) {
			super(wrapper, {
				route: "agent-workflows",
				title: "Workflow Designer",
				eyebrow: "Agent Studio · Step 3",
				intro: "A workflow is a map of steps (nodes) and arrows (edges). LangGraph follows this map at run time, so the order of work is decided by the map and the rules, not by the LLM.",
			});
			this.selected = "calc_shortage";
			this.refresh();
		}

		label(id) {
			if (id === "END") return "END";
			return this.data.workflow.nodes.find((n) => n.id === id)?.label || id;
		}

		render() {
			const wf = this.data.workflow;
			const node = wf.nodes.find((n) => n.id === this.selected);
			return `
				<div class="as-callout">
					<strong>${t("Version 1 is read-only.")}</strong>
					${t("Developers define the graph in Python and publish it here. Drag-and-drop editing comes later, once a second workflow proves which node types are needed.")}
				</div>
				<div class="as-split-wide">
					<section class="as-panel">
						<div class="as-panel-head">
							<h2>${escape(wf.name)}</h2>
							${badge("Active")}
						</div>
						<p class="as-muted">${escape(wf.version)} · ${wf.nodes.length} ${t("nodes")}</p>
						<div class="as-legend">${Object.keys(studio.kindLabels).filter((k) => k !== "end").map(kindBadge).join("")}</div>
						<div class="as-flow">
							<div class="as-node" style="cursor:default"><span class="as-node-num">▶</span><span class="as-node-title">${t("START: buyer request")}</span><span></span></div>
							${wf.nodes.map((n, i) => `
								<div class="as-connector"></div>
								<button type="button" class="as-node as-node-${n.kind} ${n.id === this.selected ? "is-selected" : ""}" data-node="${n.id}">
									<span class="as-node-num">${i + 1}</span>
									<span>
										<span class="as-node-title">${t(n.label)}</span>
										<div class="as-node-edges">${n.next.map(([cond, to]) => `${cond ? `<b>${t(cond)}</b> → ` : "→ "}${t(this.label(to))}`).join(" &nbsp;·&nbsp; ")}</div>
									</span>
									${kindBadge(n.kind)}
								</button>`).join("")}
						</div>
					</section>

					<div>
						<section class="as-panel as-node-detail">
							<div class="as-panel-head">
								<h2>${t(node.label)}</h2>
								${kindBadge(node.kind)}
							</div>
							<p class="as-muted">${t("Node ID")}: <code>${escape(node.id)}</code></p>
							<p>${t(node.desc)}</p>
							${node.tools ? `<h3>${t("Tools called")}</h3><p>${node.tools.map((x) => `<code>${escape(x)}</code>`).join(", ")}</p>` : ""}
							<h3>${t("Outgoing edges")}</h3>
							<div class="as-table-scroll"><table class="as-table">
								<thead><tr><th>${t("Condition")}</th><th>${t("Goes to")}</th></tr></thead>
								<tbody>${node.next.map(([cond, to]) => `<tr><td>${cond ? t(cond) : `<span class="as-muted">${t("always")}</span>`}</td><td>${t(this.label(to))}</td></tr>`).join("")}</tbody>
							</table></div>
						</section>

						<section class="as-panel">
							<div class="as-panel-head">
								<h2>${t("Graph validation")}</h2>
								<button type="button" class="btn btn-default btn-sm as-test-run">${t("Test run with sample request")}</button>
							</div>
							<div class="as-table-scroll"><table class="as-table"><tbody>
								${checks.map(([name, result]) => `<tr><td>${t(name)}</td><td>${badge(result)}</td></tr>`).join("")}
							</tbody></table></div>
						</section>
					</div>
				</div>`;
		}

		bind(body) {
			body.querySelectorAll("[data-node]").forEach((button) =>
				button.addEventListener("click", () => {
					this.selected = button.dataset.node;
					this.refresh();
				})
			);
			body.querySelector(".as-test-run").addEventListener("click", () => frappe.set_route("agent-runs"));
		}
	}

	wrapper.agent_studio = new AgentWorkflowsPage(wrapper);
};
