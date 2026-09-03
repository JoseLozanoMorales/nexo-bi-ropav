"""Local audit: no provider calls, no business-data writes."""
import json
from pathlib import Path
from unittest.mock import patch
import ai_chat
from db import connect,regions_catalog
from semantic_analytics import query_semantic
from forecasting import _linear

checks=[]
def check(name,actual,expected):
    checks.append(dict(name=name,actual=actual,expected=expected,ok=actual==expected))

with connect() as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    rows=conn.execute("""SELECT c.nombre_canal canal,COUNT(*)::int total
      FROM public.ventas v JOIN public.canales_venta c USING(id_canal)
      WHERE v.estado_venta<>'Cancelada' AND v.fecha_venta::date BETWEEN '2025-01-01' AND '2025-12-31'
      GROUP BY 1""").fetchall()
    expected={r['canal']:r['total'] for r in rows}
actual={r['etiqueta']:r['valor'] for r in query_semantic(['canal'],'transacciones',{'desde':'2025-01-01','hasta':'2025-12-31'},500)['datos']}
check('Conteo por canal frente a SQL independiente sin joins de detalle',actual,expected)
check('Regiones maestras',len(regions_catalog()['regiones']),4)

for prompt,expected_horizon in [('Pronostica el próximo mes',1),('Proyecta seis meses',6),('Proyecta los próximos 6 meses',6)]:
    args=ai_chat._prediction_args([dict(role='user',content=prompt)])
    check(prompt,args['horizonte_meses'],expected_horizon)

# Reserve the final three calendar months; compare forecast with a naive baseline.
with connect() as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    rows=conn.execute("""WITH months AS (
      SELECT generate_series(date '2024-01-01',date '2025-12-01',interval '1 month') m)
      SELECT to_char(m,'YYYY-MM') mes,COALESCE(SUM(v.total_venta),0)::float total
      FROM months LEFT JOIN public.ventas v ON date_trunc('month',v.fecha_venta)=m
      AND v.estado_venta<>'Cancelada' GROUP BY m ORDER BY m""").fetchall()
values=[r['total'] for r in rows];train,observed=values[:-3],values[-3:]
predicted=[max(0,p[0]) for p in _linear(train,3)[0]]
mae=lambda a:sum(abs(x-y) for x,y in zip(a,observed))/len(observed)
backtest={'held_out':[r['mes'] for r in rows[-3:]],'actual':observed,'prediction':predicted,
          'mae_linear':mae(predicted),'mae_last_value':mae([train[-1]]*3),
          'note':'Sólo tres meses de validación; no prueba precisión general.'}
report={'checks':checks,'backtest':backtest}
out=Path('tmp/battery-qa');out.mkdir(parents=True,exist_ok=True)
(out/'local-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
