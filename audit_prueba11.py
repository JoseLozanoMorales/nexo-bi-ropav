"""Opt-in real-provider acceptance checks; output stays under tmp/."""
import json
from pathlib import Path
import ai_chat
from test_prueba11 import DASH, PRED
from db import connect

records=[]
def run(name,prompt,history=None):
 messages=list(history or [])+[{'role':'user','content':prompt}]
 result=ai_chat.ask(messages)
 records.append({'id':name,'prompt':prompt,'response':result})
 Path('tmp/prueba11').mkdir(parents=True,exist_ok=True)
 Path('tmp/prueba11/results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 print(name, 'tools:',[t['name'] for t in result.get('tools',[])],flush=True)
 return result,messages+[{'role':'assistant','content':result['text'],'chart':result.get('chart'),'dashboard':result.get('dashboard')}]

box,_=run('boxplot','Haz un boxplot del importe de las ventas de 2025 por canal')
assert sum(b['count'] for b in box['chart']['boxes'])==277
# Independent SQL median, rather than comparing the renderer to itself.
with connect() as conn:
 rows=conn.execute("SELECT c.nombre_canal canal, percentile_cont(0.5) WITHIN GROUP (ORDER BY v.total_venta) mediana FROM public.ventas v JOIN public.canales_venta c ON c.id_canal=v.id_canal WHERE v.fecha_venta::date BETWEEN '2025-01-01' AND '2025-12-31' AND v.estado_venta<>'Cancelada' GROUP BY 1").fetchall()
 medians={r['canal']:round(float(r['mediana']),2) for r in rows}
assert all(b['median']==medians[b['label']] for b in box['chart']['boxes'])
dash,_=run('dashboard',DASH)
assert not dash['dashboard'].get('objective_id')
panels=[(c['semantic']['dimensiones'],c['semantic']['metrica']) for c in dash['dashboard']['charts']]
assert panels==[(['mes'],'ingresos'),(['region','producto'],'unidades'),(['categoria'],'margen')],panels
ranking=dash['dashboard']['charts'][1]
assert ranking['ranking']['top_per_group']==5 and len(ranking['labels'])==10
pred,_=run('forecast',PRED)
spec=pred['dashboard'];chart=spec['charts'][0]
assert chart['labels']==['2026-01','2026-02','2026-03'],chart['labels']
assert chart['filters']['desde']=='2024-01-01' and chart['filters']['hasta']=='2025-12-31'
assert abs(spec['kpis'][0]['value']-sum(chart['datasets'][0]['values']))<0.02
ideas,history=run('proposals','Propón cinco objetivos de análisis de negocio que podamos investigar con los datos de esta base')
assert not any(t['name'] in ('consultar_objetivos_dashboards','generar_dashboard_objetivo') for t in ideas.get('tools',[]))
follow,_=run('proposal-followup','Genera un dashboard del segundo objetivo para 2025',history)
assert follow.get('dashboard') and not follow['dashboard'].get('objective_id')
print('PASS: boxplot SQL, paneles, periodo/KPI predictivo, propuestas y seguimiento',flush=True)
