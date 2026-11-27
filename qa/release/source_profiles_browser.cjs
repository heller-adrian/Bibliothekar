const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const origin = "http://bibliothekar.test";

async function verify(browser, enabled, lang, width) {
  const html = fs.readFileSync(process.argv[enabled ? 3 : 2], "utf8");
  const page = await browser.newPage({viewport: {width, height: 900}});
  const deviceCalls = [];
  const scans = [];
  const errors = [];
  const imports = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(({lang, width}) => {
    localStorage.setItem("bibliothekar-language", lang);
    localStorage.setItem("bibliothekar-theme", width < 600 ? "dark" : "light");
    localStorage.setItem("bk-sd-recheck:old-card", "old-task");
  }, {lang, width});
  const removable = [
    {kind:"sd_card", label:"Synthetic SD", device_path:"/dev/card", device_id:"CARD", mounted:true, read_only:true},
    {kind:"usb_drive", label:"Synthetic USB", device_path:"/dev/drive", device_id:"DRIVE", mounted:true, read_only:false},
  ];
  await page.route(origin + "/**", route => {
    const req = route.request();
    const uri = new URL(req.url());
    if (uri.pathname === "/") return route.fulfill({body: html, contentType:"text/html"});
    if (uri.pathname === "/api/source-devices") {
      deviceCalls.push(req.method());
      return route.fulfill({json:{devices:removable}});
    }
    if (uri.pathname.startsWith("/api/sd-rechecks/")) {
      scans.push(uri.pathname);
      return route.fulfill({json:{state:"completed"}});
    }
    if (uri.pathname === "/api/source-folders") {
      const relative = uri.searchParams.get("relative_path");
      return route.fulfill({json:{root_key:"nas", relative_path:relative, parent_relative_path:relative === "." ? null : ".",
        directories:relative === "." ? [{name:"Inbox", relative_path:"Inbox"}] : []}});
    }
    if (uri.pathname === "/api/source-folder-summary")
      return route.fulfill({json:{media_count:1, file_count:1, total_size_bytes:100}});
    if (uri.pathname === "/api/jobs/folder-import") {
      imports.push(req.postDataJSON());
      return route.fulfill({json:{status:"sd_check", task_id:"folder-check", accepted:true}, status:202});
    }
    if (uri.pathname === "/api/health")
      return route.fulfill({json:{tools:{},paths:{workspace:{writable:true}},runtime:{uid:568,gid:568},database:{initialized:true}}});
    if (uri.pathname === "/api/operations/status")
      return route.fulfill({json:{writes_allowed:true,workspace_writes_allowed:true,issues:[],reservations:[]}});
    if (uri.pathname.startsWith("/api/"))
      return route.fulfill({json:{jobs:[],tasks:[],count:0,total:0,libraries:[],operations:[]}});
    return route.fulfill({body:""});
  });

  await page.goto(origin);
  const folder = page.locator('[data-source-pane="folder"]');
  if (enabled) {
    assert.equal(await page.locator("#bk-source-picker button").count(), 3);
    await page.locator("#sd-card-status").getByText(/Synthetic SD/, {exact:false}).waitFor();
    assert.equal(await page.locator("#sd-import-button").isEnabled(), true);
    await page.locator('[data-source-mode="drive"]').click();
    assert.equal(await page.locator("#device-import-button").isDisabled(), true);
    assert.ok(deviceCalls.length);
    await page.locator('[data-source-mode="folder"]').click();
  } else {
    assert.equal(await page.locator("#bk-source-picker").count(), 0);
    assert.equal(await page.locator("#sd-card-status").count(), 0);
    assert.equal(await page.locator("#device-select").count(), 0);
  }
  await folder.waitFor();
  await folder.locator('[data-folder="Inbox"]').click();
  await folder.locator("#folder-import-button").click();
  await page.waitForFunction(() => !document.getElementById("folder-import-button").disabled);
  assert.equal(imports.length, 1);
  assert.deepEqual([imports[0].source_root_key, imports[0].source_relative_path, imports[0].source_mode], ["nas","Inbox","folder"]);
  if (!enabled) {
    assert.deepEqual(deviceCalls, []);
    assert.deepEqual(scans, ["/api/sd-rechecks/folder-check"]);
  }
  assert.deepEqual(errors, []);
  await page.close();
}

(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE || undefined});
  try {
    for (const enabled of [false, true]) {
      await verify(browser, enabled, "de", 390);
      await verify(browser, enabled, "en", 1280);
    }
    console.log("Source profiles passed in German mobile and English desktop Chromium.");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
