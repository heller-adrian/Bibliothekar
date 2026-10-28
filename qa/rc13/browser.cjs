/* Actual render functions and CSS, synthetic API responses, offline Chromium. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const strip=s=>s.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const locale of ['en','de'])for(const width of [390,1280]){
const context=await browser.newContext({viewport:{width,height:1000},offline:true});await context.route('**/*',r=>r.abort());
const page=await context.newPage();await context.route('http://rc13.invalid/events',r=>r.fulfill({contentType:'text/html',body:strip(bundle.events)}));await page.goto('http://rc13.invalid/events');await page.evaluate(()=>document.documentElement.dataset.bkTheme='light');await page.addScriptTag({content:bundle.i18n});
await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
await page.addScriptTag({content:`
const changeRequestBody=document.getElementById('change-request-body'),changeRequestTitle=document.getElementById('change-request-title'),changeRequestSubtitle=document.getElementById('change-request-subtitle'),changeRequestDialog=document.getElementById('change-request-dialog'),changeRequestClose=document.getElementById('change-request-close');
const sortPlanBody=document.getElementById('sort-plan-body'),sortPlanTitle=document.getElementById('sort-plan-title'),sortPlanSubtitle=document.getElementById('sort-plan-subtitle'),sortPlanDialog=document.getElementById('sort-plan-dialog'),sortPlanCloseButton=document.getElementById('sort-plan-close-button');
let currentSortPlan=null,mandatoryMutationContext=null,mandatoryArchiveChangeContext=null;
const escapeHtml=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const formatBytes=n=>Number(n)+' B',planStatusLabel=x=>x,renderMessageList=rows=>rows.map(r=>'<p>'+escapeHtml(r.message)+'</p>').join('');
const setStatus=(s,error)=>{if(error)throw Error(s)},setChangeStepInUrl=()=>{},syncArchiveChangeContext=()=>false;
const scheduleVisibleTreeFit=()=>{};
${bundle.helpers}
${bundle.families}
${bundle.reversal}
${bundle.change}
${bundle.sort}
window.renderChange=async data=>{
 window.fetch=async url=>({ok:true,json:async()=>url.endsWith('/files')?data.rows:url.includes('/assistant')?data.assistant:data.cr});
 await showChangeRequestDetail('CR',{phase:data.phase,skipReversalCheck:true});
 if(!changeRequestDialog.open)changeRequestDialog.showModal();
};
window.renderReversal=async assistant=>{await showArchiveReversalDetail('CR',{assistant});if(!changeRequestDialog.open)changeRequestDialog.showModal()};
window.renderPlan=plan=>{if(changeRequestDialog.open)changeRequestDialog.close();renderSortPlan(plan);sortPlanDialog.showModal()};
`});
const archive='/Businessarchiv',work='/workspace/Library Workspaces/business',backup='/workspace/SD Card Backups';
const base={cr:{id:'CR',status:'aenderbar_bestaetigt',event_name:'Mein Ereignis'},rows:[{action:'delete',old_path:'2026/Mein Ereignis/All/A.JPG',workspace_release_path:'Released Archive Files/2026/A.JPG',verification_status:'verified'}],assistant:{event_name:'Mein Ereignis',path_labels:{archive_root:archive,work_root:work,backup_root:backup},preparation_required:true,preparation:{staging_root:work+'/Assign Later',missing_directories:['2026/Mein Ereignis'],incoming_file_count:1},operations:[{kind:'move_archive_files',title:'Dateien innerhalb der Kamerabibliothek verschieben',source:archive+'/2026/Mein Ereignis/All',target:archive+'/2026/Mein Ereignis/B/All',items:['A.JPG'],detail:'1 Datei in den angegebenen Zielordner verschieben.',state:'pending'}],target_structure:{lines:['2026','└── Mein Ereignis'],deleted:false},release_stock:{required:false}}};
for(const stage of ['prepare','copy_to_ssd','remove_archive','complete','verify']){
 const data=structuredClone(base);data.phase=stage==='prepare'?'prepare':stage==='verify'?'verify':'finder';
 if(stage==='copy_to_ssd'||stage==='remove_archive')data.assistant.release_stock={required:true,stage,root:'Released Archive Files',release_directory_name:'Released Archive Files',rows:base.rows,family_count:1,segments:[]};
 if(stage==='remove_archive')data.assistant.release_stock.folder_removal={qualified:true,path:archive+'/2026/Mein Ereignis'};
 await page.evaluate(d=>window.renderChange(d),data);await page.waitForTimeout(60);
 const body=await page.locator('#change-request-body').innerText();assert(!body.startsWith('Fehler:'),body);assert(!body.includes('${escapeHtml'),body);
 assert(!body.includes('Kamerabibliothek/')&&!body.includes('SD-Kartensicherungen/'),body);
 if(stage==='complete')assert(body.includes(archive+'/2026/Mein Ereignis'),body);
 if(locale==='en')assert(!/oder|Freigewordene|fehlende Ordner|Die App|Hilfsstrukturen|SSD/.test(body),body);
 await page.screenshot({path:path.join(out,`${locale}-${width}-${stage}.png`)});results.push({locale,width,stage,status:'PASS'});
}
for(const phase of ['prepare','finder','verify']){
 await page.evaluate(async({phase,archive,work})=>window.renderReversal({active:true,phase,path_labels:{archive_root:archive,work_root:work},original_root:'2026/Mein Ereignis',original_stock_path:work+'/Assign Later/Reversal/CR/Restoration/2026/Mein Ereignis',operations:[{kind:'restore_from_ssd',title:'Ursprünglichen Bestand aus Später zuordnen zurückkopieren',source:work+'/Assign Later/Reversal/CR/Restoration/2026/Mein Ereignis',target:archive+'/2026',state:'pending',items:['Mein Ereignis'],detail:'Fehlende ursprüngliche Ordner und Dateien aus dem vorbereiteten Rückänderungsbestand zurück in die alte Archivstruktur übernehmen.'}]}),{phase,archive,work});
 await page.waitForTimeout(60);const text=await page.locator('#change-request-body').innerText();
 if(locale==='en')assert(!/Finder|SSD|Vor diesem|Arbeitsbereich\/|Kamerabibliothek\//.test(text),text);
 await page.screenshot({path:path.join(out,`${locale}-${width}-reversal-${phase}.png`)});results.push({locale,width,stage:'reversal-'+phase,status:'PASS'});
}
await page.evaluate(()=>window.renderPlan({event:{name:'Mein Ereignis'},summary:{ready:true,file_count:2,family_count:1,target_group_count:1,total_size_bytes:24,same_filesystem:true},source_root:'/workspace/Library Workspaces/business',target_root:'/workspace/Library Workspaces/business',structure_lines:[],warnings:[{message:'Unterereignis „Teil A“ enthält aktuell keine Dateifamilien; die leere Ordnerstruktur wird trotzdem angelegt.'}],families:[{group_key:'F',family_id:1,display_name:'Original.JPG',file_count:2,file_ids:[],total_size_bytes:24,media_types:['raw','jpeg'],ready:true}],target_groups:[{target_relative_path:'2026/Mein Ereignis',family_group_keys:['F'],family_count:1,file_count:2,total_size_bytes:24,ready:true}]}));
await page.locator('.plan-target-group').evaluate(n=>n.open=true);await page.locator('.plan-family').evaluate(n=>n.open=true);await page.waitForTimeout(60);
const sort=await page.locator('#sort-plan-body').innerText();
if(locale==='en')assert(!/Familien|Dateien|Familie:|Einzeldateien|Dateisystem: ja|Unterereignis/.test(sort),sort);
await page.screenshot({path:path.join(out,`${locale}-${width}-nested-sort.png`)});results.push({locale,width,stage:'nested-sort',status:'PASS'});
await page.setContent(bundle.warning);
for(const choice of [locale==='en'?'de':'en',locale]){
 await page.locator('.bk-lang[data-lang="'+choice+'"]').click();await page.waitForTimeout(60);
 assert.equal(await page.locator('#storage-title').innerText(),choice==='en'?'Storage unavailable':'Speicherordner nicht verfügbar');
 assert.equal(await page.locator('.storage-copy').innerText(),choice==='en'?'Copy name':'Namen kopieren');
 assert.equal(await page.evaluate(()=>window.BibliothekarI18n.getLocale()),choice);
}
assert.equal(await page.locator('#storage-setup-blocker').count(),0);assert.equal(await page.locator('.storage-copy').getAttribute('data-copy'),'Trash');
await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined});document.execCommand=kind=>{window.rc13Copied={kind,value:document.activeElement.value};return true}});
await page.locator('.storage-copy').click();
assert.deepEqual(await page.evaluate(()=>window.rc13Copied),{kind:'copy',value:'Trash'});
assert.equal(await page.locator('textarea').count(),0);
await page.screenshot({path:path.join(out,`${locale}-${width}-storage.png`)});results.push({locale,width,stage:'storage',status:'PASS'});
await page.goto('http://rc13.invalid/events');await page.evaluate(()=>document.documentElement.dataset.bkTheme='light');await page.addScriptTag({content:bundle.i18n});await page.evaluate(l=>window.BibliothekarI18n.setLocale(l),locale);
await page.evaluate(()=>{window.mutations=0;window.fetch=async(_,options={})=>{if(options.method==='POST')window.mutations++;return {ok:true,json:async()=>({operations:[{kind:'apply',id:'batch-rc13',status:'applied',active:false,label:'Ereignisse anwenden',detail:'1 von 1 Ereignissen verarbeitet',href:'/events',progress_percent:100}]})}}});
await page.addScriptTag({content:bundle.activity});await page.waitForTimeout(60);
const activity=page.locator('.bk-page-activity');
if(width===390){assert(await activity.isVisible());if(locale==='en')assert((await activity.innerText()).includes('Apply events'));await page.locator('.bk-page-activity-dismiss').click();assert(!(await activity.isVisible()));await page.reload();await page.addScriptTag({content:bundle.i18n});await page.evaluate(()=>window.fetch=async()=>({ok:true,json:async()=>({operations:[{kind:'apply',id:'batch-rc13',status:'applied',active:false,label:'Ereignisse anwenden',href:'/events'}]})}));await page.addScriptTag({content:bundle.activity});await page.waitForTimeout(60);assert(!(await page.locator('.bk-page-activity').isVisible()));}
else{assert(!(await activity.isVisible()));await page.setViewportSize({width:390,height:1000});assert(await activity.isVisible());await page.setViewportSize({width:1280,height:1000});assert(!(await activity.isVisible()));}
results.push({locale,width,stage:'activity-dismiss-resize-reload',status:'PASS'});
await context.close();
}
fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({status:'PASS',cases:results},null,2));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
