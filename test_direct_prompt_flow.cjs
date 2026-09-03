// Visual conversation test using deliberately short follow-up prompts.
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{
 const out='tmp/direct-flow-qa';await fs.mkdir(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{const host=new URL(route.request().url()).hostname;return ['127.0.0.1','localhost'].includes(host)?route.continue():route.abort()});
  await page.goto('http://127.0.0.1:8000');await page.locator('[data-view="adaptable"]').click();
  async function send(prompt){
   await page.locator('#question').fill(prompt);await page.locator('#ask').click();
   await page.locator('.chat-loading').waitFor({state:'detached',timeout:90000});
   const answer=page.locator('.chat-message.assistant').last();
   assert.equal(await answer.locator('.chart-error').count(),0,prompt);
   return answer;
  }
  let answer=await send('Ingresos por canal en 2025. En barras.');
  assert.ok(await answer.locator('.chat-chart').count());

  answer=await send('De dona.');
  assert.ok(await answer.locator('.chat-chart').count());
  assert.match(await answer.locator('.chat-bubble').innerText(),/Gráfico actualizado/i);

  answer=await send('Ahora por provincia.');
  assert.match(await answer.locator('.chat-chart h3').innerText(),/provincia/i);

  answer=await send('Cambia ingresos por unidades.');
  assert.match(await answer.locator('.chat-chart h3').innerText(),/Unidades por provincia/i);

  answer=await send('Solo personalizados.');
  assert.match(await answer.locator('.chat-bubble').innerText(),/personalizado.*Sí/is);

  answer=await send('Ponlo en un dashboard.');
  const dashboard=answer.locator('.ai-dashboard');assert.ok(await dashboard.count());
  assert.match(await dashboard.locator('h2').innerText(),/Unidades por provincia/i);
  const [png]=await Promise.all([page.waitForEvent('download'),dashboard.locator('.dashboard-download').click()]);
  await png.saveAs(`${out}/dashboard-desde-frases-cortas.png`);

  answer=await send('Proyecta tres meses.');
  assert.ok(await answer.locator('.ai-dashboard').count());
  assert.equal(await answer.getByText('Pronóstico de unidades por provincia',{exact:true}).count(),1);
  assert.match(await answer.locator('.chat-bubble').innerText(),/"horizonte_meses": 3/);
  await page.locator('#answer').screenshot({path:`${out}/flujo-completo.png`});
  assert.deepEqual(errors,[]);
  console.log('Flujo directo: dona, provincia, unidades, personalizados, dashboard, PNG y pronóstico: OK');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
