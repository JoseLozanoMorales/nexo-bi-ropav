"""Read-only PostgreSQL regression and fixtures for visual QA."""
import json
from pathlib import Path
from semantic_analytics import query_semantic, chart_contract
from dashboard_builder import _planned_dashboard
f={'desde':'2025-01-01','hasta':'2025-12-31'}
plan={'title':'Ingresos y ticket promedio por mes y promoción','kpis':['ingresos','ticket_promedio','transacciones'],'charts':[{'dimensions':['mes','promocion'],'metric':m,'type':'line','limit':500} for m in ['ingresos','ticket_promedio']]}
dashboard=_planned_dashboard(f,plan)
ticket=dashboard['charts'][1]
raw=query_semantic(['mes','promocion'],'ticket_promedio',f,500)['datos']
lookup={(r['etiqueta'],r['serie']):r['valor'] for r in raw}
missing=0
for d in ticket['datasets']:
 for i,month in enumerate(ticket['labels']):
  key=(month,d['label'])
  if key not in lookup:
   missing+=1;assert d['values'][i] is None
  else:assert d['values'][i]==lookup[key]
assert missing==30
assert len({d['color'] for d in ticket['datasets']})==11
margin=chart_contract({'dimensions':['categoria'],'metric':'margen','type':'bar'},f)
Path('tmp/prueba12').mkdir(parents=True,exist_ok=True)
Path('tmp/prueba12/results.json').write_text(json.dumps({'dashboard':dashboard,'margin':margin},ensure_ascii=False),encoding='utf-8')
print('PASS: 30 huecos sin ceros inventados, valores restantes coinciden con SQL y 11 colores distintos')
