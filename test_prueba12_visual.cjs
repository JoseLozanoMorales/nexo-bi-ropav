const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs/promises');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8000');
 const data=JSON.parse(await fs.readFile('tmp/prueba12/results.json','utf8'));
 const observed=await page.evaluate(()=>{
  const calls=[],texts=[],proto=CanvasRenderingContext2D.prototype,oldLine=proto.lineTo,oldArc=proto.arc,oldText=proto.fillText;
  proto.lineTo=function(...a){calls.push(['line',...a]);return oldLine.apply(this,a)};proto.arc=function(...a){calls.push(['arc',...a]);return oldArc.apply(this,a)};proto.fillText=function(t,...a){texts.push(String(t));return oldText.call(this,t,...a)};
  try{const c=document.createElement('canvas');c.dataset.renderWidth='400';drawChatChart(c,{type:'line',semantic:{},labels:['Enero','Febrero','Marzo','Abril'],datasets:[{label:'A',color:'#119988',values:[10,null,20,0]}],value_format:'moneda'});return {calls,texts}}finally{proto.lineTo=oldLine;proto.arc=oldArc;proto.fillText=oldText}
 });
 assert(observed.texts.includes('USD'));assert(observed.texts.includes('Febrero'));assert.equal(observed.calls.filter(c=>c[0]==='arc').length,3);
 // Five grid lines and just one data segment (March to real zero in April).
 assert.equal(observed.calls.filter(c=>c[0]==='line').length,6);
 await page.evaluate(s=>addChat('assistant','Comprobación de promociones','',null,s),data.dashboard);
 const [download]=await Promise.all([page.waitForEvent('download'),page.evaluate(s=>downloadDashboard(s),data.dashboard)]);await download.saveAs('tmp/prueba12/promociones.png');
 for(const [name,ch] of [['ticket',data.dashboard.charts[1]],['margin',data.margin]]){const png=await page.evaluate(ch=>chartExportCanvas(ch).toDataURL(),ch);await fs.writeFile('tmp/prueba12/'+name+'.png',Buffer.from(png.split(',')[1],'base64'))}
 assert.equal(errors.length,0,errors.join('\n'));console.log('PASS: huecos sin segmentos falsos, cero real, escala USD y exportaciones sin errores JS');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
