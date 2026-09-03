// End-to-end visual QA for catalog, dynamic dashboards and predictive charts.
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');

(async()=>{
 const out='tmp/predictive-qa';await fs.mkdir(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{const host=new URL(route.request().url()).hostname;return ['127.0.0.1','localhost'].includes(host)?route.continue():route.abort()});
  await page.goto('http://127.0.0.1:8000');await page.locator('[data-view="adaptable"]').click();
  async function send(prompt){
   await page.locator('#question').fill(prompt);await page.locator('#ask').click();
   await page.locator('.chat-loading').waitFor({state:'detached',timeout:90000});
   return page.locator('.chat-message.assistant').last();
  }

  let answer=await send('¿Cuántas regiones tenemos registradas en la base de datos?');
  const regionText=await answer.locator('.chat-bubble').innerText();
  for(const region of ['Costa','Sierra','Amazonía','Insular'])assert.ok(regionText.includes(region));
  assert.ok(regionText.lastIndexOf('Parámetros de la consulta')>regionText.lastIndexOf('Fuente:'));
  await answer.screenshot({path:`${out}/regiones-catalogo.png`});

  answer=await send('Genera un histograma predictivo de ingresos por región para los próximos 3 meses');
  assert.match(await answer.locator('.chat-chart h3').innerText(),/Pronóstico/i);
  assert.ok(await answer.locator('.chart-description').innerText().then(text=>text.includes('no una garantía')));
  const [chartPng]=await Promise.all([page.waitForEvent('download'),answer.locator('.chart-download').click()]);
  await chartPng.saveAs(`${out}/histograma-predictivo.png`);
  await answer.screenshot({path:`${out}/histograma-predictivo-ui.png`});

  answer=await send('Genera un dashboard sobre los productos personalizados más vendidos en cada región');
  const dashboard=answer.locator('.ai-dashboard');
  assert.match(await dashboard.locator('h2').innerText(),/personalizados.*región/i);
  assert.ok(await dashboard.getByText(/Unidades por región y producto/i).count());
  assert.ok(await dashboard.locator('.dashboard-download').count());
  await dashboard.screenshot({path:`${out}/dashboard-personalizados-region.png`});

  await page.setViewportSize({width:390,height:844});
  await dashboard.scrollIntoViewIfNeeded();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
  await dashboard.screenshot({path:`${out}/dashboard-movil.png`});
  assert.deepEqual(errors,[]);
  console.log('Catálogo de regiones, parámetros finales, predicción, PNG, dashboard dinámico y móvil: OK');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
