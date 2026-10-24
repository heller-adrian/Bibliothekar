/* Isolated synthetic renderer probe using the actual RC3 HTML, CSS and JS.
   No application server, NAS, remote requests, cookies or user data. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const strip=html=>html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const results=[];
(async()=>{
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE ? {executablePath:process.env.CHROMIUM_EXECUTABLE} : {})});
try {
const context=await browser.newContext({viewport:{width:390,height:844},offline:true});await context.route('**/*',route=>route.abort());
const page=await context.newPage();
for(const locale of ['en','de']) {
await page.goto('about:blank');await page.setContent(strip(bundle.workspace));
await page.addScriptTag({content:bundle.i18n});
await page.evaluate(locale=>window.BibliothekarI18n.setLocale(locale),locale);
await page.addScriptTag({content:`
const structurePreview=document.getElementById('structure-preview'),previewBody=document.getElementById('preview-body');
let selectedPreviewEventId=null,groups=[];
const selectedAllGroups=()=>groups,scheduleTreeFit=()=>{};
const escapeHtml=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const formatStoredDateTime=v=>v,workspaceStatusLabel=v=>v;
const bk0511PreviewLabel=(de,en)=>document.documentElement.dataset.bkLocale==='de'?de:en;
${bundle.preview}
${bundle.stored}
window.probePreview=(selected,event)=>{groups=selected==='day'?[{}]:[];selectedPreviewEventId=selected==='event'?'E':null;syncMobilePreviewButton();if(event)renderStoredEventPreview(event);};
`});
assert.equal(await page.locator('#mobile-preview-button').isVisible(),false);
await page.evaluate(()=>window.probePreview('day'));
assert.equal(await page.locator('#mobile-preview-button').isVisible(),true);
await page.locator('#mobile-preview-button').click();
assert.equal(await page.locator('#mobile-preview-dialog').evaluate(n=>n.open),true);
await page.locator('#mobile-preview-close').click();
assert.equal(await page.locator('#mobile-preview-dialog').evaluate(n=>n.open),false);
await page.evaluate(()=>window.probePreview('event',{event:{name:'< & Test',status:'planned',folder_name:'07-20 - < & Test'},structure_text:'2026/\n└── 07-20 - < & Test/\n    └── All/'}));
await page.locator('#mobile-preview-button').click();
assert.match(await page.locator('#mobile-preview-dialog').innerText(),/2026\/\n└── 07-20 - < & Test\//);
assert.equal(await page.locator('#structure-preview img,#structure-preview script').count(),0);
await page.screenshot({path:path.join(out,`preview-planned-${locale}.png`)});
await page.keyboard.press('Escape');
assert.equal(await page.locator('#mobile-preview-dialog').evaluate(n=>n.open),false);
assert.equal(await page.evaluate(()=>document.body.style.overflow),'');
assert.equal(await page.locator('aside.preview').evaluate(n=>n.parentElement.className),'workspace-layout');
await page.evaluate(()=>window.probePreview('event',{event:{name:'< & Test',status:'archived'},structure_text:'MUST NOT SHOW PLAN',physical_state:{available:true,event_prefix:'2026/07-20 - actual',tree_text:'All/\n   preserved.JPG'}}));
await page.locator('#mobile-preview-button').click();
assert.match(await page.locator('#mobile-preview-dialog').innerText(),/2026\/07-20 - actual/);
assert.doesNotMatch(await page.locator('#mobile-preview-dialog').innerText(),/MUST NOT SHOW PLAN/);
await page.setViewportSize({width:1280,height:900});
await page.waitForFunction(()=>!document.querySelector('#mobile-preview-dialog').open);
assert.equal(await page.locator('#mobile-preview-button').isVisible(),false);
assert.equal(await page.locator('aside.preview').isVisible(),true);
await page.setViewportSize({width:390,height:844});
// Actual day-card CSS; long user names remain fully readable.
await page.evaluate(()=>{document.querySelector('#day-list').innerHTML='<div class="day-card"><input type="checkbox"><span class="day-main"><span class="day-name">Monday, 07/20/2026 · &lt; &amp; Test</span><span class="day-meta">26 files · 13 families</span></span><span class="badge">Metadata confirmed</span></div>';});
assert.equal(await page.locator('.day-card>.badge').evaluate(n=>getComputedStyle(n).gridColumnStart),'2');
assert(await page.locator('.day-card').evaluate(n=>n.scrollWidth<=n.clientWidth));
await page.screenshot({path:path.join(out,`workspace-${locale}.png`)});
results.push({case:`R03/R05-${locale}`,status:'PASS',viewport:'390x844 and 1280x900',checks:'day/event selection, actual shared panel, full planned root, physical actual tree, escaping, close/Escape, scroll restoration, desktop, card geometry'});
}
// Real import renderer and translation observer, historical JSON and user labels.
await page.goto('about:blank');await page.setContent(strip(bundle.import));await page.addScriptTag({content:bundle.i18n});
await page.addScriptTag({content:`const openHistoryIds=new Set(['J']);${bundle.jobs}\nwindow.probeJob=job=>{document.querySelector('#notice').innerHTML=renderJob(job)};`});
const job={id:'J',operation:'folder_import',kind:'sd_import',trigger_type:'approved_sd',source_volume_label:'Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01',state:'completed',progress_message:'Ordnerimport erfolgreich abgeschlossen. 18 Mediendateien wurden verifiziert.',file_count:18,result:{source:{duplicate_file_count:90,duplicate_files:[{relative_path:'DSCF0603.JPG',existing_source_label:'Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01',existing_relative_path:'2026/07-20 - < & Test/All/DSCF0603.JPG'}]},organization:{devices:[{name:'Camera A'},{name:'Camera B'}]}}};
await page.evaluate(job=>window.probeJob(job),job);await page.waitForTimeout(100);
assert.equal(await page.locator('#notice .bk-history-text strong').innerText(),'SD Card Import · '+job.source_volume_label);
await page.locator('#notice details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
const visible=await page.locator('#notice').innerText();
assert.match(visible,/Import completed. 18 media files verified./);
assert.match(visible,/Time remaining:\s+done/);
assert.match(visible,/Already present in Mehrere Aufnahmegeräte - 2026.07.19 - 2026.10.01/);
assert.match(visible,/2026\/07-20 - < & Test\/All\/DSCF0603.JPG/);
const raw=await page.locator('#notice pre').innerText();assert.match(raw,/Ordnerimport erfolgreich abgeschlossen/);
assert.equal(await page.locator('#notice script').count(),0);
await page.screenshot({path:path.join(out,'import-en.png')});
await page.evaluate(job=>{window.BibliothekarI18n.setLocale('de');window.probeJob(job)},job);
assert.match(await page.locator('#notice .bk-history-text strong').innerText(),/SD-Kartenimport · Mehrere Aufnahmegeräte/);
await page.evaluate(()=>window.BibliothekarI18n.setLocale('en'));
results.push({case:'R02/R06-renderer',status:'PASS',checks:'historical success/remaining, opaque user label and path, duplicate prefix, raw German JSON retained, EN/DE'});
// History disclosure, using the actual renderer and actual mobile/desktop CSS.
await page.goto('about:blank');await page.setContent(strip(bundle.archive));await page.addScriptTag({content:bundle.i18n});
await page.addScriptTag({content:`const escapeHtml=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');const formatDate=v=>v||'—';const historyList=document.querySelector('#history-list');${bundle.history}${bundle.historyMedia}\ndocument.querySelector('#history-list').innerHTML='<div class="card"><div class="title" data-bk-preserve-language>Test 2</div><div class="path" data-bk-preserve-language>2026/07-21 - Test 5</div>'+archiveHistoryCounts({current_archive:{available:true,file_count:26,family_count:13,uncatalogued_file_count:0},verification_file_count:28,verification_completed_at:'2026-07-22'})+'</div>';syncArchiveHistoryDetails();`});
await page.waitForTimeout(100);
assert.equal(await page.locator('.archive-history-details').evaluate(n=>n.open),false);
assert.equal(await page.locator('.archive-history-details .meta').isVisible(),false);
assert.match(await page.locator('#history-list').innerText(),/26 files/);
await page.locator('.archive-history-details summary').click();assert.match(await page.locator('#history-list').innerText(),/28 files/);
await page.screenshot({path:path.join(out,'archive-expanded-en.png')});
await page.locator('.archive-history-details summary').click();await page.screenshot({path:path.join(out,'archive-compact-en.png')});
await page.setViewportSize({width:1280,height:900});
assert.equal(await page.locator('.archive-history-details .meta').isVisible(),true);
results.push({case:'R04-history',status:'PASS',checks:'current26 and historical28 retained, mobile collapsed/expanded, desktop history visible, labels and paths original'});
await context.close();
} finally {await browser.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));}
console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exitCode=1});
