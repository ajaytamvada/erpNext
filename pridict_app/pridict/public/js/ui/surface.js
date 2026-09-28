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
	function remove(selectors) { document.querySelectorAll(selectors).forEach((element) => element.remove()); }
	namespace.surface = { escape, visiblePage, render, ensureIntro, ensureJourney, remove };
})();
