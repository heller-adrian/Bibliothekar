const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const b=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=process.argv[3];fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});let cases=[];try{
for(const locale of ['en','de'])for(const width of [390,1280]){
 const page=await browser.newPage({viewport:{width,height:1000}});
 await page.setContent('<html><body><div id="messages"></div><p id="meta-status"></p><button id="meta-general-reintegrate">In Tagesbestand übernehmen</button></body></html>');
 await page.addScriptTag({content:b.i18n});await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
 await page.evaluate(messages=>{for(const source of Object.keys(messages)){const p=document.createElement('p');p.textContent=source;document.querySelector('#messages').append(p)}},b.messages);
 await page.waitForTimeout(100);
 const text=await page.locator('#messages p').allTextContents();
 const expected=locale==='en'?Object.values(b.messages):Object.keys(b.messages);assert.deepEqual(text,expected);
 // Real General progress/restore handlers, synthetic durable backend job.
 const a=b.metadata.indexOf('  function syncGeneralBusy('),z=b.metadata.indexOf('  async function reintegrateSelected(',a);
 await page.addScriptTag({content:`const state={area:"general",generalJob:null,generalSubmitting:false,generalPolling:false};const $=id=>document.getElementById(id);let scans=0,tasks=0,statuses=[],queued=0;const setStatus=(s)=>statuses.push(s),scan=async()=>scans++,loadTasks=async()=>tasks++;let terminal=false;const json=async url=>url==='/api/jobs'?{jobs:[{id:'J',operation:'metadata_general_import',state:'running'}]}:{id:'J',state:terminal?'completed':'running',progress_percent:42};let pending;window.setTimeout=(fn)=>{pending=fn;};${b.metadata.slice(a,z)};window.restoreGeneral=restoreGeneralJob;window.finishGeneral=async()=>{terminal=true;await pending();};window.generalState=()=>({state,scans,tasks,statuses});`});
 await page.evaluate(()=>window.restoreGeneral());await page.waitForTimeout(20);
 assert(await page.locator('#meta-general-reintegrate').isDisabled());assert.equal(await page.locator('#meta-general-reintegrate').getAttribute('aria-busy'),'true');
 await page.evaluate(()=>window.finishGeneral());assert(!(await page.locator('#meta-general-reintegrate').isDisabled()));
 const state=await page.evaluate(()=>window.generalState());assert.equal(state.scans,1);assert.equal(state.tasks,1);assert.equal(state.state.generalJob,null);
 await page.screenshot({path:path.join(out,`${locale}-${width}-messages.png`)});cases.push({locale,width,stage:'screenshot-messages-and-General-reload',status:'PASS'});await page.close();
}
fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({status:'PASS',cases},null,2));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
