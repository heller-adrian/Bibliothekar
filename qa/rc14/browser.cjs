/* Actual i18n and workspace renderer, each RC14 screenshot finding. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const cases=[['01','6 freie Familien','6 available families'],['02','Auftrag ist fehlgeschlagen.','Job failed.'],['03','Auftrag ist fehlgeschlagen.','Job failed.'],['04','Direkter IST→SOLL-Abgleich im SSD-Arbeitsbereich','Verifying current versus planned workspace state'],['05','3922 freie Familien','3922 available families'],['07','Der gespeicherte Bibliotheks-Arbeitsbereich ist nicht verfügbar: /workspace/Library Workspaces/business','The registered library workspace is unavailable: /workspace/Library Workspaces/business'],['08','Verwaltungsordner fehlen oder sind nicht eindeutig verfügbar. Vorgänge sind gesperrt.','Managed storage folders are missing or ambiguous. Operations are paused.'],['10','Ereignis gelöscht: Familienfest · 1 Familie wieder frei.','Event deleted: Familienfest · 1 family returned to unassigned inventory.'],['11','Technische ID: business-7a108c0a','Technical ID: business-7a108c0a'],['11','Prüfung PASS · Hardlinks zum Zentralbestand möglich.','Verification passed · hard links to central inventory are possible.'],['11','Bibliothek entfernen','Remove library'],['12','Der Arbeitsbereich muss ein absoluter Containerpfad sein.','Workspace must be an absolute container path.'],['13','Das Archiv überschneidet sich mit /main-library.','The archive overlaps with /main-library.'],['14','Ungeklärtes Import-Staging verhindert den Stammordnerwechsel.','Unresolved import staging prevents changing the library root.'],['15','im Arbeitsbereich erhalten.','in the workspace.'],['17','Wiederherstellung abgeschlossen','Restoration completed.']];
(async()=>{const browser=await chromium.launch({headless:true});const results=[];try{
for(const width of [320,390,1280]){
 const page=await browser.newPage({viewport:{width,height:1000}});
 await page.goto('about:blank');await page.setContent(bundle.workspace.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,''));await page.addScriptTag({content:bundle.i18n});
 for(const locale of ['en','de','en']){
  await page.evaluate(locale=>window.BibliothekarI18n.setLocale(locale),locale);
  for(const [screenshot,source,expected] of cases){
   const translated=await page.evaluate(source=>window.BibliothekarI18n.t(source),source);
   assert.equal(translated,locale==='en'?expected:source,`${screenshot} ${locale} ${source}`);
   results.push({screenshot,width,locale,status:'PASS'});
  }
 }
 await page.addScriptTag({content:`const dayList=document.createElement('div');dayList.className='days';document.body.replaceChildren(dayList);const selectedDays=new Set();let lastSelectedDayKey=null;const group={has_date:true,day_key:'2026-10-28',file_count:3,family_count:2,review_required_count:0,released_archive:true};const planningOverview=()=>({timeline_groups:[]}),releasedArchiveGroups=()=>[group],selectableDayKeys=()=>[group.day_key],mobilePreviewDoubleTap=()=>{},updateDaySelectAllButton=()=>{},syncMobilePreviewButton=()=>{},formatDay=x=>x,formatBytes=x=>String(x),renderSelection=()=>{};${bundle.days};renderDays();`});
 await page.waitForTimeout(50);
 const badges=page.locator('.day-statuses .badge');assert.equal(await badges.count(),2);
 const metrics=await badges.evaluateAll(nodes=>nodes.map(n=>{const s=getComputedStyle(n),r=n.getBoundingClientRect();return {font:s.fontSize,padding:s.padding,line:s.lineHeight,left:r.left,right:r.right,scroll:n.scrollWidth,client:n.clientWidth}}));
 assert.equal(metrics[0].font,metrics[1].font);assert.equal(metrics[0].padding,metrics[1].padding);for(const m of metrics){assert(m.left>=0&&m.right<=width);assert(m.scroll<=m.client+1)}
 await page.screenshot({path:path.join(out,`badges-${width}.png`)});results.push({screenshot:'06',width,status:'PASS'});await page.close();
}
fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({status:'PASS',cases:results},null,2));
}finally{await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
