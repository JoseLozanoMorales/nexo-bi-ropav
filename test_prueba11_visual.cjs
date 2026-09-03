const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8000');
 const records=JSON.parse(await fs.readFile('tmp/prueba11/results.json','utf8'));
 const chart=records.find(r=>r.id==='boxplot').response.chart;
 const text=await page.evaluate(ch=>{const labels=[],original=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(t,...args){labels.push(String(t));return original.call(this,t,...args)};try{const c=document.createElement('canvas');c.dataset.renderWidth='340';drawChatChart(c,ch);return labels}finally{CanvasRenderingContext2D.prototype.fillText=original}},chart);
 assert(text.includes('Sociales')||text.includes('Redes Sociales'));assert(text.includes('Física')||text.includes('Tienda Física'));assert(text.includes('USD'));assert(text.length>=9);
 const png=await page.evaluate(ch=>chartExportCanvas(ch).toDataURL(),chart);await fs.writeFile('tmp/prueba11/boxplot.png',Buffer.from(png.split(',')[1],'base64'));
 for(const id of ['dashboard','forecast','proposal-followup']){
  const spec=records.find(r=>r.id===id).response.dashboard;
  await page.evaluate(s=>addChat('assistant','Resultado verificado',null,null,s),spec);
  const [download]=await Promise.all([page.waitForEvent('download'),page.evaluate(s=>downloadDashboard(s),spec)]);
  await download.saveAs('tmp/prueba11/'+id+'.png');
 }
 assert.equal(errors.length,0,errors.join('\n'));console.log('PASS: etiquetas de boxplot a 340px, PNG y tres dashboards sin errores JS');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
