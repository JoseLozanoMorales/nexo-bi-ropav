const fs=require('node:fs');
const rows=JSON.parse(fs.readFileSync('tmp/battery-retest/results.json','utf8'));
const byId=Object.fromEntries(rows.map(r=>[r.id,r]));
const checks=[];
function check(id,name,test){const r=byId[id];checks.push({id,name,ok:!!r&&test(r)});}
check('context-A-3','Canales sin filtro inventado, total 1192 unidades',r=>!r.visibleText.includes('Otros')&&['401.00','398.00','393.00'].every(x=>r.visibleText.includes(x)));
check('regions-4','Sólo dos regiones con ventas',r=>r.visibleText.includes('**2**')&&!r.visibleText.includes('Insular'));
check('predictions-3','Dona por canal a un mes',r=>r.response.chart.type==='doughnut'&&r.response.chart.semantic.dimensiones.includes('canal')&&r.response.chart.forecast.horizon_months===1);
check('predictions-7','Tres métricas proyectadas por canal',r=>['ingresos','utilidad','unidades'].every(m=>r.response.dashboard.charts.some(c=>c.forecast&&c.semantic.metrica===m&&c.semantic.dimensiones.includes('canal'))));
check('invalid-8','Rechaza 50 meses sin fabricar otro horizonte',r=>!r.response.chart&&r.visibleText.includes('24'));
const report={cases:rows.length,technicalFailures:rows.filter(r=>r.status==='fail').map(r=>r.id),checks};
fs.writeFileSync('tmp/battery-retest/semantic-audit.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
process.exitCode=checks.every(c=>c.ok)?0:1;
