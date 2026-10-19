frappe.pages["procurement-assistant"].on_page_load = async (wrapper) => {
	await frappe.require("/assets/pridict/css/procurement_assistant.css");
	wrapper.procurement_assistant = new ProcurementAssistant(wrapper);
	wrapper.procurement_assistant.show();
};

frappe.pages["procurement-assistant"].on_page_show = (wrapper) => {
	wrapper.procurement_assistant?.show();
};

const PA_API = "pridict.agent_studio.assistant";

// What each conversation state means to the user.
const PA_STATE = {
	working: ["Working…", "info"],
	needs_reply: ["Needs your reply", "warn"],
	approval: ["Waiting for approval", "info"],
	open: ["", "muted"],
};

// A deliberately small markdown subset for assistant replies. Everything is escaped
// first; the only HTML produced is what this function writes, and links are allowed
// only to pages inside the desk (/app/...).
function paMarkdown(source) {
	// Escapes every character that could open a tag or leave an attribute.
	const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
	const inline = (s) =>
		esc(s)
			.replace(/\[([^\]]+)\]\((\/app\/[^)\s"'<>]+)\)/g, '<a href="$2">$1</a>')
			.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
			.replace(/`([^`]+)`/g, "<code>$1</code>");
	const lines = String(source || "").split("\n");
	const out = [];
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		// Table: header row, separator row, body rows.
		if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
			const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
			const head = cells(line);
			i += 2;
			const body = [];
			while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) body.push(cells(lines[i++]));
			i--;
			out.push(`<div class="pa-table-wrap"><table class="pa-table"><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
			continue;
		}
		if (/^\s*[-*]\s+/.test(line)) {
			const items = [];
			while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s+/, ""));
			i--;
			out.push(`<ul>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ul>`);
			continue;
		}
		if (/^\s*\d+[.)]\s+/.test(line)) {
			const items = [];
			while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*\d+[.)]\s+/, ""));
			i--;
			out.push(`<ol>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ol>`);
			continue;
		}
		const heading = line.match(/^#{1,4}\s+(.*)$/);
		if (heading) {
			out.push(`<p><strong>${inline(heading[1])}</strong></p>`);
			continue;
		}
		out.push(line.trim() ? `<p>${inline(line)}</p>` : "");
	}
	return out.join("");
}

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
			this.page.add_inner_button(__("Agent Studio"), () => frappe.set_route("agent-registry"));
		}
		frappe.realtime.on("assistant_update", ({ conversation } = {}) => {
			if (!document.body.contains(this.root)) return;
			if (conversation === this.current) this.scheduleReload();
			else this.loadList();
		});
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	// ---------------------------------------------------------------- data

	async show() {
		const [, name] = frappe.get_route();
		this.current = name || null;
		this.detail = null;
		this.info = await frappe.xcall(`${PA_API}.get_assistant`);
		this.conversations = this.info.conversations;
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
		const changed = this.detail?.state !== detail.state;
		this.detail = detail;
		this.renderMain();
		if (changed) this.loadList();
		// Realtime is the main signal; polling covers a dropped socket while the assistant works.
		clearTimeout(this.poll);
		if (detail.working) this.poll = setTimeout(() => document.body.contains(this.root) && this.loadDetail(), 3000);
	}

	scheduleReload() {
		clearTimeout(this.pending);
		this.pending = setTimeout(() => this.loadDetail(), 250);
	}

	open(name) {
		frappe.set_route(name ? ["procurement-assistant", name] : ["procurement-assistant"]);
	}

	async send(text) {
		text = (text || "").trim();
		if (!text || this.sending || this.detail?.working) return;
		this.sending = true;
		const conversation = this.current;
		this.draft = "";
		// Show the message straight away; the server copy replaces it on reload.
		const mine = { role: "user", kind: "text", content: text, choices: [] };
		if (this.detail) {
			this.detail.messages.forEach((m) => (m.choices = []));
			this.detail.messages.push(mine);
			this.detail.working = true;
		} else {
			this.detail = { name: null, state: "working", working: true, messages: [mine] };
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
			<aside class="pa-side" aria-label="${__("Your conversations")}"></aside>
			<section class="pa-main" aria-live="polite"></section>`;
		this.renderSide();
		this.renderMain();
	}

	renderSide() {
		const side = this.root.querySelector(".pa-side");
		if (!side) return;
		side.innerHTML = `
			<button type="button" class="btn btn-primary btn-sm pa-new"><i class="fa fa-plus" aria-hidden="true"></i> ${__("New conversation")}</button>
			<div class="pa-side-title">${__("Your conversations")}</div>
			<nav class="pa-list">
				${this.conversations.length ? this.conversations.map((c) => {
					const [label, tone] = PA_STATE[c.state] || PA_STATE.open;
					return `<button type="button" class="pa-item ${c.name === this.current ? "is-active" : ""}" data-name="${this.esc(c.name)}">
						<span class="pa-item-title">${this.esc(c.title || __("Conversation"))}</span>
						<span class="pa-item-meta">${label ? `<span class="pa-dot pa-tone-${tone}"></span>${__(label)} · ` : ""}${c.last_activity ? frappe.datetime.comment_when(c.last_activity, true) : ""}</span>
					</button>`;
				}).join("") : `<p class="pa-muted">${__("Nothing yet. Your conversations will appear here.")}</p>`}
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
			${d?.pinned_question ? this.renderPinned(d.pinned_question) : ""}
			${this.renderComposer(d)}`;
		this.bindMain(main);
		const thread = main.querySelector(".pa-thread");
		thread.scrollTop = thread.scrollHeight;
	}

	renderHeader(d) {
		const [label, tone] = PA_STATE[d.state] || PA_STATE.open;
		return `<header class="pa-head">
			<div class="pa-head-title">${this.esc(d.title || "")}</div>
			${label ? `<span class="pa-pill pa-tone-${tone}">${__(label)}</span>` : ""}
			${d.can_cancel_run ? `<button type="button" class="btn btn-default btn-xs pa-cancel">${__("Cancel purchase request")}</button>` : ""}
		</header>`;
	}

	renderWelcome() {
		const info = this.info || {};
		const name = frappe.boot.user.first_name || frappe.session.user_fullname || "";
		return `<div class="pa-welcome">
			<div class="pa-avatar pa-avatar-lg"><i class="fa fa-magic" aria-hidden="true"></i></div>
			<h2>${__("Hi {0}, how can I help?", [this.esc(name)])}</h2>
			<p>${__("Ask me about purchase orders, material requests, invoices, suppliers, items and stock, or tell me what you need to buy. I'll find suppliers, help set up anything that's missing, and prepare a request for quotation for approval.")}</p>
			${info.available ? `<div class="pa-suggestions">${(info.suggestions || []).map((s) => `<button type="button" class="pa-chip" data-text="${this.esc(s)}">${this.esc(s)}</button>`).join("")}</div>`
			: `<div class="pa-notice pa-tone-warn">${this.esc(info.reason)}</div>`}
			${info.test_mode ? `<p class="pa-muted">${__("Test mode: the assistant is not live yet, so only administrators can use it.")}</p>` : ""}
		</div>`;
	}

	renderMessages(d) {
		const rows = d.messages.map((m) => this.renderMessage(m)).join("");
		const typing = d.working ? `<div class="pa-row pa-row-assistant"><div class="pa-avatar"><i class="fa fa-magic" aria-hidden="true"></i></div><div class="pa-typing" role="status" aria-label="${__("Working")}"><span></span><span></span><span></span></div></div>` : "";
		return rows + typing;
	}

	renderMessage(m) {
		if (m.role === "user") {
			return `<div class="pa-row pa-row-user"><div class="pa-bubble pa-bubble-user">${this.esc(m.content).replace(/\n/g, "<br>")}</div></div>`;
		}
		if (m.kind === "notice") {
			return `<div class="pa-row pa-row-notice"><i class="fa fa-check-circle" aria-hidden="true"></i> ${this.esc(m.content)}</div>`;
		}
		return `<div class="pa-row pa-row-assistant">
			<div class="pa-avatar"><i class="fa fa-magic" aria-hidden="true"></i></div>
			<div class="pa-stack">
				<div class="pa-bubble pa-md ${m.kind === "error" ? "pa-bubble-error" : ""}">${paMarkdown(m.content)}</div>
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

	renderPinned(question) {
		const first = (question.text || "").split("\n").filter(Boolean).slice(-1)[0] || "";
		return `<div class="pa-pinned" role="status">
			<div class="pa-pinned-text"><i class="fa fa-hourglass-half" aria-hidden="true"></i> <strong>${__("Your purchase request is waiting for an answer:")}</strong> ${this.esc(first)}</div>
			${question.choices?.length ? `<div class="pa-suggestions">${question.choices.map((c) => `<button type="button" class="pa-chip" data-text="${this.esc(c)}">${this.esc(c)}</button>`).join("")}</div>` : ""}
		</div>`;
	}

	renderComposer(d) {
		const available = this.info?.available;
		const working = d?.working;
		const placeholder = working ? __("One moment, I'm working on it…") : __("Ask a question or describe what you need…");
		const disabled = working || this.sending || !available;
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
		main.querySelector(".pa-cancel")?.addEventListener("click", () =>
			frappe.confirm(__("Cancel the open purchase request? Nothing more will be done for it."), async () => {
				await frappe.xcall(`${PA_API}.cancel_sourcing`, { conversation: this.current });
				this.loadDetail();
			})
		);
	}
}
