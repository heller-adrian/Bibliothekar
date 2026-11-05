/* Offline synthetic task-card test. No NAS, server, cookies or real requests. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
 const rows=[];
 try{
  for(const width of [390,1280])for(const theme of ['light','dark']){
   const context=await browser.newContext({viewport:{width,height:844},offline:true});await context.route('**/*',r=>r.abort());
   const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.setContent(bundle.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,''));
   await page.evaluate(theme=>{
    document.documentElement.dataset.bkTheme=theme;
    window.BibliothekarI18n={t:v=>v==='Prüfung abbrechen'?'Cancel check':v};
    window.fetch=async()=>({ok:true,json:async()=>({operations:[{id:'SYNTHETIC',kind:'sd_check',active:true,status:'verifying',progress_percent:22,label:'Synthetic source',detail:'Checking complete source'}]})});
   },theme);
   await page.addScriptTag({content:bundle.script});
   if(width>900){await page.locator('.bk-activity-collapse').waitFor({state:'visible'});await page.locator('.bk-activity-collapse').click();}
   await page.waitForFunction(()=>document.querySelector('.bk-activity-mini-count')?.textContent==='22%');
   const actual=await page.evaluate(()=>{
    const mini=document.querySelector('.bk-activity-mini'),count=document.querySelector('.bk-activity-mini-count'),card=document.querySelector('.bk-activity-card'),icon=document.querySelector('.bk-activity-mini .bk-activity-icon');
    const m=getComputedStyle(mini),c=getComputedStyle(count),p=getComputedStyle(card),ring=getComputedStyle(icon),r=mini.getBoundingClientRect();
    return {mini:m.backgroundColor,count:c.backgroundColor,card:p.backgroundColor,image:m.backgroundImage,countImage:c.backgroundImage,text:count.textContent,animation:ring.animationName,visible:!mini.hidden,fits:r.right<=innerWidth&&r.left>=0};
   });
   assert.equal(actual.mini,actual.count);assert.equal(actual.card,actual.count);assert.equal(actual.image,'none');assert.equal(actual.countImage,'none');assert.equal(actual.text,'22%');assert.equal(actual.visible,true);assert.equal(actual.fits,true);assert.notEqual(actual.animation,'none');
   await page.screenshot({path:path.join(out,`task-${width}-${theme}.png`)});
   await page.locator('.bk-activity-mini').click();assert.equal(await page.locator('.bk-activity-card').isVisible(),true);
   assert.equal(await page.locator('.bk-activity-card button').filter({hasText:'Cancel check'}).count(),1);
   assert.deepEqual(errors,[]);rows.push({width,theme,result:'PASS',...actual});await context.close();
  }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));
})().catch(e=>{console.error(e);process.exitCode=1;});
