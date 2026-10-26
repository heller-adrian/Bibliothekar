/* Offline warning UI only: no API requests, NAS, or installed application. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const pages=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});const results=[];
 try{
  for(const width of [390,1280])for(const lang of ['de','en'])for(const allowed of [false,true]){
   const context=await browser.newContext({viewport:{width,height:844},offline:true});await context.route('**/*',r=>r.abort());
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.setContent(pages[allowed?'allowed':'blocked']);await page.evaluate(lang=>window.BibliothekarI18n.setLocale(lang),lang);
   assert.equal(await page.locator('#storage-protection').isVisible(),true);
   assert.equal(await page.locator('#storage-initialize').count(),allowed?1:0);
   if(allowed){assert.equal(await page.locator('#storage-initialize').textContent(),lang==='en'?'Set up again':'Neu einrichten');}
   else{
    assert.equal(await page.locator('#storage-setup-blocker h2').textContent(),lang==='en'?'New setup is currently blocked':'Neue Einrichtung derzeit gesperrt');
    assert.equal(await page.locator('#storage-recovery-help').isVisible(),true);
    assert.match(await page.locator('#storage-recovery-help').textContent(),lang==='en'?/Do not delete operation records/:/Keine Operationsnachweise löschen/);
   }
   assert.equal(await page.locator('#storage-title').textContent(),lang==='en'?'Storage folder unavailable':'Speicherordner nicht verfügbar');
   assert.equal(await page.locator('#storage-protection li code').first().textContent(),'/workspace/Trash');
   const rect=await page.locator('#storage-protection').boundingBox();assert(rect.x>=0&&rect.x+rect.width<=width);
   assert.deepEqual(errors,[]);await page.screenshot({path:path.join(out,`${width}-${lang}-${allowed?'allowed':'blocked'}.png`)});
   results.push({width,lang,allowed,result:'PASS'});await context.close();
  }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;});
