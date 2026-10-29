const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true});const cases=[];
try{for(const lang of ['de','en'])for(const width of [390,1280])for(const critical of [false,true]){
 const requests=[],context=await browser.newContext({viewport:{width,height:900}});
 await context.addInitScript(l=>localStorage.setItem('bibliothekar-language',l),lang);
 await context.route('**/*',route=>{
  const req=route.request();requests.push({url:req.url(),method:req.method()});
  if(req.url()==='http://pre3.invalid/')return route.fulfill({contentType:'text/html',body:bundle.html});
  if(req.url().endsWith('/api/settings/recovery-diagnostics'))return route.fulfill({contentType:'application/json',body:JSON.stringify({mode:'authenticated_read_only',operations_allowed:false,
   libraries:[{display_name:'Main <script>alert(1)</script>',library_id:'main',work_root:'/workspace/Library Workspaces/main'}],
   operations:[{scope:critical?'storage_or_unknown':'single_file_requires_qualification',kind:critical?'unknown':'metadata',authorized_to_finish:false,
    task:critical?null:{source_relative_path:'<img src=x onerror="window.hacked=1">.JPG',status:'completed'},path:'/database/control/operation-example.json'}],startup_error:'synthetic recovery diagnosis'})});
  return route.abort();
 });
 const page=await context.newPage();await page.goto('http://pre3.invalid/');
 await page.locator('#storage-diagnostics-open').click();await page.locator('#storage-diagnostics-content pre').waitFor();
 assert.match(await page.locator('#storage-diagnostics-open').innerText(),lang==='de'?/Diagnose|diagnose/:/diagnosis/i);
 const text=await page.locator('#storage-diagnostics-content').innerText();assert.match(text,/operation-example/);assert.match(text,/Main <script>/);
 if(!critical)assert.match(text,/completed/);
 assert.equal(await page.locator('#storage-diagnostics-content img').count(),0);
 assert.equal(await page.evaluate(()=>window.hacked),undefined);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert(requests.every(r=>r.method==='GET'));assert.equal(requests.filter(r=>r.url.endsWith('/api/settings/recovery-diagnostics')).length,1);
 await page.screenshot({path:path.join(out,`${lang}-${width}-${critical?'storage':'file'}.png`),fullPage:true});
 cases.push({lang,width,critical,status:'PASS'});await context.close();
}}finally{await browser.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({cases,status:cases.length===8?'PASS':'FAIL'},null,2));}
})().catch(e=>{console.error(e);process.exit(1)});
