const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const [host,out]=process.argv.slice(2);assert(new URL(host).hostname==='127.0.0.1');fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const cases=[];
try{for(const lang of ['de','en'])for(const width of [390,1440]){
const context=await browser.newContext({viewport:{width,height:900}});
await context.addInitScript(l=>localStorage.setItem('bibliothekar-language',l),lang);
await context.route('**/*',r=>new URL(r.request().url()).origin===host?r.continue():r.abort());
const page=await context.newPage();await page.goto(host+'/login');await page.locator('#password').fill('isolated-pre5-test-password');
const serverErrors=[],optionalChecks=[];
page.on('response',r=>{
 if(r.status()<500)return;
 const error={url:r.url(),status:r.status()};
 // This fixture explicitly disables the optional SD/USB helper. Its native
 // device endpoint reports 503; validate that exact body, never exempt other
 // 503s (especially health) or turn a hidden HTTP500 into a passing browser.
 if(r.status()===503&&new URL(r.url()).pathname==='/api/source-devices'){
  optionalChecks.push(r.json().then(data=>{
   if(data.detail!=='Quellen-Helfer ist nicht erreichbar.')serverErrors.push({...error,body:data});
  }).catch(failure=>serverErrors.push({...error,read_error:String(failure)})));
 }else serverErrors.push(error);
});
await Promise.all([page.waitForURL(host+'/'),page.locator('#login button').click()]);
await page.waitForLoadState('networkidle');
for(const target of ['/','/trash']){
await page.goto(host+target);await page.waitForLoadState('networkidle');const note=page.locator('#bibliothekar-operation-notice');await note.waitFor();
assert.match(await note.innerText(),lang==='de'?/unabhängige Aktionen bleiben verfügbar/:/independent actions remain available/);
assert(!(await page.locator('body').innerText()).includes('Storage unavailable'));
const health=await context.request.get(host+'/api/settings/storage-health');assert.equal(health.status(),200);
const status=await health.json();assert.equal(status.state,'READY');assert.equal(status.operation_health.writes_allowed,false);assert.equal(status.operation_health.workspace_writes_allowed,true);
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
if(target==='/'){
 const helper=await context.request.get(host+'/api/source-devices');
 assert.equal(helper.status(),503);assert.equal((await helper.json()).detail,'Quellen-Helfer ist nicht erreichbar.');
 assert(await page.locator('#sd-import-button').isDisabled());
 const diagnosis=page.locator('#database-diagnosis');const card=page.locator('#database-status-card');
 assert.equal(await diagnosis.isVisible(),false,'healthy database diagnosis starts collapsed');
 await card.click();
 const summary=diagnosis.locator(':scope > summary');
 assert(await summary.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'diagnosis summary is clipped');
 assert.equal(await card.getAttribute('aria-expanded'),'true');
 await page.waitForFunction(()=>document.querySelector('#database-diagnosis-result')?.textContent.includes('schema_current'));
 const report=JSON.parse(await page.locator('#database-diagnosis-result').textContent());
 assert.equal(report.database.connected,true);assert.equal(report.database.schema_current,true);
 assert.equal(report.database.automatic_repair,false);assert.equal(report.operation_health.workspace_writes_allowed,true);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await card.click();assert.equal(await diagnosis.isVisible(),false);
}
await page.screenshot({path:path.join(out,`${lang}-${width}-${target==='/'?'import':'trash'}.png`),fullPage:true});
cases.push({lang,width,target,status:'PASS'});
}await Promise.all(optionalChecks);assert.deepEqual(serverErrors,[],'live browser requests returned unexpected server errors');await context.close();}
}finally{await browser.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({cases,status:cases.length===8?'PASS':'FAIL'},null,2));}
})().catch(e=>{console.error(e);process.exit(1)});
