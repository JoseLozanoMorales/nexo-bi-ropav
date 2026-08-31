// Browser QA in a fresh headless profile; never uses personal browser data.
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
 const out='tmp/objective-qa';await fs.mkdir(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  // Keep the test on localhost; embedded third-party BI services are out of scope.
  await page.route('**/*',route=>{const u=new URL(route.request().url());return ['127.0.0.1','localhost'].includes(u.hostname)?route.continue():route.abort()});
  await page.goto('http://127.0.0.1:8000');
  await page.locator('[data-view="adaptable"]').click();
  for(let i=1;i<=6;i++){
   await page.locator('#question').fill(`Genera el dashboard del objetivo ${i} en 2025`);
   await page.locator('#ask').click();
   const panel=page.locator('.ai-dashboard').last();
   await page.waitForFunction(n=>document.querySelectorAll('.ai-dashboard').length===n,i);
   await page.locator('#ask').waitFor({state:'visible'});
   assert.equal(await panel.locator('.dashboard-kpis article').count(),4);
   assert.ok(await panel.locator('.objective-context').count());
   assert.ok(await panel.locator('canvas').count());
   if(i!==3)assert.ok(await panel.locator('table').count());
   await panel.scrollIntoViewIfNeeded();
   await panel.screenshot({path:`${out}/objetivo-${i}.png`});
   const [download]=await Promise.all([page.waitForEvent('download'),panel.getByText('Descargar definición JSON',{exact:true}).click()]);
   const jsonPath=`${out}/objetivo-${i}.json`;await download.saveAs(jsonPath);
   const spec=JSON.parse(await fs.readFile(jsonPath,'utf8'));assert.equal(spec.objective_id,i);
   const [png]=await Promise.all([page.waitForEvent('download'),panel.getByText('Descargar PNG',{exact:true}).click()]);
   await png.saveAs(`${out}/objetivo-${i}-export.png`);
   console.log(`Objetivo ${i}: UI, tabla/gráficos, JSON y PNG OK`);
  }
  await page.reload();assert.equal(await page.locator('.ai-dashboard').count(),6);
  await page.setViewportSize({width:430,height:900});
  await page.locator('[data-view="adaptable"]').click();
  await page.locator('.ai-dashboard').last().screenshot({path:`${out}/movil.png`});
  assert.deepEqual(errors,[]);console.log('Restauración del chat, móvil y errores JavaScript: OK');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
