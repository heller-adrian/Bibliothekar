// Render the real wizard and control only its API responses for reproducible browser checks.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { strict: assert } = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const html = fs.readFileSync(process.argv[2], "utf8");
const origin = "http://bibliothekar.test";
const jobId = "a".repeat(32);
const batchId = "b".repeat(32);
const segments = Array.from({length: 60}, (_, index) => {
  const day = new Date(Date.UTC(2025, 0, index + 1)).toISOString().slice(0, 10);
  return {day_key: day, start_time: "00:00", end_time: "23:59",
    start_datetime: day + "T00:00:00", end_datetime: day + "T23:59:00", families: 5, files: 7};
});
segments.push({...segments[0], day_key: "2026-01-01", start_datetime: "2026-01-01T00:00:00", end_datetime: "2026-01-01T23:59:00"});
const cases = Array.from({length: 55}, (_, index) => ({
  family_key: "review-" + index, state: "open", files: [], reasons: ["missing_capture_time"], can_copy: true,
  metadata_choices: [{source: "EXIF:ExifIFD:DateTimeOriginal", time: "2025-01-01T00:00:00"}],
}));
const inactive = {total: 0, copied: 0, failed: 0, pending: 0, running: false};
const active = {...inactive, batch_id: batchId, state: "active", total: 1, pending: 1, running: true,
  bytes_written: 2048, bytes_total: 4096};
const paused = {...active, running: false, state: "cancelling",
  cancel_error: "Eine Arbeitskopie oder ihr Ordner wurde verändert. Die Bereinigung wartet auf eine sichere Wiederherstellung."};

async function geometry(page, selector, scrollAt) {
  return page.evaluate(({selector, scrollAt}) => {
    const element = document.querySelector(selector);
    window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY + scrollAt);
    const box = element.getBoundingClientRect();
    const container = element.closest("section").getBoundingClientRect();
    return {top: box.top, bottom: box.bottom, containerBottom: container.bottom, height: box.height,
      background: getComputedStyle(element).backgroundColor};
  }, {selector, scrollAt});
}

async function check(browser, width, height, theme, language) {
  const page = await browser.newPage({viewport: {width, height}});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(({theme, language}) => {
    localStorage.setItem("bibliothekar-theme", theme);
    localStorage.setItem("bibliothekar-language", language);
  }, {theme, language});
  let batch = inactive;
  let cancelCount = 0;
  let pending = {"review-0": {source: "EXIF:ExifIFD:DateTimeOriginal"}};
  await page.route(origin + "/**", route => {
    const url = new URL(route.request().url());
    const key = url.pathname.split("/" + jobId).at(-1);
    if (url.pathname === "/legacy-adoption") return route.fulfill({body: html, contentType: "text/html"});
    if (key === "") return route.fulfill({json: {plan: {}, state: "inventoried",
      draft: {events: [{name: "Existing test event"}], metadata_review_pending: pending}, draft_revision: 1,
      files: 100, families: 95, errors: 0, review_count: cases.length, source_root: "/synthetic/source"}});
    if (key === "/draft/check") return route.fulfill({json: {valid: true, free_segments: segments, coverage: {unassigned: 25},
      events: [{name: "Existing test event", start: "2025-01-01T01:00:00", end: "2025-01-01T02:00:00", families: 1, files: 1}]}});
    if (key === "/draft/structure") return route.fulfill({json: {directories: ["2025/Existing test event/Photos"]}});
    if (key === "/review") return route.fulfill({json: cases});
    if (key === "/review/selection") return route.fulfill({json: cases.map(item => item.family_key)});
    if (key === "/review/batch") return route.fulfill({json: batch});
    if (key === "/review/batch/cancel") {
      assert.deepEqual(route.request().postDataJSON(), {batch_id: batchId});
      cancelCount++;
      batch = cancelCount === 1 ? {...active, state: "cancelling"} : {...inactive, state: "cancelled"};
      return route.fulfill({status: 202, json: {accepted: true}});
    }
    if (key === "/review/metadata") {
      pending = {[route.request().postDataJSON().family_keys[0]]: {source: route.request().postDataJSON().source}};
      return route.fulfill({json: {revision: 2, staged: 1, rejected: {}}});
    }
    if (key === "/assets/bibliothekar-logo-v3.svg") {
      return route.fulfill({path: path.join(__dirname, "../../app/bibliothekar-logo-v3.svg")});
    }
    if (key === "/auth/client.js" || key === "/favicon.ico" || key.startsWith("/static/")) return route.fulfill({body: ""});
    throw Error("Unmocked wizard request " + url.pathname);
  });
  const german = language === "de";
  const visit = origin + "/legacy-adoption?job=" + jobId + "&step=plan";
  await page.goto(visit);
  await page.locator("#days [data-day]").nth(59).waitFor();
  const tools = page.locator(".adoption-plan-tools");
  assert.ok((await tools.boundingBox()).y > 120, "the event tools start in document flow");
  const start = await geometry(page, ".adoption-plan-tools", 160);
  assert.ok(Math.abs(start.top) < 2 && start.containerBottom >= start.bottom && start.background !== "rgba(0, 0, 0, 0)");
  await page.locator(".adoption-event-card summary").focus();
  await page.keyboard.press("Enter");
  await page.locator("#planning-preview code", {hasText: "Photos"}).waitFor();
  const last = page.locator("#days [data-day]").nth(59);
  await last.focus();
  await page.keyboard.press("Space");
  await page.locator("#planning-preview").getByText(segments[59].day_key, {exact: false}).waitFor();
  const inspector = await page.locator(".adoption-plan-inspector").boundingBox();
  assert.ok(inspector.y >= (await tools.boundingBox()).height - 2 && inspector.y < height);
  if (width > 900) assert.ok(inspector.x >= width / 2);
  assert.equal(await page.locator("#days [aria-checked=true]").count(), 1);
  const nextYear = tools.getByRole("button", {name: "2026 (5)"});
  await nextYear.focus();
  await page.keyboard.press("Enter");
  await page.locator("#days [data-day]").getByText("2026-01-01").waitFor();
  assert.ok(await nextYear.evaluate(button => button === document.activeElement));
  await tools.getByRole("button", {name: german ? "Ohne gesichertes Datum (55)" : "No verified date (55)"}).click();
  const review = page.locator(".adoption-review-tools");
  const rows = page.locator(".adoption-review-row");
  await rows.nth(54).waitFor();
  const selection = review.getByRole("button", {name: german ? "Alle auswählen" : "Select all"});
  const reviewBox = await geometry(page, ".adoption-review-tools", 350);
  assert.ok(Math.abs(reviewBox.top) < 2 && reviewBox.containerBottom >= reviewBox.bottom);
  await selection.focus();
  await page.keyboard.press("Enter");
  await review.getByText(german ? "55 ausgewählt" : "55 selected").waitFor();
  assert.equal(await rows.getByRole("checkbox", {checked: true}).count(), 55);
  const source = rows.nth(32).getByRole("combobox");
  await source.selectOption("EXIF:ExifIFD:DateTimeOriginal");
  await page.evaluate(() => {
    const footer = document.createElement("div");
    footer.style.height = "120vh";
    document.body.append(footer);
    window.scrollTo(0, document.body.scrollHeight);
  });
  assert.ok((await review.boundingBox()).y + reviewBox.height <= 0);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  if (process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await geometry(page, ".adoption-review-tools", 350);
    await page.screenshot({path: process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS + "/" + width + "-" + theme + ".png"});
  }

  batch = active;
  await page.reload();
  const cancel = page.getByRole("button", {name: german ? "Kopieren abbrechen" : "Cancel Copy"});
  await cancel.waitFor();
  assert.ok((await cancel.boundingBox()).y >= (await page.locator("#review-progress progress").boundingBox()).y);
  assert.ok(await cancel.evaluate(button => button.classList.contains("danger-button")));
  await cancel.click();
  await page.getByText(german ? /Abbruch angefordert/ : /Cancellation requested/).waitFor();
  assert.equal(await cancel.count(), 0);
  await page.reload();
  await page.getByText(german ? /Abbruch angefordert/ : /Cancellation requested/).waitFor();
  batch = paused;
  const resume = page.getByRole("button", {name: german ? "Bereinigung fortsetzen" : "Resume cleanup"});
  await resume.waitFor();
  await resume.click();
  await page.getByText(german ? "Kopierauftrag abgebrochen" : "Copy job cancelled").waitFor();
  assert.equal(await cancel.count(), 0);
  assert.equal(cancelCount, 2);
  assert.deepEqual(errors, []);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    for (const variant of [[1400, 880, "light", "en"], [1024, 680, "dark", "de"], [390, 780, "dark", "de"]]) {
      await check(browser, ...variant);
      console.log("Passed", ...variant);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
