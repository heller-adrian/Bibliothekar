const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");

const html = fs.readFileSync(process.argv[2], "utf8");
const origin = "http://bibliothekar.test";
const items = Array.from({length: 23}, (_, index) => ({
  event_id: String(index), released: true, name: "Event " + index,
  folder_name: "Event " + index, event_created_at: "2026-11-27",
  current_archive: {available: true, file_count: 3, family_count: 1},
}));

async function test(browser, lang, width) {
  const page = await browser.newPage({viewport: {width, height: 900}});
  await page.addInitScript(({lang, width}) => {
    localStorage.setItem("bibliothekar-language", lang);
    localStorage.setItem("bibliothekar-theme", width < 600 ? "dark" : "light");
  }, {lang, width});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  let posts = 0;
  let state = {status: "idle", last_success_at: null};
  await page.route(origin + "/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/transfer") return route.fulfill({body: html, contentType: "text/html"});
    if (url.pathname === "/api/archive/summary") {
      const before = url.searchParams.get("event_id");
      const start = before === null ? 0 : Number(before) + 1;
      const end = start + 10;
      return route.fulfill({json: {
        archive_readable: true, candidate_count: 0, blocked_count: 0, verified_count: 0, released_count: 23,
        candidates: items.slice(start, end),
        history_next_cursor: end < items.length ? {created_at: "2026-11-27", event_id: String(end - 1)} : null,
      }});
    }
    if (url.pathname === "/api/settings/archive-inventory") {
      if (route.request().method() === "POST") {
        posts += 1;
        state = {id: "scan", status: "running", phase: "hashing", checked: 3, total: 23, percent: 13, eta_seconds: null};
      }
      return route.fulfill({json: state});
    }
    if (url.pathname === "/api/operations/status")
      return route.fulfill({json: {writes_allowed: true, workspace_writes_allowed: true, issues: [], reservations: []}});
    if (url.pathname.startsWith("/api/"))
      return route.fulfill({json: {tasks: [], libraries: [], count: 0, operations: []}});
    return route.fulfill({body: ""});
  });

  await page.goto(origin + "/transfer");
  const more = page.locator("#archive-history-more");
  await more.waitFor({state: "visible"});
  assert.equal(await page.locator("#history-list article").count(), 10);
  assert.equal(await page.locator("#released-count").innerText(), "23");
  await more.click();
  await page.waitForFunction(() => document.querySelectorAll("#history-list article").length === 20);
  await more.click();
  await more.waitFor({state: "hidden"});
  assert.deepEqual(await page.locator("#history-list article .title [data-bk-preserve-language]").allTextContents(),
    items.map(item => item.name));

  async function openGeneral() {
    await page.locator("[data-bk-open-settings]").evaluate(button => button.click());
    await page.locator('[data-bk-settings-area="general"]').click();
  }
  await openGeneral();
  const scan = page.locator("#bk-archive-scan-start");
  const status = page.locator("#bk-archive-scan-state");
  await scan.click();
  const progress = page.locator("#bk-archive-scan-progress");
  await progress.waitFor({state: "visible"});
  assert.equal(await progress.getAttribute("value"), "13");
  assert.match(await status.innerText(), lang === "de" ? /Wird berechnet/ : /Calculating/);
  await page.reload();
  await openGeneral();
  await progress.waitFor({state: "visible"});
  assert.equal(await scan.isDisabled(), true);
  assert.equal(posts, 1);

  state = {...state, status: "completed", checked: 23, percent: 100, last_success_at: "2026-11-27T18:00:00Z",
    result: {changed: 1}};
  await progress.waitFor({state: "hidden"});
  assert.match(await status.innerText(), lang === "de" ? /Scan abgeschlossen/ : /Scan complete/);
  assert.equal(await scan.isEnabled(), true);
  assert.match(await page.locator("#bk-archive-scan-result").innerText(),
    lang === "de" ? /Inhalt geändert 1/ : /Content changed 1/);
  assert.deepEqual(errors, []);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
  });
  try {
    await test(browser, "de", 390);
    await test(browser, "en", 1280);
    console.log("Archive history and archive inventory settings passed on mobile and desktop.");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
