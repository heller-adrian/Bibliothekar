// Exercise both archive completion dialogs against controlled API responses.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const origin = "http://bibliothekar.test";
const prefix = "/api/change-requests/synthetic";
const missing = "2026/Event/All/photo.RAF";

async function check(browser, language, width) {
  const page = await browser.newPage({viewport: {width, height: 850}});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(({language, width}) => {
    localStorage.setItem("bibliothekar-language", language);
    localStorage.setItem("bibliothekar-theme", width < 500 ? "dark" : "light");
    sessionStorage.setItem("bk-pre71-manual-confirmed:synthetic", "1");
  }, {language, width});
  const requestCounts = new Map();
  let reversal = null;
  const event = {id:"event", job_id:"job", name:"Synthetic event", status:"archived",
    event_kind:"event", start_datetime:"2026-07-22T00:00:00", end_datetime:"2026-07-22T23:59:59"};
  let resume;
  await page.route(origin + "/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    if (pathname === "/events") return route.fulfill({body:html, contentType:"text/html"});
    if (pathname === "/api/events/search") return route.fulfill({json:{events:[event]}});
    if (pathname === "/api/change-requests") return route.fulfill({json:{change_requests:[]}});
    if (pathname.endsWith("/events/event/edit")) return route.fulfill({json:{
      event, structural_editable:true, archived_change_request:true, folder_layout:{structure_enabled:true,
        input_path:"All", layout:{version:2,nodes:[{id:"all",name:"All"},{id:"export",name:"Export",role:"export"}]}}
    }});
    if (pathname.endsWith("/events/event/structure")) return route.fulfill({json:{}});
    if (pathname === prefix) return route.fulfill({json:{id:"synthetic",status:"aenderbar_bestaetigt"}});
    if (pathname === prefix + "/assistant") return route.fulfill({json:{phase:"verify",operations:[]}});
    if (pathname === prefix + "/files") return route.fulfill({json:[]});
    if (pathname === prefix + "/reversal" && !url.searchParams.has("refresh"))
      return route.fulfill({json:{active:Boolean(reversal), phase:reversal}});
    if (pathname.startsWith(prefix)) {
      const count = (requestCounts.get(pathname) || 0) + 1;
      requestCounts.set(pathname, count);
      await new Promise(resolve => { resume = resolve; });
      resume = null;
      if (pathname === prefix + "/archive") return route.fulfill(count === 1
        ? {status:400, json:{detail:"Incomplete", verification:{files:[{new_path:missing,status:"missing"}]}}}
        : {json:{status:"archiviert"}});
      if (pathname === prefix + "/reversal/prepare") {
        reversal = "finder";
        return route.fulfill({json:{active:true,phase:reversal}});
      }
      if (pathname === prefix + "/reversal") {
        reversal = "verify";
        return route.fulfill({json:{active:true,phase:reversal}});
      }
      if (pathname === prefix + "/reversal/finish") return route.fulfill(count === 1
        ? {status:409, json:{detail:"Incomplete", verification:{problems:[{path:missing,message:"File missing"}]}}}
        : {json:{status:"abgebrochen"}});
      throw new Error("Unexpected archive request " + pathname);
    }
    if (pathname.startsWith("/api/")) return route.fulfill({json:{tasks:[],libraries:[],writes_allowed:true}});
    return route.fulfill({body:""});
  });
  await page.goto(origin + "/events?job=job&event=event");
  const editor = page.locator("#event-edit-dialog");
  await editor.locator("#event-edit-header-button").click();
  const checkbox = editor.locator("#edit-subfolders");
  const bounds = await checkbox.boundingBox();
  assert.ok(bounds.width <= 20 && bounds.height <= 20);
  if (width > 900) {
    const day = await editor.locator("#edit-preserve").boundingBox();
    assert.ok(Math.abs(day.y + day.height / 2 - bounds.y - bounds.height / 2) <= 3);
    assert.ok(bounds.x - day.x - day.width >= 20);
  }
  await editor.locator(".bk-event-layout-editor summary").first().click();
  await editor.locator("[data-bk-layout-name=export]").fill("Export Test");
  assert.equal(await editor.locator(".bk-event-export-heading + select option:checked").textContent(),"Export Test");

  const visit = () => page.goto(origin + "/events?task=change:synthetic&change_step=verify");
  const dialog = page.locator("#change-request-dialog");
  async function run(selector, status) {
    const button = dialog.locator(selector);
    await button.click();
    await dialog.locator(status + ".bk-loading-status").waitFor();
    assert.ok(await button.isDisabled());
    assert.ok(resume);
    resume();
  }
  await visit();
  assert.equal(await dialog.locator("[data-cr-verify]").count(),0);
  await run("[data-cr-archive]","#change-verify-summary");
  await dialog.getByText(missing,{exact:true}).waitFor();
  assert.ok(await dialog.locator("[data-cr-back]").isVisible());
  await run("[data-cr-archive]","#change-verify-summary");
  await dialog.waitFor({state:"hidden"});
  reversal = "prepare";
  await visit();
  await run("[data-reversal-prepare]","[data-reversal-activity]");
  await run("[data-reversal-finder-check]","[data-reversal-activity]");
  assert.equal(await dialog.locator("[data-reversal-verify]").count(),0);
  assert.equal(await dialog.locator("[data-reversal-back]").isVisible(),false);
  await run("[data-reversal-finish]","[data-reversal-summary]");
  await dialog.getByText(missing,{exact:true}).waitFor();
  assert.ok(await dialog.locator("[data-reversal-back]").isVisible());
  await run("[data-reversal-finish]","[data-reversal-summary]");
  await dialog.waitFor({state:"hidden"});
  assert.deepEqual([...requestCounts.values()],[2,1,1,2]);
  assert.deepEqual(errors,[]);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    for (const [language, width] of [["en",1280],["de",390]]) {
      await check(browser,language,width);
      console.log("Passed archive edit, completion and reversal",language,width);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
