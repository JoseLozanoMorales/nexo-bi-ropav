const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 await page.goto('http://127.0.0.1:8000');
 const result=await page.evaluate(()=>{
  const chart={type:'pie',title:'Doce categorías de prueba',labels:Array.from({length:12},(_,i)=>'Categoría '+(i+1)),datasets:[{label:'Importes',values:Array(12).fill(10),color:'#11a99a'}],colors:['#11a99a'],source:'Prueba sintética',value_format:'currency'};
  const c=document.createElement('canvas');c.dataset.renderWidth='600';drawChatChart(c,chart);
  const ctx=c.getContext('2d'),scale=c.width/600;
  const colors=chart.labels.map((_,i)=>{const angle=-Math.PI/2+(i+.5)*2*Math.PI/12;const p=ctx.getImageData(Math.floor((300+Math.cos(angle)*40)*scale),Math.floor((170+Math.sin(angle)*40)*scale),1,1).data;return Array.from(p)});
  return {colors,legend:chartLegend(chart),number:chartNumber(46371.979999999996,chart),png:chartExportCanvas(chart).toDataURL()};
 });
 assert.equal(result.colors.length,12);assert(result.colors.every(p=>p[3]>0&&p.slice(0,3).some(v=>v<220)));
 assert(!result.legend.includes('undefined'));assert(!result.number.includes('99999'));
 await fs.mkdir('tmp/prueba9-fix',{recursive:true});await fs.writeFile('tmp/prueba9-fix/twelve-sectors.png',Buffer.from(result.png.split(',')[1],'base64'));
 console.log('PASS: 12 sectores visibles, leyenda completa y total con dos decimales');
 const records=JSON.parse(await fs.readFile('tmp/prueba9-fix/results.json','utf8'));
 const spec=records.find(r=>r.id==='predictions-7').response.dashboard;
 const [download]=await Promise.all([page.waitForEvent('download'),page.evaluate(s=>downloadDashboard(s),spec)]);
 await download.saveAs('tmp/prueba9-fix/dashboard-final.png');
 for(const id of ['prueba9-2','prueba9-3','prueba9-4','prueba9-5'])assert.equal(records.find(r=>r.id===id).response.chart.filters.hasta,'2024-03-31');
 assert.equal(records.find(r=>r.id==='prueba9-3').response.chart.labels.length,3);
 assert.deepEqual(records.find(r=>r.id==='prueba9-4').response.chart.semantic.dimensiones,['tipo_cliente']);
 assert(!records.find(r=>r.id==='reset9-3').response.chart.forecast);
 assert(records.find(r=>r.id==='reset9-6').response.dashboard);
 assert(spec.charts.every(c=>c.forecast));
 console.log('PASS: fechas, ranking, tipo de cliente, reinicio de contexto y dashboard predictivo');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
