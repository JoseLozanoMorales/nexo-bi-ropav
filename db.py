"""Acceso PostgreSQL compartido por la aplicacion y, posteriormente, MCP."""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:prototipo_local@127.0.0.1:5433/RopaV")
ROOT = Path(__file__).parent
DW_SOURCE = ROOT / "PROGRAMA EMPRESARIAL" / "PROGRAMA EMPRESARIAL"

def connect(): return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    with connect() as conn:
        conn.execute("SELECT 1 FROM public.ventas LIMIT 1")
        exists = conn.execute("SELECT to_regclass('dw.fact_ventas') IS NOT NULL AS ok").fetchone()["ok"]
        if not exists:
            conn.execute((DW_SOURCE / "01_ddl_dw_ropavacana.sql").read_text(encoding="utf-8"))
            conn.execute((DW_SOURCE / "02_etl_dw_ropavacana.sql").read_text(encoding="utf-8"))

def sync_dw(conn):
    """Sincroniza ventas nuevas y cambios de estado con el modelo de Power BI."""
    new_dates = conn.execute("""INSERT INTO dw.dim_tiempo
        (fk_tiempo,fecha,anio,mes,nombre_mes,trimestre,dia,dia_semana,nombre_dia,semana_anio,es_fin_semana)
        SELECT DISTINCT to_char(v.fecha_venta::date,'YYYYMMDD')::int,v.fecha_venta::date,
        extract(year from v.fecha_venta)::smallint,extract(month from v.fecha_venta)::smallint,
        trim(to_char(v.fecha_venta,'TMMonth')),extract(quarter from v.fecha_venta)::smallint,
        extract(day from v.fecha_venta)::smallint,extract(dow from v.fecha_venta)::smallint,
        trim(to_char(v.fecha_venta,'TMDay')),extract(week from v.fecha_venta)::smallint,
        extract(dow from v.fecha_venta) in (0,6) FROM public.ventas v
        ON CONFLICT (fk_tiempo) DO NOTHING""").rowcount
    new_facts = conn.execute("""INSERT INTO dw.fact_ventas
        (id_detalle,id_venta,fk_tiempo,fk_cliente,fk_variante,fk_canal,fk_metodo_pago,
        fk_promocion,fk_admin,estado_venta,cantidad,precio_unitario,subtotal,costo_unitario,
        costo_total,margen_total,es_personalizado)
        SELECT dv.id_detalle,dv.id_venta,to_char(v.fecha_venta,'YYYYMMDD')::int,v.id_cliente,
        dv.id_variante,v.id_canal,v.id_metodo_pago,coalesce(v.id_promocion,-1),v.id_admin,
        v.estado_venta::text,dv.cantidad,dv.precio_unitario,dv.subtotal,
        coalesce(vp.precio_compra_override,p.precio_compra),
        coalesce(vp.precio_compra_override,p.precio_compra)*dv.cantidad,
        dv.subtotal-coalesce(vp.precio_compra_override,p.precio_compra)*dv.cantidad,dv.es_personalizado
        FROM public.detalle_ventas dv JOIN public.ventas v USING(id_venta)
        JOIN public.variantes_producto vp USING(id_variante)
        JOIN public.productos p USING(id_producto)
        ON CONFLICT (id_detalle) DO NOTHING""").rowcount
    states = conn.execute("""UPDATE dw.fact_ventas f SET estado_venta=v.estado_venta::text
        FROM public.ventas v WHERE v.id_venta=f.id_venta AND f.estado_venta<>v.estado_venta::text""").rowcount
    return {"nuevas_fechas":new_dates,"nuevos_hechos":new_facts,"estados_actualizados":states}

def dw_status():
    with connect() as conn:
        row = conn.execute("""SELECT COUNT(*)::int hechos,COUNT(DISTINCT id_venta)::int ventas,
            COALESCE(MAX(dt.fecha)::text,'Sin datos') ultima_fecha
            FROM dw.fact_ventas f JOIN dw.dim_tiempo dt ON dt.fk_tiempo=f.fk_tiempo""").fetchone()
        return dict(row)

def sync_powerbi():
    with connect() as conn:
        return sync_dw(conn)

def _filters(params):
    clauses, values = [], []
    mapping = {"desde":("v.fecha_venta::date",">="), "hasta":("v.fecha_venta::date","<="), "region":("COALESCE(rg.nombre_region,'Sin región')","="), "provincia":("COALESCE(pr.nombre,'Sin provincia')","="), "canal":("cv.nombre_canal","=")}
    for key,(column,operator) in mapping.items():
        value=params.get(key)
        if value and str(value).strip().casefold() not in ("todo","todos","toda","todas","all"): clauses.append(f"{column} {operator} %s"); values.append(value)
    return (" AND "+" AND ".join(clauses) if clauses else ""),values

BASE_JOINS="""JOIN public.clientes cl ON cl.id_cliente=v.id_cliente
JOIN public.canales_venta cv ON cv.id_canal=v.id_canal
LEFT JOIN public.zona z ON z.id_zona=cl.id_zona
LEFT JOIN public.ciudad ci ON ci.id_ciudad=z.id_ciudad
LEFT JOIN public.provincia pr ON pr.id_provincia=ci.id_provincia
LEFT JOIN public.region rg ON rg.id_region=pr.id_region"""

def _rows(conn,sql,values=()): return [dict(r) for r in conn.execute(sql,values).fetchall()]

def dashboard(params=None):
    params=params or {}; result_limit=max(1,min(int(params.get("limite",12)),20)); extra,values=_filters(params); order_by={"ingresos":"ingresos","unidades":"unidades","utilidad":"utilidad"}.get(params.get("orden"),"ingresos"); sale_where="WHERE v.estado_venta <> 'Cancelada'"+extra
    with connect() as conn:
        kpi=dict(conn.execute(f"""SELECT COUNT(DISTINCT v.id_venta) transacciones,COALESCE(SUM(d.cantidad),0)::int unidades,
        COALESCE(SUM(d.subtotal),0)::float ingresos,COALESCE(SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra))),0)::float utilidad,
        COUNT(DISTINCT v.id_cliente) clientes FROM public.ventas v {BASE_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
        JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto {sale_where}""",values).fetchone())
        kpi["margen"]=round(kpi["utilidad"]/kpi["ingresos"]*100,2) if kpi["ingresos"] else 0
        tendencia=_rows(conn,f"""SELECT to_char(date_trunc('month',v.fecha_venta),'YYYY-MM') etiqueta,SUM(d.subtotal)::float ingresos,
        SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float utilidad FROM public.ventas v {BASE_JOINS}
        JOIN public.detalle_ventas d ON d.id_venta=v.id_venta JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante
        JOIN public.productos p ON p.id_producto=vp.id_producto {sale_where} GROUP BY 1 ORDER BY 1""",values)
        def sales_group(label,joins="",limit=12):
            return _rows(conn,f"""SELECT {label} etiqueta,SUM(d.subtotal)::float ingresos,
            SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float utilidad,SUM(d.cantidad)::int unidades
            FROM public.ventas v {BASE_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
            JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto
            {joins} {sale_where} GROUP BY 1 ORDER BY {order_by} DESC LIMIT {limit}""",values)
        producto=sales_group("p.nombre_producto",limit=10)
        categoria=sales_group("c.nombre_categoria","JOIN public.categorias c ON c.id_categoria=p.id_categoria")
        region=sales_group("COALESCE(rg.nombre_region,'Sin región')")
        provincia=sales_group("COALESCE(pr.nombre,'Sin provincia')")
        canal=sales_group("cv.nombre_canal")
        cliente=sales_group("COALESCE(cl.segmento_cliente,'Sin segmento')")
        cliente_individual=sales_group("cl.nombre",limit=result_limit)
        inventario=_rows(conn,"""SELECT p.nombre_producto||' · '||vp.sku etiqueta,i.cantidad_disponible::float ingresos,
        i.cantidad_minima::float utilidad,CASE WHEN i.cantidad_disponible<=i.cantidad_minima THEN 1 ELSE 0 END alerta
        FROM public.inventario i JOIN public.variantes_producto vp USING(id_variante) JOIN public.productos p USING(id_producto)
        ORDER BY alerta DESC,i.cantidad_disponible ASC LIMIT 12""")
        entrega=_rows(conn,f"""SELECT e.estado_entrega::text etiqueta,COUNT(*)::float ingresos,
        COUNT(*) FILTER(WHERE e.estado_entrega='Entregado')::float utilidad,COUNT(*)::int unidades
        FROM public.entregas e JOIN public.ventas v ON v.id_venta=e.id_venta {BASE_JOINS} {sale_where} GROUP BY 1 ORDER BY ingresos DESC""",values)
        recientes=_rows(conn,f"""SELECT v.id_venta id,to_char(v.fecha_venta,'YYYY-MM-DD') fecha,string_agg(DISTINCT p.nombre_producto,', ') producto,
        COALESCE(rg.nombre_region,'Sin región') region,COALESCE(pr.nombre,'Sin provincia') provincia,cv.nombre_canal canal,cl.nombre vendedor,SUM(d.cantidad)::int cantidad,v.total_venta::float total,v.estado_venta::text estado
        FROM public.ventas v {BASE_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante
        JOIN public.productos p ON p.id_producto=vp.id_producto {sale_where} GROUP BY v.id_venta,v.fecha_venta,rg.nombre_region,pr.nombre,cv.nombre_canal,cl.nombre,v.total_venta,v.estado_venta
        ORDER BY v.id_venta DESC LIMIT 12""",values)
    return {"kpi":kpi,"tendencia":tendencia,"producto":producto,"categoria":categoria,"region":region,"provincia":provincia,"canal":canal,"cliente":cliente,"cliente_individual":cliente_individual,"inventario":inventario,"entrega":entrega,"recientes":recientes}


ALLOWED_SCHEMAS=("public","dw")
def database_schema(action="listar_tablas", schema=None, table=None):
    """Metadatos de solo lectura para que el MCP explique la estructura de RopaV."""
    if schema and schema not in ALLOWED_SCHEMAS: raise ValueError("Esquema no permitido")
    schemas=[schema] if schema else list(ALLOWED_SCHEMAS)
    with connect() as conn:
        if action=="listar_tablas":
            return {"accion":action,"esquemas":schemas,"tablas":_rows(conn, """SELECT table_schema esquema,table_name tabla,
                CASE table_type WHEN 'BASE TABLE' THEN 'tabla' ELSE lower(table_type) END tipo
                FROM information_schema.tables WHERE table_schema=ANY(%s)
                ORDER BY table_schema,table_name""",(schemas,))}
        if action=="describir_tabla":
            if not schema or not table: raise ValueError("Se requieren esquema y tabla")
            exists=conn.execute("""SELECT EXISTS(SELECT 1 FROM information_schema.tables
                WHERE table_schema=%s AND table_name=%s) ok""",(schema,table)).fetchone()["ok"]
            if not exists: raise ValueError("La tabla indicada no existe en los esquemas permitidos")
            columns=_rows(conn,"""SELECT column_name columna,data_type tipo,is_nullable='YES' permite_nulos,
                column_default valor_predeterminado FROM information_schema.columns
                WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",(schema,table))
            return {"accion":action,"esquema":schema,"tabla":table,"columnas":columns}
        if action=="listar_relaciones":
            return {"accion":action,"esquemas":schemas,"relaciones":_rows(conn, """SELECT
                tc.table_schema esquema,tc.table_name tabla,kcu.column_name columna,
                ccu.table_schema esquema_referenciado,ccu.table_name tabla_referenciada,
                ccu.column_name columna_referenciada,tc.constraint_name restriccion
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
                WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema=ANY(%s)
                ORDER BY tc.table_schema,tc.table_name,kcu.column_name""",(schemas,))}
        raise ValueError("Accion de esquema no valida")

def sales_histogram(desde=None,hasta=None,intervalos=10):
    """Distribución real del importe total por venta no cancelada."""
    intervalos=max(2,min(int(intervalos or 10),30))
    clauses=["estado_venta<>'Cancelada'"]; values=[]
    if desde: clauses.append("fecha_venta::date >= %s"); values.append(desde)
    if hasta: clauses.append("fecha_venta::date <= %s"); values.append(hasta)
    with connect() as conn:
        amounts=[float(r["importe"]) for r in conn.execute(
            "SELECT total_venta::float importe FROM public.ventas WHERE "+" AND ".join(clauses)+" ORDER BY total_venta",values).fetchall()]
    if not amounts:
        return {"fuente":"PostgreSQL RopaV","dimension":"histograma_ventas","filtros":{"desde":desde,"hasta":hasta,"intervalos":intervalos},"estadisticas":{"ventas":0},"datos":[]}
    low,high=min(amounts),max(amounts); width=(high-low)/intervalos if high>low else 1
    counts=[0]*intervalos
    for amount in amounts:
        index=min(int((amount-low)/width),intervalos-1); counts[index]+=1
    rows=[]
    for i,count in enumerate(counts):
        left=low+i*width; right=high if i==intervalos-1 else low+(i+1)*width
        rows.append({"etiqueta":f"{left:.2f}–{right:.2f}","desde":round(left,2),"hasta":round(right,2),"frecuencia":count})
    mean=sum(amounts)/len(amounts)
    return {"fuente":"PostgreSQL RopaV","dimension":"histograma_ventas","filtros":{"desde":desde,"hasta":hasta,"intervalos":intervalos},
        "estadisticas":{"ventas":len(amounts),"minimo":round(low,2),"maximo":round(high,2),"promedio":round(mean,2)},"datos":rows}

def sales_periods():
    with connect() as conn:
        summary=dict(conn.execute("SELECT MIN(fecha_venta::date)::text desde,MAX(fecha_venta::date)::text hasta,COUNT(DISTINCT id_venta)::int transacciones FROM public.ventas WHERE estado_venta<>'Cancelada'").fetchone())
        months=_rows(conn,"SELECT to_char(date_trunc('month',fecha_venta),'YYYY-MM') mes,COUNT(*)::int transacciones FROM public.ventas WHERE estado_venta<>'Cancelada' GROUP BY 1 ORDER BY 1")
        return {'fuente':'PostgreSQL RopaV','rango':summary,'meses':months}

def catalog():
    with connect() as conn:
        return {"productos":_rows(conn,"""SELECT vp.id_variante id,p.nombre_producto||' · '||vp.sku nombre,COALESCE(vp.precio_venta_override,p.precio_venta)::float precio,i.cantidad_disponible stock
        FROM public.variantes_producto vp JOIN public.productos p USING(id_producto) JOIN public.inventario i USING(id_variante) WHERE vp.activo AND i.cantidad_disponible>0 ORDER BY 2"""),
        "clientes":_rows(conn,"SELECT id_cliente id,nombre FROM public.clientes ORDER BY nombre"),"canales":_rows(conn,"SELECT id_canal id,nombre_canal nombre FROM public.canales_venta ORDER BY nombre"),
        "administradores":_rows(conn,"SELECT id_admin id,nombre FROM public.administradores ORDER BY nombre"),"metodos":_rows(conn,"SELECT id_metodo_pago id,nombre FROM public.metodo_pago WHERE activo ORDER BY nombre"),
        "regiones":[r["nombre"] for r in _rows(conn,"SELECT nombre_region nombre FROM public.region ORDER BY id_region")],
        "provincias":[r["nombre"] for r in _rows(conn,"SELECT nombre FROM public.provincia ORDER BY nombre")]}

def add_sale(data):
    required=("fecha","id_variante","id_cliente","id_canal","id_admin","id_metodo_pago","cantidad","precio")
    missing=[k for k in required if data.get(k) in (None,"")]
    if missing: raise ValueError("Faltan campos: "+", ".join(missing))
    quantity,price=int(data["cantidad"]),float(data["precio"])
    if quantity<=0 or price<0: raise ValueError("Cantidad y precio deben ser validos")
    with connect() as conn:
        row=conn.execute("""INSERT INTO public.ventas(fecha_venta,total_venta,estado_venta,id_cliente,id_canal,id_admin,id_metodo_pago)
        VALUES(%s,0,'Completada',%s,%s,%s,%s) RETURNING id_venta""",(data.get("fecha",date.today().isoformat()),int(data["id_cliente"]),int(data["id_canal"]),int(data["id_admin"]),int(data["id_metodo_pago"]))).fetchone()
        sale_id=row["id_venta"]
        conn.execute("INSERT INTO public.detalle_ventas(id_venta,cantidad,precio_unitario,es_personalizado,id_variante) VALUES(%s,%s,%s,%s,%s)",(sale_id,quantity,price,bool(data.get("es_personalizado",False)),int(data["id_variante"])))
        sync_dw(conn)
        return int(sale_id)

def delete_sale(sale_id):
    with connect() as conn:
        cur=conn.execute("UPDATE public.ventas SET estado_venta='Cancelada' WHERE id_venta=%s AND estado_venta<>'Cancelada'",(sale_id,))
        if cur.rowcount: sync_dw(conn)
        return cur.rowcount>0
