/* Real UI functions; synthetic responses; every browser request stays offline. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const b=JSON.parse(fs.readFileSync(process.argv[2])),out=process.argv[3];fs.mkdirSync(out,{recursive:true});
const strip=s=>s.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
(async()=>{const browser=await chromium.launch({headless:true});const results=[];try{
for(const locale of ['en','de'])for(const width of [390,1280]){
 const ctx=await browser.newContext({offline:true,viewport:{width,height:1000}});
 await ctx.route('**/*',r=>r.fulfill({contentType:'text/html',body:'<main>Isolated destination</main>'}));
 const page=await ctx.newPage();await page.goto('http://pre6.invalid/');await page.setContent(strip(b.index));
 await page.addScriptTag({content:b.i18n});await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
 await page.addScriptTag({content:`(()=>{const formatBytes=n=>String(n);let fixtureHealth={version:'pre6',status:'ok',errors:[],runtime:{uid:568,gid:568},database:{initialized:true,schema_versions:[1,55]},paths:{workspace:{writable:true,available_bytes:123}}};window.fetch=async url=>({ok:true,json:async()=>url==='/api/health'?fixtureHealth:{database:{ok:true}}});${b.database};window.checkHealth=loadHealth;window.damageDatabase=()=>{fixtureHealth.database={initialized:false,error:'synthetic integrity error'}};${b.backup};window.isSelectable=selectableBackup;})()`});
 assert.equal(await page.locator('#database-diagnosis').isVisible(),false);
 await page.locator('#database-status-card').click();assert.equal(await page.locator('#database-status-card').getAttribute('aria-expanded'),'true');
 await page.locator('#database-status-card').press('Enter');assert.equal(await page.locator('#database-diagnosis').isVisible(),false);
 await page.locator('#database-status-card').press('Space');assert.equal(await page.locator('#database-diagnosis').isVisible(),true);
 await page.locator('#database-status-card').click();await page.evaluate(()=>checkHealth());assert.equal(await page.locator('#database-diagnosis').isVisible(),false);
 await page.evaluate(()=>{damageDatabase();return checkHealth()});assert.equal(await page.locator('#database-diagnosis').isVisible(),true);
 const choices=await page.evaluate(()=>['completed','queued','verifying','failed','interrupted','blocked'].map(state=>isSelectable({state,workflow_status:'planned',active_family_count:0,total_family_count:0})));
 assert.deepEqual(choices,[false,true,true,true,true,true]);
 assert(await page.evaluate(()=>isSelectable({state:'completed',workflow_status:'archived',active_family_count:0,total_family_count:5})));
 await page.screenshot({path:path.join(out,`${locale}-${width}-database.png`)});results.push({locale,width,finding:'UX03/F04',status:'PASS'});
 await page.setContent('<div id="meta-open-tasks"></div>');await page.addScriptTag({content:b.i18n});await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
 await page.addScriptTag({content:`(()=>{const $=id=>document.getElementById(id),esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');let state={area:'general',tasks:[{id:'D',area:'general',source_filename:'synthetic.dng',status:'blocked',error_message:'Error: [minor] DNG Version 1.7.0.0 not yet tested'}]};const applyTask=()=>{throw Error('Unsupported task executed')},cancelTask=()=>{};${b.meta};renderTasks();})()`});
 await page.locator('#meta-open-tasks details').first().evaluate(n=>n.open=true);
 assert(await page.locator('[data-meta-apply]').isDisabled());assert(await page.locator('[data-meta-cancel]').isEnabled());
 assert.equal(await page.locator('#meta-open-tasks pre').isVisible(),false);
 await page.waitForTimeout(60);const dngText=await page.locator('#meta-open-tasks').innerText();assert(dngText.includes(locale==='en'?'Safe writing':'derzeit nicht sicher'));
 results.push({locale,width,finding:'DNG communication',status:'PASS'});
 await page.setContent(strip(b.events));await page.addScriptTag({content:b.i18n});await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
 await page.addScriptTag({content:`(()=>{
const changeRequestBody=document.getElementById('change-request-body'),changeRequestTitle=document.getElementById('change-request-title'),changeRequestSubtitle=document.getElementById('change-request-subtitle'),changeRequestDialog=document.getElementById('change-request-dialog'),changeRequestClose=document.getElementById('change-request-close');
let mandatoryArchiveChangeContext=null;const escapeHtml=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');const formatBytes=n=>String(n),setStatus=()=>{},setChangeStepInUrl=()=>{},syncArchiveChangeContext=()=>false,scheduleVisibleTreeFit=()=>{};
${b.helpers}\n${b.families}\n${b.change}
window.renderChange=async verified=>{window.fetch=async url=>({ok:true,json:async()=>url.endsWith('/files')?[{verification_status:verified?'verified':'missing',old_path:'A.JPG'}]:url.includes('/assistant')?{event_name:'synthetic',preparation_required:true,path_labels:{archive_root:'/read-only-archive',work_root:'/workspace/Library Workspaces/main'},operations:[{kind:'move_archive_files',title:'Move',source:'/read-only-archive/old',target:'/read-only-archive/new',state:'done'}],review_files:[]}:{id:'CR',status:'aenderbar_bestaetigt',event_name:'synthetic'}});await showChangeRequestDetail('CR',{phase:'verify',skipReversalCheck:true});if(!changeRequestDialog.open)changeRequestDialog.showModal();};
let verifiedResponse=false;const requestJson=async()=>({complete:verifiedResponse,file_count:1,verified_file_count:verifiedResponse?1:0,files:[],directories:[],obsolete_directories:[]});window.verifySuccess=()=>{verifiedResponse=true};})()`});
 await page.evaluate(()=>renderChange(true));assert.equal(await page.locator('[data-cr-back]').isVisible(),false);assert(await page.locator('[data-cr-archive]').isEnabled());
 assert.equal(await page.locator('[data-change-step]').count(),3);assert(await page.locator('[data-change-step="finder"]').isEnabled());
 await page.evaluate(()=>renderChange(false));assert.equal(await page.locator('[data-cr-back]').isVisible(),false);
 await page.locator('[data-cr-verify]').click();assert.equal(await page.locator('[data-cr-back]').isVisible(),true);assert(await page.locator('[data-cr-archive]').isDisabled());
 assert(await page.locator('[data-cr-back]').evaluate(n=>n.parentElement.classList.contains('change-footer')));
 await page.evaluate(()=>verifySuccess());await page.locator('[data-cr-verify]').click();assert.equal(await page.locator('[data-cr-back]').isVisible(),false);assert(await page.locator('[data-cr-archive]').isEnabled());
 await page.screenshot({path:path.join(out,`${locale}-${width}-archive.png`)});results.push({locale,width,finding:'UX04',status:'PASS'});
 await page.close();await ctx.close();
}
// Execute actual workspace save handler. The result must navigate to pending
// preview for the canonical event job; no apply or physical-refresh call.
const ctx=await browser.newContext({offline:true});await ctx.route('**/*',r=>r.fulfill({body:'<main>pending preview</main>'}));const page=await ctx.newPage();await page.goto('http://pre6.invalid/workspace');await page.setContent('<dialog id="e"></dialog>');
await page.addScriptTag({content:`(()=>{const anchorJobIdForSelection=()=> 'new-source',selectedDatedGroups=()=>[],activeNoEventTarget={id:'E'},existingNoEventTarget={value:'E'},collectEventPayload=()=>({no_event_segments:[{day_key:'2026-07-24'}]}),payloadForAllSources=x=>x;const workspace={events:[{id:'E',job_id:'old-anchor'}]},dialogMode='existing_no_event',selectedDays=new Set();let physicalCalls=0;const loadWorkspace=async()=>{physicalCalls++;throw Error('Unexpected physical refresh')};const postWithCanonicalMembership=async(url,body)=>{if(!url.includes('old-anchor'))throw Error('Wrong job');return {resort_required:true,event_id:'E',target_job_id:'old-anchor',assigned_family_count:16}};const element=()=>document.createElement('div'),saveResult=element(),saveEventButton=element(),calculatePreviewButton=element(),dialogError=element(),eventDialog=document.getElementById('e');${b.save};window.saveActualEvent=saveEvent;})()`});
await Promise.all([page.waitForURL('**/events?job=old-anchor&task=resort:E'),page.evaluate(()=>saveActualEvent())]);results.push({finding:'UX02 actual save handler',status:'PASS'});await ctx.close();
fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({status:'PASS',cases:results},null,2));console.log(JSON.stringify({status:'PASS',cases:results.length}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
