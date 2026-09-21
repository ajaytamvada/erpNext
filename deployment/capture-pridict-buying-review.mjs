import fs from "node:fs/promises";
import path from "node:path";

const options = Object.fromEntries(
  process.argv.slice(2).map((argument) => {
    const separator = argument.indexOf("=");
    if (separator === -1) return [argument, true];
    return [argument.slice(0, separator), argument.slice(separator + 1)];
  }),
);

const debuggerUrl = options.debuggerUrl || "http://127.0.0.1:9224";
const baseUrl = options.baseUrl || "http://127.0.0.1:8000";
const username = options.username;
const password = options.password;
const outputDirectory = path.resolve(options.output || "design/review-20260921/restricted");
const viewportWidth = Number(options.width || 1440);
const viewportHeight = Number(options.height || 1000);
const purchaseOrder = options.purchaseOrder || "PUR-ORD-2026-00001";
const screenSet = options.screenSet || "buying";
const themes = (options.themes || "light,dark").split(",");

if (!username || !password) {
  throw new Error("username and password arguments are required");
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function getPageTarget() {
  const response = await fetch(`${debuggerUrl}/json`);
  if (!response.ok) throw new Error(`Unable to query Chrome: HTTP ${response.status}`);
  const targets = await response.json();
  const target = targets.find(
    (candidate) => candidate.type === "page" && candidate.url.startsWith(baseUrl),
  );
  if (!target) throw new Error(`No page target for ${baseUrl}`);
  return target;
}

class CdpClient {
  constructor(webSocketUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.socket = new WebSocket(webSocketUrl);
  }

  async connect() {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("CDP connection timed out")), 10000);
      this.socket.addEventListener("open", () => {
        clearTimeout(timeout);
        resolve();
      });
      this.socket.addEventListener("error", (event) => {
        clearTimeout(timeout);
        reject(event.error || new Error("CDP connection failed"));
      });
      this.socket.addEventListener("message", (event) => {
        const message = JSON.parse(event.data);
        if (!message.id || !this.pending.has(message.id)) return;
        const { resolve: resolveCommand, reject: rejectCommand, timeout: commandTimeout } =
          this.pending.get(message.id);
        clearTimeout(commandTimeout);
        this.pending.delete(message.id);
        if (message.error) rejectCommand(new Error(message.error.message));
        else resolveCommand(message.result);
      });
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out`));
      }, 30000);
      this.pending.set(id, { resolve, reject, timeout });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    this.socket.close();
  }
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  }
  return result.result.value;
}

async function waitFor(client, expression, timeoutMilliseconds = 30000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    try {
      if (await evaluate(client, expression)) return;
    } catch {
      // Navigation briefly invalidates the JavaScript execution context.
    }
    await delay(250);
  }
  throw new Error(`Timed out waiting for: ${expression}`);
}

async function navigate(client, route) {
  await client.send("Page.navigate", { url: `${baseUrl}${route}` });
  await waitFor(client, "document.readyState === 'complete'");
  await waitFor(
    client,
    "!Array.from(document.querySelectorAll('.freeze, .loading-screen')).some((element) => element.offsetParent !== null && getComputedStyle(element).visibility !== 'hidden')",
  );
  await delay(1500);
}

async function setTheme(client, theme) {
  await evaluate(
    client,
    `(() => {
      document.documentElement.setAttribute('data-theme-mode', ${JSON.stringify(theme)});
      if (window.frappe?.ui?.set_theme) window.frappe.ui.set_theme(${JSON.stringify(theme)});
      else document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
      return true;
    })()`,
  );
  await waitFor(
    client,
    `document.documentElement.getAttribute('data-theme') === ${JSON.stringify(theme)}`,
  );
  await delay(1500);
}

async function capture(client, screen, theme) {
  await navigate(client, screen.route);
  await setTheme(client, theme);
  if (screen.beforeCapture) {
    await evaluate(client, screen.beforeCapture);
    await delay(750);
  }

  const state = await evaluate(
    client,
    `(() => ({
      title: document.title,
      url: location.href,
      theme: document.documentElement.getAttribute('data-theme'),
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyText: document.body.innerText.slice(0, 1200),
      hasPridict: /Pridict/i.test(document.body.innerText),
      upstreamVisible: /(Frappe School|ERPNext documentation|Powered by ERPNext)/i.test(document.body.innerText),
      upstreamLinks: Array.from(document.querySelectorAll('a[href]'))
        .map((link) => link.href)
        .filter((href) => /(?:docs\.erpnext\.com|docs\.frappe\.io\\/erpnext)/i.test(href)),
      upstreamTourDescriptions: Object.values(window.frappe?.tour || {})
        .flatMap((steps) => Array.isArray(steps) ? steps : [])
        .map((step) => step?.description || '')
        .filter((description) => /(?:docs\.erpnext\.com|docs\.frappe\.io\\/erpnext)/i.test(description)),
      errorVisible: /(?:not found|not permitted|permission error|server error|internal server error)/i.test(
        document.body.innerText,
      ),
      firstDataRow: (() => {
        const row = document.querySelector('.list-row-container .list-row');
        if (!row) return null;
        return Array.from(row.querySelectorAll('.list-row-col, .level-left, .level-right, .list-subject, .indicator-pill'))
          .filter((element) => element.offsetParent !== null)
          .map((element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return {
              className: element.className,
              text: element.innerText?.trim().slice(0, 120),
              x: Math.round(rect.x),
              y: Math.round(rect.y),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
              display: style.display,
              position: style.position,
              overflow: style.overflow,
              boxSizing: style.boxSizing,
              maxWidth: style.maxWidth,
              cssWidth: style.width,
              flex: style.flex,
              justifyContent: style.justifyContent,
              marginLeft: style.marginLeft,
              marginRight: style.marginRight,
              transform: style.transform
            };
          });
      })()
    }))()`,
  );

  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  const filename = `${screen.name}-${theme}.png`;
  await fs.writeFile(path.join(outputDirectory, filename), Buffer.from(screenshot.data, "base64"));

  return {
    screen: screen.name,
    theme,
    route: screen.route,
    file: path.join(outputDirectory, filename),
    ...state,
    horizontalOverflow: state.scrollWidth > state.width,
  };
}

await fs.mkdir(outputDirectory, { recursive: true });
const target = await getPageTarget();
const client = new CdpClient(target.webSocketDebuggerUrl);
await client.connect();

try {
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Network.enable");
  await client.send("Network.setCacheDisabled", { cacheDisabled: true });
  await client.send("Emulation.setUserAgentOverride", {
    userAgent:
      viewportWidth <= 600
        ? "Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
        : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    platform: viewportWidth <= 600 ? "Android" : "Windows",
  });
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: viewportWidth,
    height: viewportHeight,
    deviceScaleFactor: 1,
    mobile: viewportWidth <= 600,
  });

  await navigate(client, "/api/method/logout");
  await navigate(client, "/login");
  await evaluate(
    client,
    `(() => {
      const username = document.querySelector('#login_email');
      const password = document.querySelector('#login_password');
      if (!username || !password) return false;
      username.value = ${JSON.stringify(username)};
      password.value = ${JSON.stringify(password)};
      username.dispatchEvent(new Event('input', { bubbles: true }));
      password.dispatchEvent(new Event('input', { bubbles: true }));
      document.querySelector('.btn-login')?.click();
      return true;
    })()`,
  );
  await waitFor(client, "location.pathname.startsWith('/app')", 45000);

  const screens = screenSet === "contextual-help"
    ? [
        { name: "accounts-settings", route: "/app/accounts-settings" },
        { name: "payment-reconciliation", route: "/app/payment-reconciliation" },
        { name: "process-payment-reconciliation", route: "/app/process-payment-reconciliation" },
        { name: "selling-settings", route: "/app/selling-settings" },
        { name: "item", route: "/app/item/new-item-1" },
        { name: "stock-settings", route: "/app/stock-settings" },
        { name: "stock-entry", route: "/app/stock-entry/new-stock-entry-1" },
      ]
    : screenSet === "all-modules"
      ? [
          { name: "accounting", route: "/app/accounting" },
          { name: "assets", route: "/app/assets" },
          { name: "build", route: "/app/build" },
          { name: "buying", route: "/app/buying" },
          { name: "crm", route: "/app/crm" },
          { name: "erpnext-integrations", route: "/app/erpnext-integrations" },
          { name: "pridict-settings", route: "/app/erpnext-settings" },
          { name: "financial-reports", route: "/app/financial-reports" },
          { name: "home", route: "/app/home" },
          { name: "integrations", route: "/app/integrations" },
          { name: "manufacturing", route: "/app/manufacturing" },
          { name: "payables", route: "/app/payables" },
          { name: "projects", route: "/app/projects" },
          { name: "quality", route: "/app/quality" },
          { name: "receivables", route: "/app/receivables" },
          { name: "selling", route: "/app/selling" },
          { name: "stock", route: "/app/stock" },
          { name: "support", route: "/app/support" },
          { name: "tools", route: "/app/tools" },
          { name: "users", route: "/app/users" },
          { name: "website", route: "/app/website" },
        ]
      : screenSet === "representative-pages"
        ? [
            { name: "sales-invoice-list", route: "/app/sales-invoice" },
            { name: "sales-invoice-form", route: "/app/sales-invoice/new-sales-invoice-1" },
            { name: "customer-list", route: "/app/customer" },
            { name: "customer-form", route: "/app/customer/new-customer-1" },
            { name: "item-list", route: "/app/item" },
            { name: "item-form", route: "/app/item/PRIDICT-QA-CHAIR" },
            { name: "supplier-list", route: "/app/supplier" },
            { name: "supplier-form", route: "/app/supplier/Pridict%20QA%20Office%20Supplies" },
            { name: "asset-list", route: "/app/asset" },
            { name: "asset-form", route: "/app/asset/new-asset-1" },
            { name: "bom-list", route: "/app/bom" },
            { name: "bom-form", route: "/app/bom/new-bom-1" },
            { name: "work-order-list", route: "/app/work-order" },
            { name: "work-order-form", route: "/app/work-order/new-work-order-1" },
            { name: "project-list", route: "/app/project" },
            { name: "project-form", route: "/app/project/_T-Project-00001" },
            { name: "task-list", route: "/app/task" },
            { name: "task-form", route: "/app/task/new-task-1" },
            { name: "quality-inspection-list", route: "/app/quality-inspection" },
            { name: "quality-inspection-form", route: "/app/quality-inspection/new-quality-inspection-1" },
            { name: "issue-list", route: "/app/issue" },
            { name: "issue-form", route: "/app/issue/new-issue-1" },
            { name: "user-list", route: "/app/user" },
            { name: "user-form", route: "/app/user/Administrator" },
            { name: "web-page-list", route: "/app/web-page" },
            { name: "web-page-form", route: "/app/web-page/new-web-page-1" },
            { name: "stock-entry-list", route: "/app/stock-entry" },
            { name: "stock-entry-form", route: "/app/stock-entry/MAT-STE-2026-00002" },
            { name: "delivery-note-list", route: "/app/delivery-note" },
            { name: "delivery-note-form", route: "/app/delivery-note/new-delivery-note-1" },
            { name: "purchase-invoice-list", route: "/app/purchase-invoice" },
            { name: "purchase-invoice-form", route: "/app/purchase-invoice/new-purchase-invoice-1" },
            { name: "general-ledger", route: "/app/query-report/General%20Ledger" },
            { name: "stock-ledger", route: "/app/query-report/Stock%20Ledger" },
            { name: "accounts-receivable", route: "/app/query-report/Accounts%20Receivable" },
            { name: "accounts-payable", route: "/app/query-report/Accounts%20Payable" },
            { name: "account-tree", route: "/app/account/view/tree" },
            { name: "event-calendar", route: "/app/event/view/calendar" },
            { name: "todo-kanban", route: "/app/todo/view/kanban" },
          ]
      : [
          { name: "buying-workspace", route: "/app/buying" },
          {
            name: "purchase-order-list",
            route:
              "/app/purchase-order?company=%5B%22%3D%22%2C%22_Test%20Company%22%5D&status=%5B%22in%22%2C%5B%22To%20Receive%22%2C%22To%20Receive%20and%20Bill%22%5D%5D",
          },
          {
            name: "purchase-order-form",
            route: `/app/purchase-order/${purchaseOrder}`,
            beforeCapture:
              'document.querySelector("[data-fieldname=items]")?.scrollIntoView({ block: "center" })',
          },
        ];

  const evidence = [];
  for (const screen of screens) {
    for (const theme of themes) {
      evidence.push(await capture(client, screen, theme));
    }
  }

  await fs.writeFile(
    path.join(outputDirectory, "capture-manifest.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  console.table(
    evidence.map(({ screen, theme, title, horizontalOverflow, upstreamVisible }) => ({
      screen,
      theme,
      title,
      horizontalOverflow,
      upstreamVisible,
    })),
  );
} finally {
  client.close();
}
