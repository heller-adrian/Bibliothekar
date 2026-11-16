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
const customLayout = {structure_enabled: true, input_path: "All", layout: {version: 2, nodes: [
  {id: "all", name: "All", children: [{id: "jpg", name: "JPG", children: [{id: "deep", name: "Selection"}]}]},
  {id: "export", name: "Export", role: "export"},
]}};
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
  const page = await browser.newPage({viewport: {width, height}, hasTouch: width <= 1024});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(({theme, language}) => {
    localStorage.setItem("bibliothekar-theme", theme);
    localStorage.setItem("bibliothekar-language", language);
  }, {theme, language});
  let batch = inactive;
  let cancelCount = 0;
  let releaseSave;
  let notifySaveStarted;
  let savedRevision=1;
  let pending = {"review-0": {source: "EXIF:ExifIFD:DateTimeOriginal"}};
  await page.route(origin + "/**", async route => {
    const url = new URL(route.request().url());
    const key = url.pathname.split("/" + jobId).at(-1);
    if (url.pathname === "/legacy-adoption") return route.fulfill({body: html, contentType: "text/html"});
    if (key === "") return route.fulfill({json: {plan: {}, state: "inventoried",
      draft: {events: [{name: "Existing test event", start_date: "2025-01-01", end_date: "2025-01-01",
        folder_layout: customLayout}], metadata_review_pending: pending}, draft_revision: savedRevision,
      files: 100, families: 95, errors: 0, review_count: cases.length, source_root: "/synthetic/source"}});
    if (key === "/draft" && route.request().method() === "PUT") {
      await new Promise(resolve => { releaseSave=resolve; notifySaveStarted(); });
      savedRevision++;
      return route.fulfill({json:{revision:savedRevision}});
    }
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
  await tools.scrollIntoViewIfNeeded();
  const cardBox = await page.locator(".adoption-event-card").boundingBox();
  const toolsBox = await tools.boundingBox();
  assert.ok(cardBox.y - toolsBox.y - toolsBox.height >= 10, "saved cards clear the year divider");
  const flatControls = await page.locator("main button, .bk-setup-banner button").evaluateAll(buttons =>
    buttons.every(button => getComputedStyle(button).boxShadow === "none" &&
      ["solid", "none"].includes(getComputedStyle(button).borderTopStyle)));
  assert.ok(flatControls, "wizard and header controls are flat");
  const start = await geometry(page, ".adoption-plan-tools", 160);
  assert.ok(Math.abs(start.top) < 2 && start.containerBottom >= start.bottom && start.background !== "rgba(0, 0, 0, 0)");
  await page.locator(".adoption-event-card summary").focus();
  await page.keyboard.press("Enter");
  await page.locator("#planning-preview code", {hasText: "Photos"}).waitFor();
  await page.locator(".adoption-event-card").getByRole("button", {name: german ? "Bearbeiten" : "Edit"}).click();
  const dialog = page.locator("#event-editor");
  await dialog.locator(".bk-event-layout-editor > summary").click();
  const folderRows = dialog.locator(".bk-folder-layout-row");
  assert.equal(await folderRows.count(), 4);
  const measure = () => folderRows.evaluateAll(rows => rows.map(row => {
    const field = row.querySelector("[data-bk-layout-name]").getBoundingClientRect();
    const buttons = [...row.querySelectorAll("button")].map(button => button.getBoundingClientRect());
    return {fieldWidth: field.width, left: row.getBoundingClientRect().left,
      top: Math.min(...buttons.map(rect => rect.top)), bottom: Math.max(...buttons.map(rect => rect.bottom)),
      right: Math.max(...buttons.map(rect => rect.right))};
  }));
  const positions = await measure();
  for (const [index, position] of positions.entries()) {
    assert.ok(position.fieldWidth > 55 && position.right < width);
    if (index > 0) assert.ok(position.top - positions[index - 1].bottom >= 6,
      `folder button rows overlap at ${width}px ${theme}: ${JSON.stringify(positions)}`);
  }
  assert.ok(positions[0].left < positions[1].left && positions[1].left < positions[2].left);
  assert.equal(positions[0].left, positions[3].left);
  await folderRows.nth(2).locator("[data-bk-layout-child]").click();
  assert.equal(await folderRows.count(), 5);
  const deepest = folderRows.nth(3);
  await deepest.locator("[data-bk-layout-name]").fill("Deep Folder");
  assert.equal(await deepest.locator("[data-bk-layout-name]").inputValue(), "Deep Folder");
  const deeper = await measure();
  assert.ok(deeper[3].top - deeper[2].bottom >= 6 && deeper[3].fieldWidth > 55);
  if (process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS) {
    await deepest.scrollIntoViewIfNeeded();
    await page.screenshot({path: process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS + "/folder-" + width + "-" + theme + ".png"});
  }
  await deepest.locator("[data-bk-layout-remove]").click();
  assert.equal(await folderRows.count(), 4);
  page.once("dialog", confirmation => confirmation.accept());
  await page.keyboard.press("Escape");
  await dialog.waitFor({state: "hidden"});
  await page.locator(".adoption-event-card").getByRole("button", {name:german?"Bearbeiten":"Edit"}).click();
  const saveStarted=new Promise(resolve=>{notifySaveStarted=resolve;});
  await dialog.getByRole("button", {name:german?"Im Entwurf speichern":"Save in draft"}).click();
  await dialog.locator("#editor-message[data-result=busy].bk-loading-status").waitFor();
  await page.waitForFunction(() => document.getElementById("editor-message").textContent.length > 0);
  await saveStarted;
  releaseSave();
  await page.locator("#message[data-result=success]").waitFor();
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

async function checkManual(browser, language, width) {
  const page=await browser.newPage({viewport:{width,height:900},reducedMotion:"reduce"});
  page.setDefaultTimeout(10000);
  const german=language==="de";
  const l=(de,en)=>german?de:en;
  const planId="c".repeat(32);
  let execution=null, done=false, restored=false, releaseConfirm;
  let confirmStarted;
  const pendingConfirmation=new Promise(resolve=>{confirmStarted=resolve;});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.addInitScript(language=>{
    localStorage.setItem("bibliothekar-language",language);
    localStorage.setItem("bibliothekar-theme",language==="de"?"dark":"light");
  },language);
  await page.route(origin+"/**",async route=>{
    const url=new URL(route.request().url());
    const key=url.pathname.split("/"+jobId).at(-1);
    if (url.pathname==="/legacy-adoption")return route.fulfill({body:html,contentType:"text/html"});
    if (url.pathname==="/setup/adoption")return route.fulfill({body:"Synthetic setup choice"});
    if (!key)return route.fulfill({json:{state:"inventoried",files:2,families:1,errors:0,review_count:0,
      draft_revision:1,draft:{},source_root:"/sources/photos",plan:{id:planId,documents_at:"set",execution,
        state:execution?.phase==="registration_pending"?"verified":"prepared",move_files:2,move_families:1,
        move_bytes:700,library_name:"Main Library",source_root:"/sources/photos",archive_root:"/main-library",
        dataset:{dataset:"test/media"},events:[{existing:false}],counts:{pending:2},issues:0}}});
    if (key==="/review/batch")return route.fulfill({json:inactive});
    if (key==="/confirm") {
      assert.deepEqual(route.request().postDataJSON(),{plan_id:planId,method:"manual",acknowledged:true});
      await new Promise(resolve=>{releaseConfirm=resolve;confirmStarted();});
      execution={method:"manual",phase:"manual"};return route.fulfill({json:{execution}});
    }
    if (key==="/manual-work") {
      const checked=url.searchParams.get("check")==="true";
      const reverse=execution.phase==="rolling_back";
      const ready=checked && (reverse?restored:done);
      const state=checked?(ready?"done":"pending"):"unchecked";
      return route.fulfill({json:{plan_id:planId,reverse,checked,ready,source_root:"/sources/photos",archive_root:"/main-library",steps:[
        {kind:reverse?"restore_source":"prepare",state,items:[{path:reverse?"old":"new/event.json",state}]},
        {kind:"move",state,from:reverse?"new":"old",to:reverse?"old":"new",items:[{from:"a.raf",to:"a.raf",state}]},
      ]}});
    }
    if (key==="/verify"){
      assert.ok(done);execution={method:"manual",phase:"registration_pending"};
      return route.fulfill({json:{execution,state:"verified"}});
    }
    if (key==="/rollback/start"){
      execution={method:"manual",phase:"rolling_back"};return route.fulfill({json:{execution}});
    }
    if (key==="/rollback/check"){
      assert.ok(restored);execution={method:"manual",phase:"rolled_back"};return route.fulfill({json:{execution}});
    }
    if (key==="/assets/bibliothekar-logo-v3.svg")
      return route.fulfill({path:path.join(__dirname,"../../app/bibliothekar-logo-v3.svg")});
    if (key==="/auth/client.js" || key==="/favicon.ico")return route.fulfill({body:""});
    throw Error("Unmocked manual wizard request "+url.pathname);
  });
  await page.goto(origin+"/legacy-adoption?job="+jobId+"&step=execution");
  const submit=page.getByRole("button",{name:l("Durchführung verbindlich starten","Confirm and start")});
  assert.ok(await submit.isDisabled());
  await page.locator(".adoption-ack input").check();
  await submit.click();
  await pendingConfirmation;
  assert.equal(await submit.getAttribute("aria-busy"),"true");
  assert.ok(await submit.evaluate(button=>getComputedStyle(button,"::after").animationName==="none"));
  await page.locator("#message.bk-loading-status").waitFor();
  releaseConfirm();
  await page.getByRole("link",{name:l("Ordnergerüst mit Ereignisdokumenten (ZIP)","Folder scaffold with event documents (ZIP)")}).waitFor();
  const advance=page.getByRole("button",{name:l("Weiter: Archiv prüfen","Next: Verify archive")});
  assert.ok(await advance.isDisabled());
  const refresh=page.locator("#manual-refresh");
  await refresh.click();
  await page.locator(".adoption-manual-step [data-state=pending]").first().waitFor();
  const move=page.locator(".adoption-manual-step").nth(1);
  await move.locator("summary").focus();
  await page.keyboard.press("Enter");
  await move.getByText("/sources/photos/old",{exact:true}).waitFor();
  await move.getByText("/main-library/new",{exact:true}).waitFor();
  await move.getByText("a.raf",{exact:true}).waitFor();
  done=true;
  await refresh.click();
  await move.locator("summary [data-state=done]").waitFor();
  assert.ok(await move.evaluate(card=>card.open));
  if(process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS)
    await page.screenshot({path:process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS+"/manual-"+language+".png"});
  await page.reload();
  assert.ok(await advance.isDisabled());
  await refresh.click();
  await advance.click();
  await page.getByRole("button",{name:l("Übernahme registrieren","Register adoption")}).waitFor();
  page.once("dialog",confirmation=>confirmation.accept());
  await page.locator("#top-actions .danger-button").click();
  await page.getByRole("link",{name:l("Ursprüngliches Ordnergerüst (ZIP)","Original folder scaffold (ZIP)")}).waitFor();
  const finish=page.getByRole("button",{name:l("Wiederherstellung prüfen und Auftrag beenden","Verify rollback and end job")});
  await finish.waitFor();
  assert.ok(await finish.isDisabled());
  restored=true;
  await refresh.click();
  await finish.click();
  await page.waitForURL("**/setup/adoption");
  assert.deepEqual(errors,[]);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    for (const variant of [[1400, 880, "light", "en"], [1024, 680, "dark", "de"], [768, 1024, "light", "en"], [390, 780, "dark", "de"]]) {
      await check(browser, ...variant);
      console.log("Passed", ...variant);
    }
    for(const [language,width] of [["de",390],["en",1100]]){
      await checkManual(browser,language,width);
      console.log("Passed manual work",language,width);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
