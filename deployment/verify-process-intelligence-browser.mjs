import assert from "node:assert/strict";
import fs from "node:fs/promises";

const base = "http://process-intelligence.localhost:8000";
const debuggerUrl = "http://127.0.0.1:9225";
const output = "documentation/process-intelligence/evidence/browser";
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const results = { checked_at: new Date().toISOString(), site: base, checks: [], screenshots: [] };
const targets = await (await fetch(`${debuggerUrl}/json`)).json();
const target = targets.find((item) => item.type === "page" && item.url.startsWith(`${base}/`));
assert.ok(target, "Open the isolated local site in a separate Chrome profile on port 9225 first.");
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let sequence = 0;
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
socket.addEventListener("message", ({ data }) => {
	const message = JSON.parse(data);
	if (message.method === "Runtime.exceptionThrown") {
		(results.runtime_errors ||= []).push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
	}
	const request = pending.get(message.id);
	if (!request) return;
	pending.delete(message.id);
	clearTimeout(request.timer);
	if (message.error) request.reject(new Error(message.error.message));
	else request.resolve(message.result);
});
function send(method, params = {}) {
	return new Promise((resolve, reject) => {
		const id = ++sequence;
		const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, 180000);
		pending.set(id, { resolve, reject, timer });
		socket.send(JSON.stringify({ id, method, params }));
	});
}
async function evaluate(expression) {
	const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
	if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
	return result.result.value;
}
async function waitFor(expression, timeout = 60000) {
	const deadline = Date.now() + timeout;
	while (Date.now() < deadline) {
		try { if (await evaluate(expression)) return; } catch {}
		await delay(200);
	}
	throw new Error(`Timed out: ${expression}`);
}
async function check(name, expression) {
	assert.equal(await evaluate(expression), true, name);
	results.checks.push(name);
	console.log(`PASS: ${name}`);
}
async function click(selector) {
	const point = await evaluate(`(() => {
		const element = [...document.querySelectorAll(${JSON.stringify(selector)})].find(item => item.getClientRects().length && !item.disabled);
		if (!element) throw new Error('No visible enabled element: ' + ${JSON.stringify(selector)});
		element.scrollIntoView({ block: 'center', inline: 'center' });
		const rect = element.getBoundingClientRect();
		return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
	})()`);
	await send("Input.dispatchMouseEvent", { type: "mousePressed", button: "left", clickCount: 1, ...point });
	await send("Input.dispatchMouseEvent", { type: "mouseReleased", button: "left", clickCount: 1, ...point });
}
async function key(key, code, virtualKey, modifiers = 0) {
	const params = { key, code, windowsVirtualKeyCode: virtualKey, modifiers };
	await send("Input.dispatchKeyEvent", { type: "keyDown", ...params });
	await send("Input.dispatchKeyEvent", { type: "keyUp", ...params });
}
async function type(selector, value) {
	await click(selector);
	await key("a", "KeyA", 65, 2);
	await send("Input.insertText", { text: value });
}
async function navigate(route) {
	await send("Page.navigate", { url: `${base}${route}` });
	await waitFor("document.readyState === 'complete'");
}
async function screenshot(name, selector) {
	if (selector) await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`);
	else await evaluate("window.scrollTo(0, 0)");
	await delay(250);
	const image = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
	await fs.writeFile(`${output}/${name}.png`, Buffer.from(image.data, "base64"));
	results.screenshots.push(`${name}.png`);
}
async function layout(name) {
	const state = await evaluate(`(() => ({
		width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
		theme: document.documentElement.dataset.theme,
		active: [...document.querySelectorAll('.pridict-app-rail-link.is-active')].map(element => element.dataset.pridictModule),
		context: window.pridict?.routeContext?.classify(),
		filters: document.querySelector('.pi-filters')?.getBoundingClientRect().toJSON(),
		background: document.querySelector('.pi-panel') ? getComputedStyle(document.querySelector('.pi-panel')).backgroundColor : null
	}))()`);
	(results.layouts ||= {})[name] = state;
	assert.ok(state.scrollWidth <= state.width + 1, `${name}: horizontal page overflow`);
	if (state.filters) assert.ok(state.filters.left >= 0 && state.filters.right <= state.width, `${name}: clipped analysis panel`);
	results.checks.push(`${name}: no page overflow`);
}
async function scope(start, end) {
	await evaluate(`(() => {
		for (const [name, value] of Object.entries(${JSON.stringify({ start_date: start, end_date: end })})) {
			const input = document.querySelector('.pi-filters [name="' + name + '"]');
			input.value = value; input.dispatchEvent(new Event('change', {bubbles:true}));
		}
	})()`);
}
async function analyze() {
	await click(".pi-filters [type=submit]");
	await waitFor("!!document.querySelector('.pi-result-heading')", 180000);
}
async function login(user) {
	await send("Network.clearBrowserCookies");
	await navigate("/login");
	await waitFor("!!document.querySelector('#login_email')");
	await type("#login_email", user);
	await type("#login_password", process.env.PI_DEMO_PASSWORD || "Local-PI-Demo-2026!");
	await click(".btn-login");
	await waitFor("location.pathname.startsWith('/app') && !!window.frappe?.boot");
}
async function sharedUI() {
	await login("pi.reviewer@example.test");
	const routes = [
		["website", "website", "workspace"],
		["workflow-state", "administration", "list"],
		["sales-invoice", "sales", "list"],
		["purchase-order", "procurement", "list"],
		["stock-entry", "inventory", "list"],
		["query-report/General Ledger", "finance", "report"],
	];
	for (const [width, theme] of [[1440, "light"], [390, "dark"]]) {
		await send("Emulation.setDeviceMetricsOverride", { width, height: width === 390 ? 844 : 1000, deviceScaleFactor: 1, mobile: width === 390 });
		for (const [route, module, surface] of routes) {
			await navigate(`/app/${route}`);
			await waitFor(`document.documentElement.dataset.pridictModule === ${JSON.stringify(module)} && document.documentElement.dataset.pridictSurface === ${JSON.stringify(surface)}`);
			await evaluate(`frappe.ui.set_theme(${JSON.stringify(theme)})`);
			await waitFor(`document.documentElement.dataset.theme === ${JSON.stringify(theme)}`);
			await delay(1200);
			const name = `ui-${route.replaceAll("/", "-").replaceAll(" ", "-")}-${width}-${theme}`;
			await check(`${name}: correct module navigation`, `document.querySelector('.pridict-app-rail-link.is-active')?.dataset.pridictModule === ${JSON.stringify(module)}`);
			await check(`${name}: no visible route error`, "!/not permitted|not found|internal server error/i.test(document.body.innerText)");
			await check(`${name}: no duplicated page context`, "[...document.querySelectorAll('.pridict-has-breadcrumbs > .pridict-page-context')].every(element => !element.getClientRects().length)");
			await layout(name);
			if (route === "website") {
				await check(`${name}: native workspace sidebar removed`, "[...document.querySelectorAll('.layout-side-section')].every(element => !element.getClientRects().length || element.getBoundingClientRect().width === 0)");
			}
			if (["sales-invoice", "purchase-order"].includes(route)) {
				await waitFor("!!window.cur_list?.filter_area && !!document.querySelector('.pridict-list-context')");
				await check(`${name}: one compact quick-filter row`, "document.querySelectorAll('.pridict-list-context').length === 1 && !document.querySelector('.pridict-list-context p')");
				const preset = route === "sales-invoice" ? "[data-sales-list-filter]" : "[data-pridict-list-filter]";
				await click(preset);
				await waitFor("window.cur_list.filter_area.get().length > 0");
				await check(`${name}: preset applies without route change`, "window.cur_list.filter_area.get().length > 0");
				await click(route === "sales-invoice" ? "[data-sales-list-all]" : "[data-pridict-list-all]");
				await waitFor("window.cur_list.filter_area.get().length === 0");
				results.checks.push(`${name}: All clears preset filters`);
			}
			await screenshot(name);
		}
		await check(`ui-${width}: notification trigger stays compact`, "document.querySelector('.dropdown-notifications').getBoundingClientRect().width < 80");
		await click(".dropdown-notifications .notifications-icon");
		await waitFor("document.querySelector('.dropdown-notifications .dropdown-menu').getClientRects().length > 0");
		await check(`ui-${width}: notification dropdown remains onscreen`, "(() => {const rect=document.querySelector('.dropdown-notifications .dropdown-menu').getBoundingClientRect();return rect.left >= 0 && rect.right <= innerWidth;})()");
		await screenshot(`ui-notifications-${width}-${theme}`);
		await key("Escape", "Escape", 27);
	}
}
async function suite() {
	await send("Page.enable");
	await send("Runtime.enable");
	await send("Network.enable");
	await send("Network.setCacheDisabled", { cacheDisabled: true });
	await send("Emulation.setDeviceMetricsOverride", { width: Number(process.env.PI_WIDTH || 1440), height: 1000, deviceScaleFactor: 1, mobile: process.env.PI_WIDTH === "390" });
	if (process.env.PI_INSPECT) {
		console.log(JSON.stringify(await evaluate(process.env.PI_INSPECT), null, 2));
		return;
	}
	if (process.env.PI_MODE === "ui") return sharedUI();
	await login("pi.analyst@example.test");
	await waitFor("!!document.querySelector('.pridict-app-rail-link[data-route=\"process-intelligence\"]')");
	await click('.pridict-app-rail-link[data-route="process-intelligence"]');
	await waitFor("!!document.querySelector('.pi-filters')");
	await check("Ordinary analyst navigates to permission-controlled page", "location.pathname === '/app/process-intelligence' && document.querySelector('.pi-filters select').options.length === 1");
	await scope("2026-10-02", "2026-10-02");
	await screenshot("initial-desktop");
	await click(".pi-filters [name=company]");
	await key("Escape", "Escape", 27);
	await key("Tab", "Tab", 9);
	await check("Company to creation-date keyboard navigation", "document.activeElement.name === 'start_date'");
	await click(".pi-filters [type=submit]");
	await waitFor("!!document.querySelector('.pi-results [role=status]')");
	await check("Loading state disables scope controls", "[...document.querySelectorAll('.pi-filters input, .pi-filters select, .pi-filters button')].every(element => element.disabled)");
	await screenshot("loading-desktop");
	await waitFor("!!document.querySelector('.pi-result-heading')", 180000);
	await check("Real linked flow: seven documents, ten links, one journey", "JSON.stringify([...document.querySelectorAll('.pi-metrics strong')].map(element => element.textContent)) === JSON.stringify(['7','10','1','0'])");
	await check("Graph, timeline and unknown metrics remain distinct", "document.querySelectorAll('.pi-node-count').length === 7 && document.querySelectorAll('.pi-timeline li').length === 7 && document.querySelectorAll('.pi-unsupported dd').length === 4 && [...document.querySelectorAll('.pi-unsupported dd')].every(element => element.textContent === 'Data not available')");
	await click(".pi-journey-button");
	await check("Journey selection", "document.querySelector('.pi-journey-button').getAttribute('aria-pressed') === 'true'");
	await check("Journey selection retains keyboard focus", "document.activeElement.classList.contains('pi-journey-button')");
	await key("Enter", "Enter", 13);
	await check("Journey can be selected with keyboard", "document.activeElement.getAttribute('aria-pressed') === 'true'");
	await click(".pi-graph + details summary");
	await check("Equivalent graph connection table opens", "document.querySelector('.pi-graph + details').open && document.querySelectorAll('.pi-graph + details tbody tr').length > 0");
	await click(".pi-history summary");
	await check("Historical evidence disclosure opens", "document.querySelector('.pi-history').open");
	await type(".pi-search", "no-matching-document");
	await check("Journey search empty state", "document.querySelector('.pi-journeys').textContent.includes('No matching journeys.') && document.querySelector('.pi-journey-detail').textContent === ''");
	await type(".pi-search", "PUR-ORD");
	await check("Journey search matches document number", "document.querySelectorAll('.pi-journey-button').length === 1 && document.querySelectorAll('.pi-timeline li').length === 7");
	await type(".pi-search", "");
	for (const theme of ["light", "dark"]) {
		await evaluate(`frappe.ui.set_theme(${JSON.stringify(theme)})`);
		await waitFor(`document.documentElement.dataset.theme === ${JSON.stringify(theme)}`);
		for (const width of [1440, 390]) {
			await send("Emulation.setDeviceMetricsOverride", { width, height: width === 390 ? 844 : 1000, deviceScaleFactor: 1, mobile: width === 390 });
			await delay(400);
			const name = `${theme}-${width}`;
			await layout(name);
			await screenshot(`${name}-results`);
			await screenshot(`${name}-graph`, ".pi-graph");
			await screenshot(`${name}-journey`, ".pi-journey-detail");
			await screenshot(`${name}-limits`, ".pi-evidence-grid");
		}
	}
	await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
	const links = await evaluate("[...document.querySelectorAll('.pi-timeline a')].map(element => ({href:element.getAttribute('href'), name:element.textContent.replace('↗','').trim()}))");
	for (const link of links) {
		const before = new Set((await send("Target.getTargets")).targetInfos.map(item => item.targetId));
		await click(`.pi-timeline a[href=${JSON.stringify(link.href)}]`);
		let opened;
		for (let attempt = 0; attempt < 50 && !opened; attempt++) {
			opened = (await send("Target.getTargets")).targetInfos.find(item => !before.has(item.targetId) && item.url.startsWith(base + link.href));
			if (!opened) await delay(200);
		}
		assert.ok(opened, `Supporting document opens: ${link.name}`);
		results.checks.push(`Supporting document opens in new tab: ${link.name}`);
		await send("Target.closeTarget", { targetId: opened.targetId });
	}
	await scope("2026-10-03", "2026-10-02");
	await click(".pi-filters [type=submit]");
	await check("Invalid date range is explained", "document.querySelector('.pi-notice')?.textContent.includes('on or before') === true");
	await screenshot("invalid-date-range");
	await scope("2000-01-01", "2000-01-01");
	await analyze();
	await check("Real empty date scope", "document.querySelector('.pi-results').textContent.includes('No visible purchasing documents in this scope') && document.querySelectorAll('.pi-timeline li').length === 0");
	await screenshot("empty-date-scope");
	await scope("2026-10-02", "2026-10-02");
	await send("Network.setBlockedURLs", { urls: ["*purchasing_screen.get_analysis*"] });
	try {
		await click(".pi-filters [type=submit]");
		await waitFor("!!document.querySelector('.pi-results [role=alert]')");
		await check("Controlled network failure restores retry controls", "document.querySelector('.pi-results').textContent.includes('Analysis could not be loaded') && !document.querySelector('.pi-filters button').disabled");
		await screenshot("controlled-network-error");
	} finally { await send("Network.setBlockedURLs", { urls: [] }); }
	await analyze();
	await check("Recovery after network failure", "document.querySelectorAll('.pi-timeline li').length === 7");
	await login("pi.noaccess@example.test");
	await check("Analysis navigation hidden without role", "!document.querySelector('.pridict-app-rail-link[data-route=\"process-intelligence\"]')");
	await navigate("/app/process-intelligence");
	await waitFor("/not permitted|not allowed|permission|Process Intelligence is unavailable/i.test(document.body.innerText)");
	await check("Direct page entry denied without role", "!document.querySelector('.pi-filters') && !document.querySelector('.pi-timeline')");
	await screenshot("role-denied");
	await login("pi.analyst@example.test");
	await navigate("/app/pridict-procurement");
	await waitFor("!![...document.querySelectorAll('.page-head button')].find(element => element.textContent.trim() === 'Process Intelligence')");
	const button = await evaluate("[...document.querySelectorAll('.page-head button')].find(element => element.textContent.trim() === 'Process Intelligence').getAttribute('data-label')");
	await click(`.page-head button[data-label=${JSON.stringify(button)}]`);
	await waitFor("!!document.querySelector('.pi-filters')");
	await check("Procurement toolbar opens analysis", "location.pathname === '/app/process-intelligence'");
}

await fs.mkdir(output, { recursive: true });
try {
	await suite();
	results.status = "passed";
} catch (error) {
	results.status = "failed";
	results.failure = error.message;
	results.failure_state = await evaluate("({url:location.href,text:document.body.innerText.slice(0,5000)})").catch(() => null);
	await screenshot("failure").catch(() => {});
	console.error(error);
	process.exitCode = 1;
} finally {
	if (!process.env.PI_INSPECT) await fs.writeFile(`${output}/${process.env.PI_MODE === "ui" ? "ui-verification" : "verification"}.json`, JSON.stringify(results, null, 2) + "\n");
	socket.close();
}
