// Real UI/API regression battery; isolated profiles and read-only business requests.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const groups=[
 ['prueba9',true,['Genera un histograma de las ventas del año 2024','Limita el intervalo al primer trimestre de 2024','Ahora hazte un gráfico de pastel sobre los 3 meses con mas ventas','Ahora crea un gráfico de barras con los tipos de clientes','Ahora crea un gráfico de barras con los tipos de clientes y las ventas de cada uno']],
 ['reset9',true,['Pronostica ingresos tres meses','Quiero un gráfico de dona de los ingresos por canal en 2025','Cámbialo a pastel','Ahora en unidades','Ponlo en un dashboard','Descárgalo']],
 ['context-A',true,['Dime las ventas totales de 2025','Ahora en unidades','Desglósalo por canal','De dona','Ahora por región','Solo personalizados','Ponlo en un dashboard','Descárgalo']],
 ['context-B',true,['¿Cuál fue el producto más vendido en 2024?','¿Y en 2025?','Compáralos','En barras horizontales','Ahora por región','Proyecta tres meses']],
 ['confirm',true,['Quiero un gráfico de dona de los ingresos por canal en 2025','Procede','Cámbialo a pastel','Hazlo','Ahora en unidades','Adelante']],
 ['dashboards',false,['Dashboard de unidades vendidas por talla y color','Dashboard de ingresos por método de pago y canal','Dashboard de utilidad por proveedor y categoría','Dashboard de clientes por rango de edad y género','Dashboard de productos personalizados más vendidos en cada provincia','Dashboard del ticket promedio por canal y tipo de cliente','Dashboard de promociones, categorías y margen porcentual','Dashboard de entregas por región y estado de entrega']],
 ['predictions',false,['Pronostica los ingresos mensuales de los próximos 6 meses','Genera un gráfico de líneas con la proyección de unidades por región para 2026','Haz una dona predictiva de ingresos por canal para el próximo mes','Genera un mapa de calor predictivo de unidades por provincia para los próximos 4 meses','Quiero un Pareto predictivo de productos por ingresos','Genera un boxplot predictivo por región','Dashboard predictivo de ingresos, utilidad y unidades por canal']],
 ['regions',true,['¿Cuántas regiones están registradas en la base?','Muéstrame todas','Incluye las que no tienen ventas','Ahora dime únicamente cuáles tuvieron ventas','Incluye también las canceladas','Preséntalo en una tabla']],
 ['charts',false,['Histograma del importe de las ventas de 2025 con 12 intervalos','Boxplot del importe por provincia','Mapa de calor mensual de ingresos por provincia','Barras apiladas de unidades por trimestre, categoría y canal','Dispersión de unidades e ingresos por producto','Pareto de productos por ingresos','Área de ingresos mensuales por región','Dona de unidades por categoría','Pastel de ingresos por método de pago','Barras horizontales de utilidad por proveedor']],
 ['ambiguous',false,['Genera las ventas por género','Genera un dashboard de ventas','Compara región y provincia','Muéstrame los clientes con más compras','Dime el producto líder','Hazlo por este año','Ahora por allí','Cambia eso','Muéstrame los mejores','Procede']],
 ['invalid',false,['Ventas del 1 al 31 de febrero de 2025','Ventas desde 2025-12-31 hasta 2025-01-01','Pronostica ventas de una región inexistente','Gráfico de ventas de 2030','Dona con una métrica que no se puede sumar: margen por producto','Histograma de clientes por región','Dashboard con exactamente cero gráficos','Proyecta 50 meses','Top 500 productos','Filtra por canal Telegram']],
 ['recommend',true,['Recomiéndame ropa para el calor','Solo talla M','Máximo 35 dólares','Dame otra opción','Ahora para una ocasión formal','¿Cuál tiene más stock?','Compáralas en una tabla']]
];
const out=process.env.QA_OUT||'tmp/battery-qa';
const selected=process.env.QA_GROUPS?groups.filter(g=>process.env.QA_GROUPS.split(',').includes(g[0])):groups;
(async()=>{
 await fs.mkdir(out,{recursive:true});const results=[];const browser=await chromium.launch({channel:'chrome',headless:true});let cursor=0;
 async function worker(){while(cursor<selected.length){const [group,chain,prompts]=selected[cursor++];const context=await browser.newContext({viewport:{width:1280,height:900}});const page=await context.newPage();
 try{
 await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
 await page.goto('http://127.0.0.1:8000');await page.locator('[data-view="adaptable"]').click();
 for(let i=0;i<prompts.length;i++){
  if(!chain&&i)await page.locator('#newChat').click();
  const record={id:`${group}-${i+1}`,group,prompt:prompts[i],issues:[],status:'review'},start=Date.now();let errors=[];
  const listener=e=>errors.push(e.message);page.on('pageerror',listener);
  try{
   await page.locator('#question').fill(record.prompt);
   const pending=page.waitForResponse(r=>r.url().endsWith('/api/chat')&&r.request().method()==='POST',{timeout:120000});
   await page.locator('#ask').click();const response=await pending;record.http=response.status();record.response=await response.json();
   await page.locator('.chat-loading').waitFor({state:'detached',timeout:15000});
   const answer=page.locator('.chat-message.assistant').last();record.visibleText=await answer.innerText();
   if(errors.length)record.issues.push(...errors);
   if(await answer.locator('.chart-error').count())record.issues.push('Error de renderizado');
   if(record.http>=500)record.issues.push('Error del servidor');
   const specs=[...(record.response.chart?[record.response.chart]:[]),...(record.response.dashboard?.charts||[])];
   record.chartTypes=specs.map(s=>s.type);
   if(specs.length){
    if(!await answer.locator('canvas,table').count())record.issues.push('Visual sin canvas ni tabla');
    const button=answer.locator(record.response.dashboard?'.dashboard-download':'.chart-download').first();
    try{const [download]=await Promise.all([page.waitForEvent('download',{timeout:15000}),button.click()]);await download.saveAs(`${out}/${record.id}.png`);const bytes=await fs.readFile(`${out}/${record.id}.png`);if(bytes.length<1000||bytes.subarray(1,4).toString()!=='PNG')record.issues.push('PNG inválido');record.pngBytes=bytes.length;}catch(e){record.issues.push('Descarga: '+e.message.slice(0,200));}
   }
   if(group==='charts'&&!specs.length)record.issues.push('Falta gráfico solicitado');
   if(group==='dashboards'&&!record.response.dashboard)record.issues.push('Falta dashboard solicitado');
   if(group==='predictions'&&!specs.some(s=>s.forecast))record.issues.push('Falta pronóstico solicitado');
   if(group==='context-A'&&i<=6){for(const s of specs)if(s.filters?.desde&&!s.filters.desde.startsWith('2025'))record.issues.push('Perdió el año 2025');}
   if(record.issues.length)await answer.screenshot({path:`${out}/${record.id}-failure.png`}).catch(()=>{});
   record.status=record.issues.length?'fail':'technical-pass';
  }catch(e){record.status='fail';record.issues.push(e.message.slice(0,400));}
  page.off('pageerror',listener);record.ms=Date.now()-start;results.push(record);await fs.writeFile(`${out}/${record.id}.json`,JSON.stringify(record,null,2));
  await fs.writeFile(`${out}/results.json`,JSON.stringify(results,null,2));console.log(`${record.id} ${record.status} ${record.ms}ms ${record.issues.join('; ')}`);
  if(record.ms>120000)break;
 }
 }finally{await context.close();}}
 }
 try{await Promise.all([worker(),worker(),worker()]);}finally{await browser.close();}
 console.log(`DONE ${results.length} cases; ${results.filter(r=>r.status==='fail').length} technical failures. Semantic validation required.`);
})().catch(e=>{console.error(e);process.exitCode=1});
