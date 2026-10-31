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
const serverErrors=[];page.on('response',r=>{if(r.status()>=500)serverErrors.push({url:r.url(),status:r.status()});});
await Promise.all([page.waitForURL(host+'/'),page.locator('#login button').click()]);
for(const target of ['/','/trash']){
await page.goto(host+target);const note=page.locator('#bibliothekar-operation-notice');await note.waitFor();
assert.match(await note.innerText(),lang==='de'?/unabhängige Aktionen bleiben verfügbar/:/independent actions remain available/);
assert(!(await page.locator('body').innerText()).includes('Storage unavailable'));
const health=await context.request.get(host+'/api/settings/storage-health');assert.equal(health.status(),200);
const status=await health.json();assert.equal(status.state,'READY');assert.equal(status.operation_health.writes_allowed,false);assert.equal(status.operation_health.workspace_writes_allowed,true);
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
if(target==='/'){
 const diagnosis=page.locator('#database-diagnosis');const summary=diagnosis.locator('summary');
 assert(await summary.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'diagnosis summary is clipped');
 await summary.click();await page.waitForFunction(()=>document.querySelector('#database-diagnosis-result')?.textContent.includes('schema_current'));
 const report=JSON.parse(await page.locator('#database-diagnosis-result').innerText());
 assert.equal(report.database.connected,true);assert.equal(report.database.schema_current,true);
 assert.equal(report.database.automatic_repair,false);assert.equal(report.operation_health.workspace_writes_allowed,true);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await summary.click();
}
await page.screenshot({path:path.join(out,`${lang}-${width}-${target==='/'?'import':'trash'}.png`),fullPage:true});
cases.push({lang,width,target,status:'PASS'});
}assert.deepEqual(serverErrors,[],'live browser requests returned server errors');await context.close();}
}finally{await browser.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({cases,status:cases.length===8?'PASS':'FAIL'},null,2));}
})().catch(e=>{console.error(e);process.exit(1)});
