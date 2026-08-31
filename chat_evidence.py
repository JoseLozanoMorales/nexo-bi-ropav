"""Small, testable guards between user requests and analytical evidence."""
import re
import unicodedata
from datetime import date
from api_errors import SafeRequestError


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))


def explicit_dates(text):
    text = plain(text)
    months = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1,13)))
    def iso(day, month, year):
        try:
            return date(int(year), months[month], int(day)).isoformat()
        except ValueError as exc:
            raise SafeRequestError('La fecha indicada no existe. Revisa el día, mes y año.') from exc
    names = '|'.join(months)
    short = re.search(rf'\b(?:del?\s+)?(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+de\s+({names})\s+de\s+(20\d{{2}})', text)
    if short:
        a,b,m,y = short.groups()
        result = {'desde':iso(a,m,y), 'hasta':iso(b,m,y)}
    else:
        hits = re.findall(rf'\b(\d{{1,2}})\s+de\s+({names})\s+de\s+(20\d{{2}})', text)
        dates = re.findall(r'\b20\d{2}-\d{2}-\d{2}\b', text) or [iso(*hit) for hit in hits]
        if not dates: return {}
        result = {'desde':dates[0], 'hasta':dates[-1]}
    validate_dates(result)
    return result


def validate_dates(filters):
    for key in ('desde','hasta'):
        if filters.get(key):
            try:
                date.fromisoformat(filters[key])
            except (ValueError, TypeError) as exc:
                raise SafeRequestError('La fecha indicada no es válida. Usa el formato AAAA-MM-DD.') from exc
    if filters.get('desde') and filters.get('hasta') and filters['desde'] > filters['hasta']:
        raise SafeRequestError('El rango está invertido: la fecha final debe ser igual o posterior a la inicial.')


def weekly_chart(result):
    summary = result['estacionalidad_semanal']
    groups = summary['grupos']
    return {'type':'bar','orientation':'vertical','title':'Transacciones por día calendario y canal',
            'labels':[g['grupo'] for g in groups], 'datasets':[
                {'label':label,'values':[g[key] for g in groups],'color':color}
                for label,key,color in [('Lunes–viernes','promedio_laborable','#11a99a'),('Sábado–domingo','promedio_fin_semana','#ff9f68')]],
            'colors':['#11a99a','#ff9f68'],'value_format':'number','source':result['fuente'],
            'description':summary['nota']}


def cancellation_counts(filters):
    from db import connect
    validate_dates(filters)
    clauses=[]; values=[]
    for key,column,op in [('desde','v.fecha_venta::date','>='),('hasta','v.fecha_venta::date','<='),('canal','cv.nombre_canal','='),('region','rg.nombre_region','='),('provincia','pr.nombre','=')]:
        if filters.get(key):
            clauses.append(f'{column} {op} %s'); values.append(filters[key])
    sql = """SELECT cv.nombre_canal canal, COUNT(*)::int todas,
        COUNT(*) FILTER (WHERE v.estado_venta='Cancelada')::int canceladas,
        COUNT(*) FILTER (WHERE v.estado_venta<>'Cancelada')::int no_canceladas,
        COUNT(*) FILTER (WHERE v.estado_venta IS NULL)::int sin_estado
        FROM public.ventas v
        LEFT JOIN public.canales_venta cv ON cv.id_canal=v.id_canal
        LEFT JOIN public.clientes cl ON cl.id_cliente=v.id_cliente
        LEFT JOIN public.zona z ON z.id_zona=cl.id_zona
        LEFT JOIN public.ciudad ci ON ci.id_ciudad=z.id_ciudad
        LEFT JOIN public.provincia pr ON pr.id_provincia=ci.id_provincia
        LEFT JOIN public.region rg ON rg.id_region=pr.id_region"""
    if clauses: sql += ' WHERE '+' AND '.join(clauses)
    with connect() as conn:
        rows=[dict(row) for row in conn.execute(sql+' GROUP BY 1 ORDER BY 1',values).fetchall()]
    keys=('todas','canceladas','no_canceladas','sin_estado')
    totals={key:sum(r[key] for r in rows) for key in keys}
    return {'fuente':'PostgreSQL RopaV · public.ventas','filtros':filters,'datos':rows,'totales':totals,
            'comprobacion':totals['todas']==sum(totals[k] for k in keys[1:]),
            'criterio_ventas':'Incluye todas las ventas. Canceladas y no canceladas se cuentan por separado; los estados nulos, si existen, se muestran como sin estado.'}
