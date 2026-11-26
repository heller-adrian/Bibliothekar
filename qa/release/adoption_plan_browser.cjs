// Render the real wizard and control only its API responses for reproducible browser checks.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const { strict: assert } = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const html = fs.readFileSync(process.argv[2], "utf8");
const origin = "http://bibliothekar.test";
const logos = ["/assets/bibliothekar-logo-v3.svg", "/assets/bibliothekar-logo-symbol-background.svg"];
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
      archive_segments: [{...segments[1], event_id: "archive", event_name: "Archived sample"}],
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
    if (logos.includes(key)) {
      return route.fulfill({path: path.join(__dirname, "../../app", path.basename(key))});
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
  const archiveCard = await page.locator("#archive-segments .day-card").boundingBox();
  assert.ok(archiveCard.y - toolsBox.y - toolsBox.height >= 10, "archived cards clear the year divider");
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
  const exportSelect=dialog.locator(".bk-event-export-heading + select");
  const exportName=folderRows.nth(3).locator("[data-bk-layout-name]");
  assert.equal(await exportSelect.inputValue(),"export");
  await exportName.fill("Export Test");
  assert.equal(await exportSelect.locator("option:checked").textContent(),"Export Test");
  assert.equal(await exportSelect.inputValue(),"export");
  await folderRows.nth(2).locator("[data-bk-input-node]").check();
  await folderRows.nth(0).locator("[data-bk-layout-name]").fill("Photos");
  assert.equal(await folderRows.nth(2).locator("[data-bk-input-node]").inputValue(),"Photos/JPG/Selection");
  await exportSelect.selectOption("jpg");
  await folderRows.nth(1).locator("[data-bk-layout-name]").fill("JPEGs");
  assert.equal(await exportSelect.locator("option:checked").textContent(),"Photos/JPEGs");
  await exportSelect.selectOption("export");
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
    if (key==="/preparation") return route.fulfill({json:{state:"not_started"}});
    if (key==="/review/batch")return route.fulfill({json:inactive});
    if (key==="/moves" && url.searchParams.get("renamed")==="true")
      return route.fulfill({json:[{source:"/sources/photos/old/a.raf",target:"/main-library/new/a_Adopted_001.raf",
        relative_path:"old/a.raf"}]});
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
        {kind:"move",state,from:reverse?"new":"old",to:reverse?"old":"new",items:[{from:reverse?"a_Adopted_001.raf":"a.raf",to:reverse?"a.raf":"a_Adopted_001.raf",state}]},
      ]}});
    }
    if (key==="/rollback/start"){
      execution={method:"manual",phase:"rolling_back"};return route.fulfill({json:{execution}});
    }
    if (key==="/rollback/check"){
      assert.ok(restored);execution={method:"manual",phase:"rolled_back"};return route.fulfill({json:{execution}});
    }
    if (logos.includes(key))
      return route.fulfill({path:path.join(__dirname,"../../app", path.basename(key))});
    if (key==="/auth/client.js" || key==="/favicon.ico")return route.fulfill({body:""});
    throw Error("Unmocked manual wizard request "+url.pathname);
  });
  await page.goto(origin+"/legacy-adoption?job="+jobId+"&step=execution");
  const submit=page.getByRole("button",{name:l("Durchführung verbindlich starten","Confirm and start")});
  assert.ok(!(await submit.isVisible()));
  await page.locator("#execution-method-choice").click();
  assert.ok(await submit.isDisabled());
  await page.locator("#rename-preview").locator("..").locator("summary").click();
  await page.locator("#rename-preview").getByText("→ /main-library/new/a_Adopted_001.raf",{exact:true}).waitFor();
  await page.locator(".adoption-ack input").check();
  await submit.click();
  await pendingConfirmation;
  assert.equal(await submit.getAttribute("aria-busy"),"true");
  assert.ok(await submit.evaluate(button=>getComputedStyle(button,"::after").animationName==="none"));
  await page.locator("#message.bk-loading-status").waitFor();
  releaseConfirm();
  await page.getByRole("link",{name:l("Ordnergerüst mit Ereignisdokumenten (ZIP)","Folder scaffold with event documents (ZIP)")}).waitFor();
  assert.equal(await page.locator("#wizard-steps button").count(),6);
  assert.equal(await page.locator("#wizard-steps [aria-current=step]").textContent(),
    l("6. Ausführen und prüfen","6. Execute and verify"));
  const advance=page.getByRole("button",{name:l("Übernahme prüfen und registrieren","Verify and register adoption")});
  assert.ok(await advance.isDisabled());
  const refresh=page.locator("#manual-refresh");
  await refresh.click();
  await page.locator(".adoption-manual-step [data-state=pending]").first().waitFor();
  const move=page.locator(".adoption-manual-step").nth(1);
  await move.locator("summary").focus();
  await page.keyboard.press("Enter");
  await move.getByText("/sources/photos/old",{exact:true}).waitFor();
  await move.getByText("/main-library/new",{exact:true}).waitFor();
  await move.getByText("a.raf → a_Adopted_001.raf",{exact:true}).waitFor();
  await move.getByText(l("Umbenennung erforderlich","Rename required"),{exact:true}).waitFor();
  done=true;
  await refresh.click();
  await move.locator("summary [data-state=done]").waitFor();
  assert.ok(await move.evaluate(card=>card.open));
  if(process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS)
    await page.screenshot({path:process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS+"/manual-"+language+".png"});
  await page.reload();
  assert.ok(await advance.isDisabled());
  await refresh.click();
  await advance.waitFor({state:"visible"});
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

async function checkScriptCompletion(browser, language, width) {
  const page = await browser.newPage({viewport: {width, height: 840}});
  const planId = "d".repeat(32);
  const l=(de,en)=>language==="de"?de:en;
  const plan = {id: planId, documents_at: "set", execution: null, filename_method:"script",
    manual_blocker:{path:"capture.xmp",raw_reference:"capture.raf",raw_name:"capture.RAF"},
    state: "prepared", move_files: 1, move_families: 1, move_bytes: 500, events: [],
    counts: {pending: 1}, issues: 0, dataset: {dataset: "test/media"}};
  const requests = [];
  let stage = "not_started", released = false, finished = false, confirmations=0;
  let releaseConfirmation;
  const pending = new Promise(resolve=>{releaseConfirmation=resolve;});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.addInitScript(language => localStorage.setItem("bibliothekar-language", language), language);
  await page.route(origin + "/**", async route => {
    const {pathname} = new URL(route.request().url());
    if (pathname === "/legacy-adoption") return route.fulfill({body: html, contentType: "text/html"});
    if (pathname === "/legacy-adoption/history") return route.fulfill({body: "Completed"});
    const key = pathname.split("/" + jobId).at(-1);
    if (!key) return route.fulfill({json: {state:"inventoried", plan, draft:{}, draft_revision:1, review_count:0}});
    if (key === "/review/batch") return route.fulfill({json: inactive});
    if (key === "/script/probe") return route.fulfill({json: {verified:true,dataset:"test/media",
      sha256:"a".repeat(64),host:{source:"/synthetic/source",archive:"/synthetic/archive"}}});
    if (key === "/preparation") return route.fulfill({json: {state:stage, phase:"source",
      worker_active:stage==="running", processed:2,total:3,bytes_processed:4194304,bytes_total:8388608}});
    if (key === "/confirm") {
      confirmations++;
      assert.deepEqual(route.request().postDataJSON(),{plan_id:planId,method:"script",acknowledged:true,probe_sha256:"a".repeat(64)});
      stage="running";
      await pending;
      return route.fulfill({status:202,json:{accepted:true}}).catch(()=>{});
    }
    if (key === "/script/release") {
      released=true;
      return route.fulfill({json:{command:"python3 synthetic-adoption.py"}});
    }
    if (key === "/script") return route.fulfill({json: {running: false, journal_started: finished,
      can_reopen:!finished, command:released?"python3 synthetic-adoption.py":null,
      status:finished?{state:"completed",mode:"apply",processed:3,total:3}:null}});
    if (route.request().method() === "POST") {
      requests.push(key);
      assert.equal(key, "/finalize");
      assert.equal(route.request().postDataJSON().plan_id, planId);
      if(requests.length===1)return route.fulfill({status:409,json:{detail:"Synthetic verification issue"}});
      return route.fulfill({json: {state: "completed"}});
    }
    if (logos.includes(pathname))
      return route.fulfill({path: path.join(__dirname, "../../app", path.basename(pathname))});
    if (pathname === "/auth/client.js" || pathname === "/favicon.ico") return route.fulfill({body: ""});
    throw Error("Unmocked scripted wizard request " + pathname);
  });
  await page.goto(origin + "/legacy-adoption?job=" + jobId + "&step=execution");
  assert.ok(await page.locator('input[value=manual]').isDisabled());
  await page.getByText("capture.xmp · capture.raf → capture.RAF",{exact:true}).waitFor();
  await page.getByRole("button",{name:l("Diese Methode wählen","Choose this method")}).click();
  const ack=page.locator(".adoption-ack input");
  const confirm=page.getByRole("button",{name:l("Durchführung verbindlich starten","Confirm and start")});
  assert.ok(await confirm.isDisabled());
  await ack.check();
  await confirm.click();
  const progress=page.locator("#execution-confirmation #preparation-progress");
  await progress.waitFor();
  assert.ok(!(await ack.isVisible()));
  assert.equal(await page.locator("#top-actions #preparation-progress").count(),0);
  await page.reload();
  await progress.getByRole("progressbar").waitFor();
  assert.ok(!(await ack.isVisible()));
  assert.equal(confirmations,1);
  assert.match(await progress.innerText(),/2 \/ 3 .*4 \/ 8 MiB/);
  if(process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS)
    await page.screenshot({path:process.env.BIBLIOTHEKAR_BROWSER_SCREENSHOTS+"/rc6-preparation-"+language+".png"});
  plan.execution={method:"script",phase:"script_prepared"};
  stage="completed";
  releaseConfirmation();
  await page.waitForURL("**step=execute");
  const back=page.locator("#wizard-navigation #script-return button");
  await back.waitFor();
  assert.equal(await page.locator("#top-actions #rollback-start").count(),0);
  const release=page.getByRole("button",{name:l("Skriptbefehl bereitstellen","Prepare script command")});
  await release.click();
  await page.locator(".adoption-command").waitFor();
  await back.waitFor();
  assert.equal(await page.locator("#top-actions #rollback-start").count(),0);
  assert.equal(await page.locator("#wizard-steps button").count(),6);
  const finalize = page.getByRole("button", {name: language === "de"
    ? "Übernahme prüfen und registrieren" : "Verify and register adoption"});
  await finalize.waitFor();
  assert.ok(await finalize.isDisabled());
  finished = true;
  await page.locator("#rollback-start").waitFor({timeout:6000});
  assert.ok(!(await back.isVisible()));
  await finalize.click({timeout: 6000});
  await page.getByText("Synthetic verification issue",{exact:true}).waitFor();
  await finalize.click({timeout:6000});
  await page.waitForURL("**/legacy-adoption/history?*");
  assert.deepEqual(requests, ["/finalize","/finalize"]);
  assert.deepEqual(errors,[]);
  await page.close();
}

async function checkReviewPlan(browser, language, width) {
  const german = language === "de";
  const page = await browser.newPage({viewport: {width, height: 850}});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(({language}) => {
    localStorage.setItem("bibliothekar-theme", language === "de" ? "dark" : "light");
    localStorage.setItem("bibliothekar-language", language);
  }, {language});
  const dirs = Array.from({length: 105}, (_, index) => "2025/Event/Folder " + String(index).padStart(3, "0"));
  const calls = [];
  const initial = {id: batchId, state: "prepared", documents_at: null, events: [],
    move_files: 1, move_bytes: 20, move_families: 1, counts: {pending: 1}, inventory_duplicates: 2,
    source_root: "/synthetic/source", archive_root: "/synthetic/archive", library_name: "Main Library"};
  let plan = {...initial};
  await page.route(origin + "/**", async route => {
    const url = new URL(route.request().url());
    const key = url.pathname.split("/" + jobId).at(-1);
    if (key === "/legacy-adoption") return route.fulfill({body: html, contentType: "text/html"});
    if (key === "") return route.fulfill({json: {plan, state: "inventoried", draft: {}, draft_revision: 0,
      files: 3, families: 3, review_count: 0, errors: 0, duplicate_files: 2, source_root: "/synthetic/source"}});
    if (key === "/directories") {
      const after = url.searchParams.get("after");
      return route.fulfill({json: dirs.filter(item => item > after).slice(0, 100)});
    }
    if (key === "/documents" || key === "/reopen") {
      calls.push(key);
      plan = key === "/documents" ? {...plan, documents_at: "2026-11-17"} : {};
      return route.fulfill({json: plan});
    }
    if (key === "/execution-method") {
      const payload=route.request().postDataJSON();
      assert.equal(payload.plan_id,plan.id);
      calls.push(payload.method);
      plan={...plan,id:payload.method==="script"?"e".repeat(32):batchId,filename_method:payload.method};
      return route.fulfill({json:plan});
    }
    if (key === "/preparation") return route.fulfill({json:{state:"not_started"}});
    if (key === "/script/probe") return route.fulfill({json:{}});
    if (key === "/moves") return route.fulfill({json:[{
      source:"/synthetic/source/DSCF.MOV",target:"/synthetic/archive/20261117_090000_Camera.MOV",
    }]});
    if (key === "/inventory-exclusions") return route.fulfill({json: [
      {relative_path: "old-copy.JPG", disposition: "duplicate"},
    ]});
    if (key === "/draft/check") return route.fulfill({json: {valid: true, events: [], coverage: {unassigned: 1}}});
    if (key === "/chronology") return route.fulfill({json: []});
    if (key === "/review/batch") return route.fulfill({json: inactive});
    if (logos.includes(key)) return route.fulfill({path: path.join(__dirname, "../../app", path.basename(key))});
    if (key === "/auth/client.js" || key === "/favicon.ico") return route.fulfill({body: ""});
    throw Error("Unmocked review request " + url.pathname);
  });
  // Bookmarks cannot skip preparation. The Review step opens the tree automatically.
  await page.goto(origin + "/legacy-adoption?job=" + jobId + "&step=execution");
  await page.waitForURL("**step=review");
  const preview = page.locator("details.adoption-target-preview").first();
  await preview.getByText("Folder 104", {exact: true}).waitFor();
  assert.ok(await preview.evaluate(details => details.open));
  assert.equal(await page.getByRole("button", {name: /Prepare event documents|Ereignisdokumente vorbereiten|Reopen plan for editing|Plan zur Bearbeitung öffnen/}).count(), 0);
  const next = page.getByRole("button", {name: german ? "Weiter: Methode wählen" : "Next: Choose execution"});
  await next.click();
  await page.waitForURL("**step=execution");
  assert.deepEqual(calls, ["/documents"]);
  await page.locator('input[name=adoption-execution][value=script]').click();
  assert.deepEqual(calls, ["/documents"]);
  assert.ok(!(await page.locator(".adoption-confirm-actions").isVisible()));
  await page.locator("#execution-method-choice").click();
  await page.locator(".adoption-confirm-actions").waitFor();
  const renames=page.locator("#rename-preview").locator("..");
  assert.equal(await renames.getAttribute("open"),null);
  await renames.locator("summary").click();
  await page.getByText("→ /synthetic/archive/20261117_090000_Camera.MOV",{exact:true}).waitFor();
  assert.ok(await page.locator('input[name=adoption-execution][value=script]').isChecked());
  assert.ok(await page.getByRole("button",{name:german?"Durchführung verbindlich starten":"Confirm and start"}).isDisabled());
  await page.reload();
  await page.locator(".adoption-confirm-actions").waitFor();
  assert.equal(await renames.getAttribute("open"),null);
  await page.locator('input[name=adoption-execution][value=manual]').click();
  assert.deepEqual(calls, ["/documents", "script"]);
  await page.locator("#execution-method-choice").click();
  await page.locator(".adoption-ack").waitFor();
  const back = page.getByRole("button", {name: german ? "Zurück" : "Back", exact: true});
  await back.click();
  await page.waitForURL("**step=review");
  await back.click();
  await page.waitForURL("**step=plan");
  assert.deepEqual(calls, ["/documents", "script", "manual", "/reopen"]);
  await back.click();
  const inventory = page.getByText(german ? "Ausgeschlossene Dateien" : "Excluded files", {exact: true});
  await inventory.click();
  await page.getByText("old-copy.JPG").waitFor();
  assert.deepEqual(errors, []);
  await page.close();
}


async function checkReloadAndReview(browser) {
  const page = await browser.newPage();
  const rows=cases.slice(0,26);
  const keys=rows.map(item=>item.family_key);
  const tag="EXIF:ExifIFD:DateTimeOriginal";
  const otherTag="EXIF:ExifIFD:CreateDate";
  let revision=0, running=false, applied=false, checkCount=0, applyCount=0;
  let releasePreview, completeApply;
  const pending={};
  await page.addInitScript(id=>{
    localStorage.setItem("bibliothekar-language","de");
    if(sessionStorage.getItem("bk-adoption-period:"+id)===null)sessionStorage.setItem("bk-adoption-period:"+id,"review");
  },jobId);
  await page.route(origin+"/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    const endpoint=path.split("/"+jobId).at(-1);
    if(path==="/legacy-adoption")return route.fulfill({body:html,contentType:"text/html"});
    if(endpoint==="")return route.fulfill({json:{plan:{},state:"inventoried",files:10347,families:10347,
      errors:0,review_count:applied?0:26,draft_revision:revision,metadata_running:running,
      draft:{metadata_review_pending:pending,metadata_review_result:applied?{applied:2,remaining:0}:null}}});
    if(endpoint==="/review/batch")return route.fulfill({json:inactive});
    if(endpoint==="/draft/check"){
      if(++checkCount===1){
        await new Promise(resolve=>{releasePreview=resolve;});
        return route.fulfill({status:503,json:{detail:"Synthetischer Fehler"}});
      }
      const restored=applied?[{...segments[0],day_key:"2022-06-03",start_datetime:"2022-06-03T00:00:00",
        end_datetime:"2022-06-03T23:59:59",families:2}]:[];
      return route.fulfill({json:{valid:true,free_segments:[...restored,...segments],events:[]}});
    }
    if(endpoint==="/review")return route.fulfill({json:rows.map(item=>({...item,metadata_choices:[
      {source:tag,time:"2022-06-03T12:00:00"},{source:otherTag,time:"2022-06-03T14:00:00"}]}))});
    if(endpoint==="/review/selection")return route.fulfill({json:keys});
    if(endpoint==="/families")return route.fulfill({json:[]});
    if(endpoint==="/review/metadata"){
      const command=route.request().postDataJSON();
      assert.equal(command.revision,revision);
      for(const key of command.family_keys)pending[key]={source:command.source};
      return route.fulfill({json:{revision:++revision,staged:command.family_keys.length,rejected:{}}});
    }
    if(endpoint==="/review/metadata/apply"){
      running=true;applyCount++;
      await new Promise(resolve=>{completeApply=resolve;});
      for(const key of Object.keys(pending))delete pending[key];
      running=false;applied=true;
      await route.fulfill({json:{revision:++revision,applied:2,rejected:{}}}).catch(()=>{});
      return;
    }
    return route.fulfill({body:""});
  });
  const button=name=>page.getByRole("button",{name,exact:true});
  await page.goto(origin+"/legacy-adoption?job="+jobId+"&step=plan");
  await button("Änderungen verwerfen").waitFor();
  await button("Zurück").waitFor();
  await page.getByText("Ereignisplanung wird geladen …",{exact:true}).waitFor();
  assert.ok(releasePreview);
  releasePreview();
  await button("Gespeicherten Auftrag erneut laden").click();
  await page.locator(".adoption-review-row").nth(25).waitFor();
  await button("Alle auswählen").click();
  await page.locator("#review-selection").getByText("26 ausgewählt",{exact:true}).waitFor();
  assert.equal(await page.locator(".adoption-review-row input:checked").count(),26);
  await button("Auswahl aufheben").click();
  assert.equal(await page.locator(".adoption-review-row input:checked").count(),0);
  for(const [index,choice] of [[0,tag],[1,otherTag]]){
    await page.locator(".adoption-metadata-source").nth(index).selectOption(choice);
    await page.getByText("Metadatenquelle vorgemerkt · 1",{exact:true}).waitFor();
  }
  await Promise.all([page.waitForRequest(request=>request.url().endsWith("/review/metadata/apply")),
    button("Änderungen anwenden").click()]);
  await page.reload();
  await page.getByText("Metadatenentscheidungen werden angewendet …",{exact:true}).waitFor();
  assert.equal(await button("Änderungen verwerfen").count(),0);
  assert.ok(completeApply);
  completeApply();
  await button("2022 (2)").waitFor();
  await page.getByText("Aufnahmezeiten übernommen · 2",{exact:true}).waitFor();
  await page.reload();
  await button("2022 (2)").waitFor();
  await button("Änderungen verwerfen").waitFor();
  assert.equal(applyCount,1);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    await checkReloadAndReview(browser);
    console.log("Passed interrupted reload and 26 review cases");
    for (const variant of [[1400, 880, "light", "en"], [1024, 680, "dark", "de"], [768, 1024, "light", "en"], [390, 780, "dark", "de"]]) {
      await check(browser, ...variant);
      console.log("Passed", ...variant);
    }
    for(const [language,width] of [["de",390],["en",1100]]){
      await checkManual(browser,language,width);
      console.log("Passed manual work",language,width);
      await checkReviewPlan(browser,language,width);
      console.log("Passed review and preparation",language,width);
      await checkScriptCompletion(browser,language,width);
      console.log("Passed script completion",language,width);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
