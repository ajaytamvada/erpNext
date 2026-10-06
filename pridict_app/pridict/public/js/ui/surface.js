(() => {
	const namespace = (window.pridict = window.pridict || {});
	function escape(value) { return window.frappe?.utils?.escape_html?.(String(value ?? "")) || String(value ?? ""); }
	function visiblePage() { return [...document.querySelectorAll(".page-container")].find((element) => element.offsetParent !== null) || null; }
	function render(element, html) { if (element && element.innerHTML !== html) element.innerHTML = html; }
	function ensureIntro(page, className, eyebrow, title, description) {
		let block = page.querySelector(`.${className}`);
		if (!block) { block = document.createElement("section"); block.className = className; page.querySelector(".page-body .container, .page-body")?.prepend(block); }
		render(block, `<span>${__(eyebrow)}</span><strong>${__(title)}</strong><p>${__(description)}</p>`);
		return block;
	}
	function ensureJourney(page, options) {
		let nav = page.querySelector(`.${options.className}`);
		if (!nav) { nav = document.createElement("nav"); nav.className = options.className; nav.setAttribute("aria-label", __(options.label)); nav.innerHTML = options.items.map(([label, route]) => `<button type="button" data-route="${route}">${__(label)}</button>`).join(""); nav.onclick = (event) => { const button = event.target.closest("[data-route]"); if (button) frappe.set_route(button.dataset.route); }; page.querySelector(".page-head")?.insertAdjacentElement("afterend", nav); }
		return nav;
	}
	function ensureListContext(page, options) {
		let block = page.querySelector(`.${options.className}`);
		if (!block) {
			block = document.createElement("section");
			block.className = options.className;
			page.querySelector(".page-body .container, .page-body")?.prepend(block);
		}
		block.classList.add("pridict-list-context");
		block.setAttribute("aria-label", __(options.label || "Quick filters"));
		render(block, `<span class="pridict-list-context-label">${escape(__(options.label || "Quick filters"))}</span><div class="pridict-list-context-actions ${escape(options.actionsClass || "")}">${options.actions || ""}</div>`);
		return block;
	}
	function applyListFilters(doctype, filters = {}) {
		const list = window.cur_list;
		if (list?.doctype === doctype && list.filter_area && list.parse_filters_from_route_options) {
			frappe.route_options = filters;
			const parsedFilters = list.parse_filters_from_route_options();
			frappe.route_options = null;
			return list.filter_area.clear(false).then(() => list.filter_area.add(parsedFilters));
		}
		frappe.route_options = filters;
		frappe.set_route("List", doctype, "List");
		return Promise.resolve();
	}
	function remove(selectors) { document.querySelectorAll(selectors).forEach((element) => element.remove()); }
	namespace.surface = { escape, visiblePage, render, ensureIntro, ensureJourney, ensureListContext, applyListFilters, remove };
})();
