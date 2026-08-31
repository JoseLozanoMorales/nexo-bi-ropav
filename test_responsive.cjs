const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  await fs.mkdir('tmp/responsive-qa',{recursive:true});
  for(const [width,height] of [[320,740],[360,800],[390,844],[768,1024],[844,390],[1024,768],[1440,1000]]){
   await page.setViewportSize({width,height});await page.goto('http://127.0.0.1:8000');
   await page.waitForFunction(()=>document.querySelector('#salesBody').children.length>0);
   const overflow=()=>page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
   let size=await overflow();assert.ok(size.scroll<=size.width+1,JSON.stringify({width,view:'standard',size}));
   await page.locator('#newSale').click();assert.ok(await page.locator('#saleDialog').isVisible());await page.locator('#cancelDialog').click();
   if(width<=1000){
    await page.locator('#menuToggle').click();assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'true');
    await page.keyboard.press('Escape');assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'false');
    await page.locator('#menuToggle').click();
   }
   await page.locator('[data-view="adaptable"]').click();
   if(width<=1000)await page.locator('#mainSidebar').waitFor({state:'hidden'});
   if(width<=800){
    await page.locator('.history-toggle').click();assert.ok(await page.locator('.chat-history').isVisible());
    await page.locator('.history-toggle').click();
   }
   await page.locator('#question').fill('Primera línea');await page.locator('#question').press('Shift+Enter');await page.locator('#question').press('a');
   assert.ok((await page.locator('#question').inputValue()).includes('\n'));
   await page.evaluate(()=>addChat('assistant','Dashboard de prueba','',null,{
    title:'Dashboard de ventas y clientes con un título extenso',source:'Datos simulados para validar diseño',
    kpis:[{label:'Ingresos',value:123456.78,format:'currency'},{label:'Transacciones',value:330}],
    charts:[{title:'Participación por canal',type:'doughnut',labels:['Tienda Física','WhatsApp','Redes Sociales'],colors:['#11a99a','#ff9f68','#56c5d0'],datasets:[{label:'Ingresos',values:[114,109,107]}]}]
   }));
   await page.locator('.ai-dashboard').waitFor();
   size=await overflow();assert.ok(size.scroll<=size.width+1,JSON.stringify({width,view:'chat',size}));
   const composer=await page.locator('.chat-composer').boundingBox();assert.ok(composer.y+composer.height<=height+2,JSON.stringify({width,composer,height}));
   await page.screenshot({path:'tmp/responsive-qa/chat-'+width+'.png',animations:'disabled'});
   console.log(width+'x'+height+': sin desbordamiento, menú, chat y formulario OK');
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
