frappe.pages["procurement-assistant"].on_page_load = async (wrapper) => {
	await frappe.require("/assets/pridict/css/procurement_assistant.css");
	wrapper.procurement_assistant = new ProcurementAssistant(wrapper);
	wrapper.procurement_assistant.show();
};

frappe.pages["procurement-assistant"].on_page_show = (wrapper) => {
	wrapper.procurement_assistant?.show();
};

const PA_API = "pridict.agent_studio.assistant";

// What each run status means to the buyer.
const PA_STATUS = {
	Queued: ["Working…", "info"],
	Running: ["Working…", "info"],
	"Waiting for buyer": ["Needs your reply", "warn"],
	"Awaiting approval": ["Waiting for approval", "info"],
	Completed: ["Done", "good"],
	Rejected: ["Not approved", "bad"],
	Cancelled: ["Stopped", "muted"],
	Failed: ["Couldn't finish", "bad"],
};

class ProcurementAssistant {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Procurement Assistant"), single_column: true });
		$(wrapper).addClass("pa-page");
		this.root = $('<div class="pa-shell"></div>').appendTo(this.page.main.empty())[0];
		this.conversations = [];
		this.current = null;
		this.detail = null;
		this.draft = "";
		this.sending = false;
		if (frappe.user.has_role("System Manager")) {
			this.page.add_inner_button(__("Agent Studio traces"), () => frappe.set_route("agent-runs"));
		}
		frappe.realtime.on("agent_run_update", ({ run } = {}) => {
			if (!document.body.contains(this.root)) return;
			if (run === this.current) this.scheduleReload();
			else if (this.conversations.some((c) => c.name === run)) this.loadList();
		});
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	text(value) {
		return this.esc(value).replace(/\n/g, "<br>");
	}

	// ---------------------------------------------------------------- data

	async show() {
		const [, name] = frappe.get_route();
		this.current = name || null;
		this.detail = null;
		const info = await frappe.xcall(`${PA_API}.get_assistant`);
		this.info = info;
		this.conversations = info.conversations;
		this.render();
		if (this.current) await this.loadDetail();
	}

	async loadList() {
		this.conversations = await frappe.xcall(`${PA_API}.get_conversations`);
		this.renderSide();
	}

	async loadDetail() {
		if (!this.current) return;
		const name = this.current;
		const detail = await frappe.xcall(`${PA_API}.get_conversation`, { name });
		if (name !== this.current) return;
		const statusChanged = this.detail?.status !== detail.status;
		this.detail = detail;
		this.renderMain();
		if (statusChanged) this.loadList();
		// Realtime is the main signal; polling covers a dropped socket while the agent works.
		clearTimeout(this.poll);
		if (detail.working) this.poll = setTimeout(() => document.body.contains(this.root) && this.loadDetail(), 4000);
	}

	scheduleReload() {
		clearTimeout(this.pending);
		this.pending = setTimeout(() => this.loadDetail(), 300);
	}

	open(name) {
		frappe.set_route(name ? ["procurement-assistant", name] : ["procurement-assistant"]);
	}

	async send(text) {
		text = (text || "").trim();
		if (!text || this.sending) return;
		this.sending = true;
		const conversation = this.detail?.can_reply ? this.current : null;
		this.draft = "";
		// Show the message straight away; the server copy replaces it on reload.
		if (conversation) {
			this.detail.messages.push({ role: "user", kind: "text", content: text, choices: [] });
			this.detail.messages.forEach((m) => (m.choices = []));
			this.detail.working = true;
			this.detail.can_reply = false;
		} else {
			this.detail = { name: null, status: "Queued", working: true, messages: [{ role: "user", kind: "text", content: text, choices: [] }] };
		}
		this.renderMain();
		try {
			const result = await frappe.xcall(`${PA_API}.send_message`, { text, conversation });
			if (result.conversation !== this.current) {
				this.current = result.conversation;
				frappe.set_route(["procurement-assistant", result.conversation]);
			} else {
				await this.loadDetail();
			}
		} catch (error) {
			// The server already showed the error; put the text back so nothing is lost.
			this.draft = text;
			if (this.current) {
				await this.loadDetail();
			} else {
				this.detail = null;
				this.renderMain();
			}
		} finally {
			this.sending = false;
		}
	}

	// ---------------------------------------------------------------- render

	render() {
		this.root.innerHTML = `
			<aside class="pa-side" aria-label="${__("Your requests")}"></aside>
			<section class="pa-main" aria-live="polite"></section>`;
		this.renderSide();
		this.renderMain();
	}

	renderSide() {
		const side = this.root.querySelector(".pa-side");
		if (!side) return;
		side.innerHTML = `
			<button type="button" class="btn btn-primary btn-sm pa-new"><i class="fa fa-plus" aria-hidden="true"></i> ${__("New request")}</button>
			<div class="pa-side-title">${__("Your requests")}</div>
			<nav class="pa-list">
				${this.conversations.length ? this.conversations.map((c) => {
					const [label, tone] = PA_STATUS[c.status] || [c.status, "muted"];
					return `<button type="button" class="pa-item ${c.name === this.current ? "is-active" : ""}" data-name="${this.esc(c.name)}">
						<span class="pa-item-title">${this.esc(c.title || __("Request"))}</span>
						<span class="pa-item-meta"><span class="pa-dot pa-tone-${tone}"></span>${__(label)} · ${frappe.datetime.comment_when(c.creation, true)}</span>
					</button>`;
				}).join("") : `<p class="pa-muted">${__("Nothing yet. Your requests will appear here.")}</p>`}
			</nav>`;
		side.querySelector(".pa-new").addEventListener("click", () => this.open(null));
		side.querySelectorAll(".pa-item").forEach((el) => el.addEventListener("click", () => this.open(el.dataset.name)));
	}

	renderMain() {
		const main = this.root.querySelector(".pa-main");
		if (!main) return;
		const d = this.detail;
		if (this.current && !d) {
			main.innerHTML = `<div class="pa-thread"><div class="pa-typing"><span></span><span></span><span></span></div></div>`;
			return;
		}
		main.innerHTML = `
			${d?.name ? this.renderHeader(d) : ""}
			<div class="pa-thread">${d ? this.renderMessages(d) : this.renderWelcome()}</div>
			${this.renderComposer(d)}`;
		this.bindMain(main);
		const thread = main.querySelector(".pa-thread");
		thread.scrollTop = thread.scrollHeight;
	}

	renderHeader(d) {
		const [label, tone] = PA_STATUS[d.status] || [d.status, "muted"];
		return `<header class="pa-head">
			<div class="pa-head-title">${this.esc(d.title || "")}</div>
			<span class="pa-pill pa-tone-${tone}">${__(label)}</span>
			${d.can_cancel ? `<button type="button" class="btn btn-default btn-xs pa-cancel">${__("Cancel request")}</button>` : ""}
		</header>`;
	}

	renderWelcome() {
		const info = this.info || {};
		const name = frappe.boot.user.first_name || frappe.session.user_fullname || "";
		return `<div class="pa-welcome">
			<div class="pa-avatar pa-avatar-lg"><i class="fa fa-magic" aria-hidden="true"></i></div>
			<h2>${__("Hi {0}, what do you need to buy?", [this.esc(name)])}</h2>
			<p>${__("Tell me what you need, how many and by when. I'll check stock and open orders, find suppliers, and prepare a request for quotation for approval. If something is missing, like the item or a supplier, I'll help you set it up.")}</p>
			${info.available ? `<div class="pa-suggestions">${(info.suggestions || []).map((s) => `<button type="button" class="pa-chip" data-text="${this.esc(s)}">${this.esc(s)}</button>`).join("")}</div>`
			: `<div class="pa-notice pa-tone-warn">${this.esc(info.reason)}</div>`}
			${info.test_mode ? `<p class="pa-muted">${__("Test mode: the assistant is not live yet, so only administrators can use it.")}</p>` : ""}
		</div>`;
	}

	renderMessages(d) {
		const rows = d.messages.map((m) => this.renderMessage(m)).join("");
		const typing = d.working ? `<div class="pa-row pa-row-assistant"><div class="pa-avatar"><i class="fa fa-magic" aria-hidden="true"></i></div><div class="pa-typing" role="status" aria-label="${__("Working")}"><span></span><span></span><span></span></div></div>` : "";
		const done = !d.working && !d.can_reply && d.status !== "Awaiting approval"
			? `<div class="pa-end"><button type="button" class="btn btn-default btn-sm pa-new-inline">${__("Start a new request")}</button></div>` : "";
		return rows + typing + done;
	}

	renderMessage(m) {
		if (m.role === "user") {
			return `<div class="pa-row pa-row-user"><div class="pa-bubble pa-bubble-user">${this.text(m.content)}</div></div>`;
		}
		if (m.kind === "notice") {
			return `<div class="pa-row pa-row-notice"><i class="fa fa-check-circle" aria-hidden="true"></i> ${this.text(m.content)}</div>`;
		}
		return `<div class="pa-row pa-row-assistant">
			<div class="pa-avatar"><i class="fa fa-magic" aria-hidden="true"></i></div>
			<div class="pa-stack">
				<div class="pa-bubble ${m.kind === "error" ? "pa-bubble-error" : ""}">${this.text(m.content)}</div>
				${m.card ? this.renderCard(m.card, m.kind) : ""}
				${m.choices?.length ? `<div class="pa-suggestions">${m.choices.map((c) => `<button type="button" class="pa-chip" data-text="${this.esc(c)}">${this.esc(c)}</button>`).join("")}</div>` : ""}
			</div>
		</div>`;
	}

	renderCard(card, kind) {
		const link = card.link;
		return `<div class="pa-card ${kind === "result" ? "pa-card-result" : ""}">
			${card.title ? `<div class="pa-card-title">${this.esc(card.title)}</div>` : ""}
			<dl>${(card.fields || []).map(([k, v]) => `<dt>${this.esc(k)}</dt><dd>${this.esc(v)}</dd>`).join("")}</dl>
			${link ? `<a class="btn btn-primary btn-xs" href="/app/${frappe.router.slug(link.doctype)}/${encodeURIComponent(link.name)}">${__("Open {0}", [this.esc(link.name)])}</a>` : ""}
		</div>`;
	}

	renderComposer(d) {
		const available = this.info?.available;
		const working = d?.working;
		let placeholder = __("Describe what you need…");
		if (d?.can_reply) placeholder = __("Type your answer…");
		else if (working) placeholder = __("One moment, I'm working on it…");
		else if (d?.name) placeholder = __("Start a new request…");
		const disabled = working || this.sending || (!d?.can_reply && !available);
		return `<form class="pa-composer">
			<textarea class="form-control pa-input" rows="1" placeholder="${placeholder}" ${disabled ? "disabled" : ""} aria-label="${__("Message")}">${this.esc(this.draft)}</textarea>
			<button type="submit" class="btn btn-primary pa-send" ${disabled ? "disabled" : ""} aria-label="${__("Send")}"><i class="fa fa-paper-plane" aria-hidden="true"></i></button>
		</form>`;
	}

	bindMain(main) {
		const input = main.querySelector(".pa-input");
		const grow = () => {
			input.style.height = "auto";
			input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
		};
		input?.addEventListener("input", () => {
			this.draft = input.value;
			grow();
		});
		input?.addEventListener("keydown", (event) => {
			if (event.key === "Enter" && !event.shiftKey) {
				event.preventDefault();
				this.send(input.value);
			}
		});
		if (input && !input.disabled) {
			grow();
			input.focus();
		}
		main.querySelector(".pa-composer")?.addEventListener("submit", (event) => {
			event.preventDefault();
			this.send(input.value);
		});
		main.querySelectorAll(".pa-chip").forEach((chip) => chip.addEventListener("click", () => this.send(chip.dataset.text)));
		main.querySelector(".pa-new-inline")?.addEventListener("click", () => this.open(null));
		main.querySelector(".pa-cancel")?.addEventListener("click", () =>
			frappe.confirm(__("Cancel this request? Nothing more will be done for it."), async () => {
				await frappe.xcall(`${PA_API}.cancel_conversation`, { conversation: this.current });
				this.loadDetail();
			})
		);
	}
}
