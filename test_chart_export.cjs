const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({acceptDownloads:true}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  await page.goto('http://127.0.0.1:8000');
  await page.waitForFunction(()=>typeof chartExportCanvas==='function');
  await page.locator('[data-view="adaptable"]').click();
  const base={title:'Ventas de prueba — PNG',description:'Datos ficticios para verificar la descarga, no resultados del negocio.',source:'Prueba local',
   labels:['Canal A','Canal B'],colors:['#11a99a','#ff9f68'],datasets:[{label:'Ingresos',values:[120,80],color:'#11a99a'}]};
  const charts=['bar','line','area','pie','doughnut','histogram'].map(type=>({...base,type}));
  charts.push({...base,type:'bar',orientation:'horizontal'},
   {...base,type:'scatter',points:[{label:'A',x:1,y:2},{label:'B',x:3,y:5}]},
   {...base,type:'boxplot',boxes:[{label:'A',min:1,q1:3,median:5,q3:7,max:9,outliers:[12]}]},
   {...base,type:'heatmap',x_labels:['Ene','Feb'],y_labels:['A','B'],matrix:[[1,2],[3,4]]},
   {...base,type:'stacked_bar',stacks:[{label:'2025',datasets:base.datasets}]},
   {...base,type:'pareto',datasets:[...base.datasets,{label:'Acumulado',values:[60,100],color:'#ff9f68'}]},
   {...base,type:'line',secondary_axis:true,datasets:[...base.datasets,{label:'Margen',values:[30,40],axis:'right',color:'#ff9f68'}]},
   {...base,type:'treemap',objective_visual:true,nodes:[{group:'Grupo',label:'A',value:120},{group:'Grupo',label:'B',value:80}]},
   ...['table','matrix'].map(type=>({...base,type,objective_visual:true,columns:[{key:'nombre',label:'Nombre',format:'text'},{key:'valor',label:'Importe',format:'currency'}],rows:[{nombre:'A',valor:120},{nombre:'B',valor:80}]})),
   {...base,type:'bar',objective_visual:true,datasets:[{label:'Variación',values:[-20,40],color:'#11a99a'}]});
  await fs.mkdir('tmp/chart-export-qa',{recursive:true});
  for(const [i,chart] of charts.entries()){
   const before=JSON.stringify(chart);
   await page.evaluate(ch=>addChat('assistant','Prueba de exportación','',ch),chart);
   const downloadPromise=page.waitForEvent('download');
   await page.locator('.chart-download').last().click();
   const download=await downloadPromise;
   assert.equal(await download.failure(),null);
   const path='tmp/chart-export-qa/'+i+'-'+chart.type+'.png';
   await download.saveAs(path);
   const bytes=await fs.readFile(path);
   assert.equal(bytes.subarray(1,4).toString(),'PNG');
   assert.equal(bytes.readUInt32BE(16),1200);assert.ok(bytes.readUInt32BE(20)>300);
   assert.ok(bytes.length>5000);
   assert.equal(JSON.stringify(chart),before);
  }
  await page.evaluate(ch=>addChat('assistant','Dashboard','',null,{title:'Prueba',kpis:[],charts:[ch]}),charts[0]);
  assert.equal(await page.locator('.ai-dashboard .chart-download').count(),1);
  await page.evaluate(()=>{HTMLCanvasElement.prototype.toBlob=function(callback){callback(null)}});
  await page.locator('.chart-download').last().click();
  await page.waitForFunction(()=>[...document.querySelectorAll('[role="status"]')].some(n=>n.textContent.includes('no pudo crear')));
  assert.equal(await page.locator('.chart-download').last().isEnabled(),true);
  assert.deepEqual(errors,[]);
  console.log(charts.length+' variantes PNG descargadas; botón en dashboard y recuperación de errores OK');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
