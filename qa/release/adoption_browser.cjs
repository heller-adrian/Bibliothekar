// Run only against a fresh disposable Bibliothekar installation with the RC2 test media.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs/promises');
const {execFileSync} = require('node:child_process');
const {BIBLIOTHEKAR_BROWSER_URL:url, BIBLIOTHEKAR_BROWSER_ARCHIVE:archive,
  BIBLIOTHEKAR_BROWSER_PASSWORD:password, BIBLIOTHEKAR_BROWSER_SCREENSHOTS:screenshots,
  CHROMIUM_EXECUTABLE:executablePath} = process.env;
assert.ok(url && archive && password, 'Set the disposable test URL, archive path and admin password');
const origin = new URL(url);
const expectedSecure=origin.protocol==='https:' || ['localhost','127.0.0.1','[::1]'].includes(origin.hostname);
async function capture(page,name){
  if(screenshots)await page.screenshot({path:path.join(screenshots,`${origin.port}-${name}.png`)});
}
async function finishManualAdoption(page){
  const archivePath=await fs.realpath(archive);
  const fixture=path.dirname(path.dirname(archivePath));
  const sourcePath=path.join(fixture,'synthetic-source');
  assert.equal(archivePath,path.join(fixture,'first-install','archive'));
  assert.ok(path.basename(fixture).startsWith('bibliothekar-rc3-browser-'));
  assert.equal(await fs.realpath(sourcePath),sourcePath);
  assert.equal(await page.locator('#introduction').getAttribute('open'),null);
  await page.locator('.adoption-target-preview summary').click();
  await page.locator('.adoption-target-preview ul ul code').filter({hasText:'Reopened Test'}).first().waitFor();
  await page.getByRole('button',{name:/Next: Choose execution|Weiter: Methode wählen/}).click();
  const panel=page.locator('#work section');
  await panel.getByRole('heading',{name:/Final safety confirmation|Verbindliche Sicherheitsbestätigung/}).waitFor();
  const order=await panel.evaluate(panel=>{
    const selectors=['h2','h2 + p','.adoption-plan-facts','details.adoption-proof',
      'details.adoption-proof + p','.adoption-target-preview','.adoption-card h3'];
    const elements=selectors.map(selector=>panel.querySelector(selector));
    if(elements.some(element=>!element))return selectors.filter((_,i)=>!elements[i]);
    return {
      inOrder:elements.every((item,i)=>i===0 || Boolean(elements[i-1].compareDocumentPosition(item)&Node.DOCUMENT_POSITION_FOLLOWING)),
      facts:elements[2].children.length,
    };
  });
  assert.deepEqual(order,{inOrder:true,facts:8});
  const methods=page.getByRole('radiogroup');
  const scriptMethod=methods.locator('[value=script]');
  const ack=page.getByLabel(/I confirm the safety conditions|Ich bestätige die Sicherheitsbedingungen/);
  const confirm=page.getByRole('button',{name:/Confirm and start|Durchführung verbindlich starten/});
  const actions=page.locator('.adoption-confirm-actions');
  const [prepare,read]=[actions.locator('button').nth(0),actions.locator('button').nth(1)];
  const preparedPlanId=await page.evaluate(async()=>{
    const job=new URL(location.href).searchParams.get('job');
    const response=await fetch(`/api/legacy-adoption/jobs/${job}`);
    if(!response.ok)throw new Error(await response.text());
    return (await response.json()).plan.id;
  });
  const probeRoute='**/api/legacy-adoption/jobs/*/script/probe';
  const confirmRoute='**/api/legacy-adoption/jobs/*/confirm';
  const prepared={verified:false,sha256:'a'.repeat(64),command:'python3 synthetic-host-check.py'};
  const verified={...prepared,verified:true,dataset:'synthetic/photos',
    host:{source:'/pool/photos/source',archive:'/pool/photos/archive'}};
  let probe={verified:false};
  await page.route(probeRoute,async route=>{
    if(route.request().method()==='POST')probe=prepared;
    await route.fulfill({json:probe});
  });
  const emptyProof=page.waitForResponse(response=>response.url().endsWith('/script/probe'));
  await scriptMethod.focus();
  await page.keyboard.press('Space');
  await emptyProof;
  await prepare.waitFor({state:'visible'});
  assert.equal(await scriptMethod.isChecked(),true);
  assert.equal(await read.isDisabled(),true);
  assert.equal(await ack.isDisabled(),true);
  assert.equal(await confirm.isDisabled(),true);
  const sequence=await actions.evaluate(group=>Array.from(group.children,element=>({
    name:element.tagName,hidden:element.getAttribute('aria-hidden'),left:element.offsetLeft,top:element.offsetTop,
  })));
  assert.deepEqual(sequence.map(element=>element.name),['BUTTON','SPAN','BUTTON','SPAN','BUTTON']);
  assert.ok(sequence.filter(element=>element.name==='SPAN').every(element=>element.hidden==='true'));
  if(page.viewportSize().width>640){
    assert.ok(sequence.every((element,i)=>i===0 || element.left>sequence[i-1].left));
  }else{
    assert.ok(sequence.every((element,i)=>i===0 || element.top>sequence[i-1].top));
  }
  await prepare.click();
  await page.locator('.adoption-command').waitFor();
  await read.click();
  await page.getByText(/No proof yet|Noch kein Nachweis/).waitFor();
  assert.equal(await ack.isDisabled(),true);
  assert.equal(await confirm.isDisabled(),true);
  probe=verified;
  await read.click();
  const proof=page.locator('.adoption-proof[data-verified=true]');
  await proof.waitFor();
  assert.ok(await proof.getByText(/Host paths and shared ZFS dataset verified|Hostpfade und gemeinsames ZFS-Dataset bestätigt/).isVisible());
  assert.ok(await proof.evaluate(element=>parseFloat(getComputedStyle(element).borderInlineStartWidth)>0));
  assert.equal(await ack.isDisabled(),false);
  assert.equal(await confirm.isDisabled(),true);
  assert.ok((await ack.boundingBox()).y>(await proof.boundingBox()).y);
  await capture(page,'verified-execution');
  await ack.check();
  assert.equal(await confirm.isEnabled(),true);
  probe={...verified,sha256:'b'.repeat(64)};
  await read.click();
  await page.locator('.adoption-confirm-actions button').nth(1).and(page.locator('button:enabled')).waitFor();
  assert.equal(await ack.isChecked(),false);
  assert.equal(await confirm.isDisabled(),true);
  await ack.check();
  let confirmPayload;
  await page.route(confirmRoute,async route=>{
    confirmPayload=route.request().postDataJSON();
    await route.fulfill({status:409,json:{detail:'Synthetic stop before file operations'}});
  });
  await confirm.click();
  await page.getByText('Synthetic stop before file operations',{exact:true}).waitFor();
  assert.deepEqual(confirmPayload,{plan_id:preparedPlanId,method:'script',acknowledged:true,probe_sha256:probe.sha256});
  await page.unroute(confirmRoute);
  await page.unroute(probeRoute);
  await methods.locator('[value=manual]').check();
  assert.equal(await ack.isChecked(),false);
  assert.equal(await ack.isDisabled(),false);
  assert.equal(await confirm.isDisabled(),true);
  await capture(page,'execution');
  await page.getByLabel(/I confirm the safety conditions|Ich bestätige die Sicherheitsbedingungen/).check();
  await page.getByRole('button',{name:/Confirm and start|Durchführung verbindlich starten/}).click();
  for (const [name,file] of [[/Empty folder structure|Leeres Ordnergerüst/,'folders.zip'],
                            [/^Event documents$|^Ereignisdokumente$/,'documents.zip']]) {
    const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('link',{name}).click()]);
    const zip=path.join(fixture,file);
    await download.saveAs(zip);
    execFileSync('unzip',['-oq',zip,'-d',archivePath]);
  }
  const moves=await page.evaluate(async()=>{
    const job=new URL(location.href).searchParams.get('job');
    const response=await fetch(`/api/legacy-adoption/jobs/${job}/moves`);
    if(!response.ok)throw new Error(await response.text());
    return response.json();
  });
  assert.equal(moves.length,6);
  for (const {source,target} of moves) {
    assert.ok((await fs.realpath(source)).startsWith(sourcePath+path.sep));
    assert.ok((await fs.realpath(path.dirname(target))).startsWith(archivePath+path.sep));
    await fs.rename(source,target);
  }
  await page.getByRole('button',{name:/Next: Verify archive|Weiter: Archiv prüfen/}).click();
  await page.getByRole('button',{name:/^Verify archive$|^Archiv prüfen$/}).click();
  await page.locator('#wizard-navigation').getByRole('button',{name:/Register adoption|Übernahme registrieren/}).click();
  await page.getByRole('heading',{name:/Collection adoption complete|Bestandsübernahme abgeschlossen/}).waitFor();
  assert.ok(await page.locator('main.adoption-complete h1').evaluate(heading=>heading.scrollWidth<=heading.clientWidth));
  await page.getByText(/Show verification record|Prüfnachweis anzeigen/,{exact:true}).click();
  await page.getByText(/SHA-256 of the confirmed plan|SHA-256 des bestätigten Plans/).waitFor();
  await capture(page,'completion');
  await page.getByRole('link',{name:/Adoption history|Übernahmehistorie/}).click();
  await page.getByRole('link',{name:/View completed adoption|Abschluss anzeigen/}).click();
  await page.getByRole('link',{name:'Reopened Test',exact:true}).click();
  await page.locator('#event-edit-dialog[open]').waitFor();
  await page.locator('.event-card .status-chip.archived').first().waitFor();
  const plans=page.locator('#summary .card').filter({hasText:/Plans eligible for deletion|Deletable plans|Löschbare Planungen/i});
  assert.equal(await plans.locator('strong').textContent(),'0');
  const emptyFilter=page.waitForResponse(response=>{
    const requested=new URL(response.url());
    return requested.pathname==='/api/workspace/summary' && requested.searchParams.get('jobs')==='';
  });
  await page.goto(new URL('/workspace',page.url()).href);
  assert.equal((await emptyFilter).status(),200);
}
(async()=>{
  const browser=await chromium.launch({
    executablePath,
    args:['--host-resolver-rules=MAP truenas.test 127.0.0.1','--no-proxy-server'],
  });
  try {
    const narrow=url.startsWith('https:');
    const width=narrow?390:origin.hostname==='localhost'?820:1240;
    const page=await browser.newPage({ignoreHTTPSErrors:true,viewport:{width,height:900}});
    page.setDefaultTimeout(10000);
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(url);
    const login=await page.evaluate(async value=>{
      const response=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({password:value})});
      return response.status;
    },password);
    assert.equal(login,200);
    await page.goto(url);
    const features=await page.evaluate(()=>({secure:isSecureContext,uuid:typeof crypto.randomUUID}));
    assert.equal(features.secure,expectedSecure);
    await page.locator('#bk-setup-theme').selectOption('light');
    const languageButtons=page.locator('.bk-setup-banner [data-bk-language-choice]');
    assert.equal(await page.locator('.bk-setup-banner #bk-setup-theme').count(),1);
    assert.equal(await languageButtons.first().evaluate(x=>getComputedStyle(x).color),
                 await languageButtons.last().evaluate(x=>getComputedStyle(x).color));
    assert.equal(await page.locator('#bk-setup-theme').evaluate(x=>getComputedStyle(x).borderRadius),'8px');
    await page.locator('#name').fill('Synthetic Main');
    await page.locator('#archive').fill('invalid-relative-path');
    await page.locator('#create').click();
    await page.getByText('The archive must be an absolute container path.',{exact:true}).waitFor();
    await languageButtons.last().click();
    await page.getByText('Das Archiv muss ein absoluter Containerpfad sein.',{exact:true}).waitFor();
    await languageButtons.first().click();
    await page.locator('#archive').fill(archive);
    await capture(page,'setup');
    const brand=await page.locator('.bk-setup-banner').boundingBox();
    const card=await page.locator('main .card').boundingBox();
    assert.ok(brand.y+brand.height<=card.y, 'brand must not overlap form');
    await page.locator('#create').click();
    await page.locator('[data-decision=adopting]').click();
    await page.locator('#pick-source:enabled').waitFor();
    assert.equal(await page.locator('#source-root-label').isVisible(),false);
    await page.locator('#choice').click();
    await page.getByRole('link',{name:'Resume adoption'}).or(page.locator('.bk-setup-choice-actions a')).click();
    await page.locator('#pick-source:enabled').waitFor();
    if(narrow){
      await page.locator('[data-bk-language-choice=de]').click();
      await page.locator('#bk-setup-theme').selectOption('dark');
    }
    const help=page.locator('#source-help > summary');
    assert.equal(await help.textContent(),narrow?'Fehlt dein Dataset?':"Can't see your dataset?");
    const bubble=page.locator('#source-help > p');
    const folders=page.locator('.adoption-folder-grid');
    await help.scrollIntoViewIfNeeded();
    const before=await folders.boundingBox();
    await help.click();
    await bubble.waitFor();
    await page.waitForFunction(()=>document.querySelector('#source-help').style.getPropertyValue('--adoption-help-offset'));
    const trigger=await help.boundingBox();
    const overlay=await bubble.boundingBox();
    assert.ok(overlay.y>=trigger.y+trigger.height && overlay.y-trigger.y-trigger.height<=8);
    assert.ok(overlay.x>=0 && overlay.x+overlay.width<=page.viewportSize().width);
    assert.ok(overlay.x<trigger.x+trigger.width && overlay.x+overlay.width>trigger.x);
    const left=await bubble.evaluate(element=>Math.min(element.parentElement.getBoundingClientRect().left,
      document.documentElement.clientWidth-16-element.offsetWidth));
    assert.ok(Math.abs(left-overlay.x)<=1);
    assert.deepEqual(await folders.boundingBox(),before);
    await capture(page,'source-help');
    await help.click();
    await bubble.waitFor({state:'hidden'});
    await help.click();
    await page.keyboard.press('Escape');
    assert.equal(await bubble.isVisible(),false);
    await page.getByRole('button',{name:'camera-1',exact:true}).click();
    const parent=page.getByRole('button',{name:/^‹ (Parent folder|Übergeordneter Ordner)$/});
    await parent.waitFor();
    assert.equal(await parent.locator('xpath=following-sibling::code').count(),1);
    const sourceActions=await page.locator('#source-actions').boundingBox();
    assert.ok((await parent.boundingBox()).y-sourceActions.y-sourceActions.height>=10);
    await parent.click();
    await page.locator('#pick-source:enabled').waitFor();
    await capture(page,'source');
    if(narrow){
      await page.locator('[data-bk-language-choice=en]').click();
      await page.locator('#bk-setup-theme').selectOption('light');
    }
    await page.locator('#pick-source').click();
    assert.equal(await page.locator('#pick-source').getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('#source-actions > #start').count(),1);
    assert.equal(await page.locator('#source-help').isVisible(),false);
    await page.locator('#start').click();
    if(process.env.BIBLIOTHEKAR_BROWSER_DELAYED_SCAN==='1'){
      await page.getByText('Reading photo collection…',{exact:true}).waitFor();
      await page.reload();
      await page.getByText('Reading photo collection…',{exact:true}).waitFor();
      assert.equal(await page.getByRole('button',{name:/Restart inventory|Resume inventory/}).count(),0);
    }
    await page.getByRole('button',{name:'Next: Plan events'}).click();
    const editor=page.locator('#event-editor');
    await page.getByRole('button',{name:'+ Event',exact:true}).click();
    assert.equal(await editor.locator('input[type=date]').first().inputValue(),'');
    await page.keyboard.press('Escape');
    await editor.waitFor({state:'hidden'});
    const cards=page.locator('.day-card');
    await cards.nth(0).click();
    await page.locator('#planning-preview').getByText(/1 file family · 2 files|1 family · 2 files/i).waitFor();
    await cards.nth(1).click({modifiers:['Shift']});
    await page.getByRole('button',{name:'+ Event',exact:true}).click();
    const name=editor.getByRole('textbox').first();
    await name.fill('Lan Test');
    assert.equal(await page.locator('#dirty').textContent(),'');
    assert.equal(await editor.locator('input[type=date]').first().inputValue(),'2026-07-19');
    assert.equal(await editor.locator('input[type=date]').last().inputValue(),'2026-07-21');
    assert.deepEqual(await editor.locator('input[type=time]').evaluateAll(fields=>fields.map(field=>field.value)),['00:00','23:59']);
    await editor.getByRole('button',{name:'Add subevent',exact:true}).click();
    await editor.locator('input[type=text]').nth(1).fill('Child Test');
    await editor.locator('input[type=datetime-local]').first().fill('2026-07-21T12:00');
    await editor.locator('input[type=datetime-local]').last().fill('2026-07-21T13:00');
    await editor.getByRole('button',{name:'Add subevent',exact:true}).click();
    assert.equal(await editor.locator('input[type=datetime-local]').nth(2).inputValue(),'2026-07-21T13:01');
    page.once('dialog',dialog=>dialog.accept());
    await editor.getByRole('button',{name:'Remove subevent',exact:true}).last().click();
    await editor.getByRole('button',{name:'Target structure preview'}).click();
    await editor.locator('.adoption-folder-tree ul ul ul code').filter({hasText:'Child Test'}).first().waitFor();
    await capture(page,'editor');
    await editor.getByRole('button',{name:'Save in draft'}).click();
    await page.getByText('Lan Test',{exact:true}).waitFor();
    await page.getByText('One media family is still unassigned.',{exact:true}).waitFor();
    assert.equal(await cards.count(),1);
    await page.reload();
    await page.locator('#draft-events summary').click();
    await page.locator('#planning-preview .adoption-structure-preview code').filter({hasText:'Child Test'}).first().waitFor();
    await capture(page,'selected-event');
    await page.locator('#draft-events').getByRole('button',{name:'Edit',exact:true}).click();
    assert.equal(await editor.getByRole('textbox').first().inputValue(),'Lan Test');
    assert.equal(await editor.locator('input[type=text]').nth(1).inputValue(),'Child Test');
    await editor.getByRole('textbox').first().fill('Reopened Test');
    await editor.getByRole('button',{name:'Save in draft'}).click();
    await page.getByText('Reopened Test',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Clear selection'}).click();
    await cards.last().click();
    await page.getByRole('button',{name:'+ Collection folder without event',exact:true}).click();
    assert.equal(await editor.locator('input[type=date]').inputValue(),'2026-07-24');
    await editor.locator('input[type=time]').first().fill('12:00');
    await editor.locator('input[type=time]').last().fill('13:00');
    await editor.getByRole('button',{name:'Save in draft'}).click();
    await editor.waitFor({state:'hidden'});
    assert.equal(await page.locator('#draft-events summary').count(),2);
    assert.equal(await page.getByText(/still unassigned/).count(),0);
    assert.equal(await page.locator('#wizard-steps button:enabled').count(),0);
    await page.locator('#wizard-navigation').getByRole('button',{name:'Back',exact:true}).click();
    const declineRescan=async dialog=>{
      assert.match(dialog.message(),/draft|Entwurf/i);
      await dialog.dismiss();
    };
    page.once('dialog',declineRescan);
    await page.getByRole('button',{name:/Restart inventory|Inventur erneut starten/}).click();
    await page.getByRole('button',{name:'Next: Plan events'}).click();
    await page.locator('#draft-events summary').nth(1).waitFor();
    if(narrow){
      await page.locator('[data-bk-language-choice=de]').click();
      await page.locator('#bk-setup-theme').selectOption('dark');
      await page.getByRole('button',{name:'+ Ereignis',exact:true}).waitFor();
    }
    await capture(page,'plan');
    await page.getByRole('button',{name:/Next: Review plan|Weiter: Plan prüfen/}).click();
    await page.getByText(/Plan prepared|Plan vorbereitet/,{exact:true}).waitFor();
    if(process.env.BIBLIOTHEKAR_BROWSER_FINISH==='1')await finishManualAdoption(page);
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(url,features,'saved, reopened, edited and prepared plan with subevent and collection');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
