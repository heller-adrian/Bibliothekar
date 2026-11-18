// The actual Archive page and shell run against controlled endpoint responses.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const html = fs.readFileSync(process.argv[2], "utf8");
const origin = "http://bibliothekar.test";
const proof = "a".repeat(32);
const releaseId = "b".repeat(32);
const photo = {event_name: "Synthetic album", status: "queued", message: null};

async function check(browser, lang, width) {
  const page = await browser.newPage({viewport: {width, height: 800}});
  const en = lang === "en";
  const errors = [];
  const requests = [];
  let dashboard = {batch: null, active: false, candidate_count: 1, release_ready_count: 0};
  page.on("pageerror", error => errors.push(error.stack));
  await page.addInitScript(({lang, width}) => {
    localStorage.setItem("bibliothekar-language", lang);
    localStorage.setItem("bibliothekar-theme", width < 600 ? "dark" : "light");
  }, {lang, width});
  const summary = {archive_readable: true, candidate_count: 1, blocked_count: 0,
    verified_count: 0, released_count: 0, candidates: []};
  await page.route(origin + "/**", route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === "/archive") return route.fulfill({body: html, contentType: "text/html"});
    if (pathname === "/api/archive/summary") return route.fulfill({json: summary});
    if (pathname === "/api/archive/batch") return route.fulfill({json: dashboard});
    if (pathname === "/api/operations/status")
      return route.fulfill({json:{writes_allowed:true, workspace_writes_allowed:true, issues:[], reservations:[]}});
    if (pathname.endsWith("/api/archive/batch/verify")) {
      requests.push(["verify", request.postDataJSON()]);
      const batch = {id: proof, kind: "verify", status: "running", updated_at: "1",
        processed: 0, total: 1, items: [photo]};
      dashboard = {...dashboard, batch, active: true, active_kind: "verify"};
      return route.fulfill({status: 202, json: batch});
    }
    if (pathname.endsWith("/api/archive/batch/release")) {
      requests.push(["release", request.postDataJSON()]);
      const batch = {id: releaseId, kind: "release", status: "running", updated_at: "3",
        processed: 0, total: 1, items: [photo]};
      dashboard = {...dashboard, batch, active: true, active_kind: "release", release_ready_count: 0};
      return route.fulfill({status: 202, json: batch});
    }
    if (pathname === "/api/background-activity") {
      const batch = dashboard.batch;
      const operations = batch ? [{kind: "archive_batch", id: batch.id, status: batch.status,
        active: dashboard.active, label: batch.kind === "verify" ? "Alle prüfen" : "Alle Arbeitsbereiche freigeben",
        detail: batch.processed + " von " + batch.total + " Ereignissen verarbeitet",
        progress_percent: batch.processed * 100}] : [];
      return route.fulfill({json: {operations, active_count: dashboard.active ? 1 : 0}});
    }
    if (pathname === "/assets/bibliothekar-logo-v3.svg") {
      return route.fulfill({path:path.join(__dirname, "../../app/bibliothekar-logo-v3.svg")});
    }
    if (pathname.startsWith("/api/")) return route.fulfill({json: {tasks: [], libraries: [], count: 0}});
    return route.fulfill({body: ""});
  });
  const button = page.locator("#archive-batch-action");
  const status = page.locator("#archive-batch-status");
  await page.goto(origin + "/archive");
  const verify = page.getByRole("button", {name: en ? "Verify all" : "Alle prüfen", exact: true});
  await verify.click();
  await page.waitForFunction(() => document.getElementById("archive-batch-action").classList.contains("bk-busy"));
  assert.equal(await button.isDisabled(), true);
  await page.reload();
  await page.waitForFunction(() => document.getElementById("archive-batch-action").getAttribute("aria-busy") === "true");
  assert.deepEqual(requests, [["verify", {}]]);

  dashboard = {...dashboard, active: false, active_kind: null, release_ready_count: 1, verification_batch_id: proof,
    batch: {...dashboard.batch, status: "completed", updated_at: "2", processed: 1,
          items: [{...photo, status: "verified"}]}};
  const ready = page.getByRole("button", {name: en ? "Release all workspaces" : "Alle Arbeitsbereiche freigeben", exact: true});
  await ready.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByText(/SHA-256/).waitFor();
  await dialog.getByRole("button", {name: en ? "Confirm" : "Bestätigen", exact: true}).click();
  await page.waitForFunction(() => document.getElementById("archive-batch-action").classList.contains("bk-busy"));
  assert.deepEqual(requests, [["verify", {}], ["release", {verification_batch_id: proof}]]);
  dashboard = {...dashboard, active: false, active_kind: null, candidate_count: 0, verification_batch_id: null,
    batch: {...dashboard.batch, status: "completed", updated_at: "4", processed: 1,
      items: [{...photo, status: "released"}]}};
  const results = page.locator("#archive-batch-results");
  await status.waitFor({state:"hidden"});
  await results.waitFor({state:"hidden"});
  await page.reload();
  await status.waitFor({state:"hidden"});
  await results.waitFor({state:"hidden"});
  const dock = page.locator(".bk-activity-list .bk-activity-item");
  await dock.getByText("100 %").waitFor({state: "attached"});
  assert.equal(await dock.count(), 1);
  assert.ok((await dock.locator("a").getAttribute("href")).includes("archive_batch=" + releaseId));
  assert.equal(await button.isDisabled(), true);
  dashboard = {...dashboard, batch: {...dashboard.batch, status:"failed", updated_at:"5", total:2, processed:2,
    items:[{...photo, status:"released"}, {event_name:"Needs attention", status:"failed"}]}};
  await page.reload();
  await status.getByText(en ? /Finished with errors/ : /Mit Fehlern beendet/).waitFor();
  await results.locator("summary").click();
  await results.getByText("Needs attention", {exact:true}).waitFor();
  assert.deepEqual(errors, []);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    await check(browser, "en", 1400);
    await check(browser, "de", 390);
    console.log("Archive batch transitions passed in English on desktop and German on mobile.");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
