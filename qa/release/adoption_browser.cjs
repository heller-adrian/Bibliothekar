// Run only against a fresh disposable Bibliothekar installation with the RC2 test media.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const {BIBLIOTHEKAR_BROWSER_URL:url, BIBLIOTHEKAR_BROWSER_ARCHIVE:archive,
  BIBLIOTHEKAR_BROWSER_PASSWORD:password, BIBLIOTHEKAR_BROWSER_SCREENSHOTS:screenshots,
  CHROMIUM_EXECUTABLE:executablePath} = process.env;
assert.ok(url && archive && password, 'Set the disposable test URL, archive path and admin password');
const origin = new URL(url);
const expectedSecure=origin.protocol==='https:' || ['localhost','127.0.0.1','[::1]'].includes(origin.hostname);
async function capture(page,name){
  if(screenshots)await page.screenshot({path:path.join(screenshots,`${origin.port}-${name}.png`)});
}
(async()=>{
  const browser=await chromium.launch({
    executablePath,
    args:['--host-resolver-rules=MAP truenas.test 127.0.0.1','--no-proxy-server'],
  });
  try {
    const narrow=url.startsWith('https:');
    const page=await browser.newPage({ignoreHTTPSErrors:true,viewport:narrow?{width:390,height:844}:{width:1240,height:900}});
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
    const languageButtons=page.locator('.bk-setup-lang button');
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
    const brand=await page.locator('.bk-setup-brand').boundingBox();
    const card=await page.locator('main .card').boundingBox();
    assert.ok(brand.y+brand.height<=card.y, 'brand must not overlap form');
    await page.locator('#create').click();
    await page.locator('[data-decision=adopting]').click();
    await page.locator('#pick-source:enabled').waitFor();
    assert.equal(await page.locator('#source-root-label').isVisible(),false);
    await page.locator('#choice').click();
    await page.getByRole('link',{name:'Resume adoption'}).or(page.locator('.bk-setup-choice-actions a')).click();
    await page.locator('#pick-source:enabled').waitFor();
    await page.getByText("Can't see your dataset?",{exact:true}).click();
    await page.getByText(/shows folders on the target archive/).waitFor();
    await page.getByText("Can't see your dataset?",{exact:true}).click();
    await page.getByRole('button',{name:'camera-1',exact:true}).click();
    const parent=page.getByRole('button',{name:'‹ Parent folder',exact:true});
    await parent.waitFor();
    assert.equal(await parent.locator('xpath=following-sibling::code').count(),1);
    await parent.click();
    await page.locator('#pick-source:enabled').waitFor();
    await capture(page,'source');
    await page.locator('#pick-source').click();
    assert.equal(await page.locator('#pick-source').getAttribute('aria-pressed'),'true');
    assert.equal(await page.locator('#source-actions > #start').count(),1);
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
    await cards.nth(1).click({modifiers:['Shift']});
    await page.getByRole('button',{name:'+ Event',exact:true}).click();
    const name=editor.getByRole('textbox').first();
    await name.fill('Lan Test');
    assert.equal(await page.locator('#dirty').textContent(),'');
    assert.equal(await editor.locator('input[type=date]').first().inputValue(),'2026-07-19');
    assert.equal(await editor.locator('input[type=date]').last().inputValue(),'2026-07-21');
    await editor.getByRole('button',{name:'Add subevent',exact:true}).click();
    await editor.locator('input[type=text]').nth(1).fill('Child Test');
    await editor.locator('input[type=datetime-local]').first().fill('2026-07-21T12:00');
    await editor.locator('input[type=datetime-local]').last().fill('2026-07-21T13:00');
    await editor.getByRole('button',{name:'Target structure preview'}).click();
    await editor.locator('.adoption-structure-preview code').filter({hasText:'Child Test'}).first().waitFor();
    await capture(page,'editor');
    await editor.getByRole('button',{name:'Save in draft'}).click();
    await page.getByText('Lan Test',{exact:true}).waitFor();
    await page.getByText('One media family is still unassigned.',{exact:true}).waitFor();
    await page.reload();
    await page.locator('#draft-events summary').click();
    await page.locator('#draft-events').getByRole('button',{name:'Open',exact:true}).click();
    await page.locator('#draft-events .adoption-structure-preview code').filter({hasText:'Child Test'}).first().waitFor();
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
    await editor.getByRole('button',{name:'Save in draft'}).click();
    await editor.waitFor({state:'hidden'});
    assert.equal(await page.locator('#draft-events summary').count(),2);
    assert.equal(await page.getByText(/still unassigned/).count(),0);
    if(narrow){
      await page.locator('[data-bk-language-choice=de]').click();
      await page.locator('#bk-setup-theme').selectOption('dark');
      await page.getByRole('button',{name:'+ Ereignis',exact:true}).waitFor();
    }
    await capture(page,'plan');
    await page.getByRole('button',{name:/Next: Review plan|Weiter: Plan prüfen/}).click();
    await page.getByText(/Plan prepared|Plan vorbereitet/,{exact:true}).waitFor();
    assert.equal(errors.length,0,JSON.stringify(errors));
    console.log(url,features,'saved, reopened, edited and prepared plan with subevent and collection');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
