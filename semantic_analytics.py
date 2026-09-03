"""Capa semántica segura para análisis dinámico de ventas."""
from db import connect
from chat_evidence import validate_dates
from weekly_analysis import SALE_CRITERION, weekly_summary

DIMENSIONS={
 "dia":"to_char(v.fecha_venta::date,'YYYY-MM-DD')",
 "mes":"to_char(date_trunc('month',v.fecha_venta),'YYYY-MM')",
 "trimestre":"concat(extract(year from v.fecha_venta)::int,'-T',extract(quarter from v.fecha_venta)::int)",
 "anio":"extract(year from v.fecha_venta)::int::text",
 "dia_semana":"trim(to_char(v.fecha_venta,'Day'))",
 "genero":"cl.genero::text",
 "rango_edad":"CASE WHEN cl.edad IS NULL THEN 'No especificado' WHEN cl.edad<25 THEN '18-24' WHEN cl.edad<35 THEN '25-34' WHEN cl.edad<45 THEN '35-44' WHEN cl.edad<55 THEN '45-54' ELSE '55+' END",
 "tipo_cliente":"COALESCE(cl.tipo_cliente,'No especificado')",
 "frecuencia_compra":"COALESCE(cl.frecuencia_compra,'No especificado')",
 "segmento_cliente":"COALESCE(cl.segmento_cliente,'No especificado')",
 "canal_preferido":"COALESCE(cp.nombre_canal,'No especificado')",
 "cliente":"cl.nombre",
 "producto":"p.nombre_producto",
 "categoria":"cat.nombre_categoria",
 "proveedor":"prov.nombre",
 "sku":"vp.sku",
 "talla":"ta.etiqueta",
 "color_principal":"col.nombre",
 "personalizado":"CASE WHEN d.es_personalizado THEN 'Sí' ELSE 'No' END",
 "canal":"cv.nombre_canal",
 "estado_venta":"v.estado_venta::text",
 "promocion":"COALESCE(prom.nombre_promocion,'Sin promoción')",
 "administrador":"adm.nombre",
 "metodo_pago":"mp.nombre",
 "region":"COALESCE(rg.nombre_region,'Sin región')",
 "provincia":"COALESCE(pr.nombre,'Sin provincia')",
 "ciudad":"COALESCE(ci.nombre,'Sin ciudad')",
 "zona":"COALESCE(z.nombre,'Sin zona')",
 "tipo_entrega":"COALESCE(e.tipo_entrega::text,'Sin entrega')",
 "estado_entrega":"COALESCE(e.estado_entrega::text,'Sin entrega')"
}
MEASURES={
 "ingresos":"SUM(d.subtotal)::float",
 "utilidad":"SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float",
 "margen":"COALESCE(100.0*SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))/NULLIF(SUM(d.subtotal),0),0)::float",
 "unidades":"SUM(d.cantidad)::float",
 "transacciones":"COUNT(DISTINCT v.id_venta)::float",
 "clientes":"COUNT(DISTINCT v.id_cliente)::float",
 "ticket_promedio":"COALESCE(SUM(d.subtotal)/NULLIF(COUNT(DISTINCT v.id_venta),0),0)::float"
}
LABELS={"ingresos":"Ingresos","utilidad":"Utilidad","margen":"Margen (%)","unidades":"Unidades","transacciones":"Transacciones","clientes":"Clientes","ticket_promedio":"Ticket promedio"}
CURRENCY={"ingresos","utilidad","ticket_promedio"}
BASE="""FROM public.ventas v
JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante
JOIN public.productos p ON p.id_producto=vp.id_producto
JOIN public.categorias cat ON cat.id_categoria=p.id_categoria
JOIN public.proveedores prov ON prov.id_proveedor=p.id_proveedor
JOIN public.clientes cl ON cl.id_cliente=v.id_cliente
JOIN public.canales_venta cv ON cv.id_canal=v.id_canal
LEFT JOIN public.canales_venta cp ON cp.id_canal=cl.id_canal_preferido
JOIN public.tallas ta ON ta.id_talla=vp.id_talla
JOIN public.colores col ON col.id_color=vp.id_color_principal
JOIN public.administradores adm ON adm.id_admin=v.id_admin
JOIN public.metodo_pago mp ON mp.id_metodo_pago=v.id_metodo_pago
LEFT JOIN public.promociones prom ON prom.id_promocion=v.id_promocion
LEFT JOIN public.zona z ON z.id_zona=cl.id_zona
LEFT JOIN public.ciudad ci ON ci.id_ciudad=z.id_ciudad
LEFT JOIN public.provincia pr ON pr.id_provincia=ci.id_provincia
LEFT JOIN public.region rg ON rg.id_region=pr.id_region
LEFT JOIN LATERAL (SELECT tipo_entrega,estado_entrega FROM public.entregas ex WHERE ex.id_venta=v.id_venta ORDER BY ex.id_entrega DESC LIMIT 1) e ON true"""

def semantic_catalog():
 return {"modelo":"ventas","dimensiones":list(DIMENSIONS),"metricas":list(MEASURES),"limite_dimensiones":2}

def query_semantic(dimensions,measure,filters=None,limit=12):
 validate_dates(filters or {})
 dimensions=list(dict.fromkeys(dimensions or []))
 if not 1<=len(dimensions)<=2: raise ValueError("Se requieren una o dos dimensiones")
 if any(item not in DIMENSIONS for item in dimensions): raise ValueError("Dimensión no permitida")
 if measure not in MEASURES: raise ValueError("Métrica no permitida")
 filters=filters or {}; clauses=["v.estado_venta <> 'Cancelada'"]; values=[]
 mapping={"desde":("v.fecha_venta::date",">="),"hasta":("v.fecha_venta::date","<="),"region":("rg.nombre_region","="),"provincia":("pr.nombre","="),"canal":("cv.nombre_canal","="),"personalizado":("d.es_personalizado","=")}
 for key,(column,operator) in mapping.items():
  value=filters.get(key)
  if value and str(value).strip().casefold() not in ("todo","todos","toda","todas","all"):
   clauses.append(f"{column} {operator} %s"); values.append(value if key!="personalizado" else str(value).strip().casefold() in ("si","sí","true","1","personalizado"))
 expressions=[DIMENSIONS[item] for item in dimensions]; select=[f"{expr} etiqueta" if i==0 else f"{expr} serie" for i,expr in enumerate(expressions)]
 chronological=dimensions[0] in ("dia","mes","trimestre","anio","dia_semana")
 order="1"+(",2" if len(dimensions)==2 else "") if chronological else "valor DESC"
 sql=f"""SELECT {','.join(select)},{MEASURES[measure]} valor {BASE}
 WHERE {' AND '.join(clauses)} GROUP BY {','.join(str(i+1) for i in range(len(dimensions)))}
 ORDER BY {order} LIMIT %s"""
 weekly="dia_semana" in dimensions and measure=="transacciones"
 with connect() as conn:
  if weekly:
   rows=[dict(row) for row in conn.execute(sql.rsplit(" LIMIT %s",1)[0],values).fetchall()]
   bounds=conn.execute(f"SELECT MIN(v.fecha_venta::date) desde, MAX(v.fecha_venta::date) hasta {BASE} WHERE {' AND '.join(clauses)}",values).fetchone()
  else:
   rows=[dict(row) for row in conn.execute(sql,values+[max(2,min(int(limit or 12),500))]).fetchall()]
 for row in rows: row["valor"]=round(float(row["valor"] or 0),2)
 result={"fuente":"PostgreSQL RopaV","modelo":"ventas","dimensiones":dimensions,"metrica":measure,"etiqueta_metrica":LABELS[measure],"formato":"currency" if measure in CURRENCY else "percent" if measure=="margen" else "number","filtros":filters,"datos":rows,"criterio_ventas":SALE_CRITERION}
 if weekly:
  start=filters.get("desde") or bounds["desde"]
  end=filters.get("hasta") or bounds["hasta"]
  if start and end: result["estacionalidad_semanal"]=weekly_summary(rows,dimensions,start,end)
 return result
DISPLAY={"dia":"día","mes":"mes","trimestre":"trimestre","anio":"año","dia_semana":"día de la semana","genero":"género","rango_edad":"rango de edad","tipo_cliente":"tipo de cliente","frecuencia_compra":"frecuencia de compra","segmento_cliente":"segmento de cliente","canal_preferido":"canal preferido","cliente":"cliente","producto":"producto","categoria":"categoría","proveedor":"proveedor","sku":"SKU","talla":"talla","color_principal":"color","personalizado":"personalización","canal":"canal","estado_venta":"estado de venta","promocion":"promoción","administrador":"administrador","metodo_pago":"método de pago","region":"región","provincia":"provincia","ciudad":"ciudad","zona":"zona","tipo_entrega":"tipo de entrega","estado_entrega":"estado de entrega"}
PALETTE=["#11a99a","#ff9f68","#56c5d0","#8576d4","#e57b9b","#f2c14e","#4f86c6","#72b01d"]

def chart_contract(item,filters,result=None):
 dimensions=item.get("dimensions") or ([item["dimension"]] if item.get("dimension") else [])
 metric=item.get("metric","ingresos"); requested_limit=500 if item.get('top_per_group') or dimensions[0] in ("dia","mes","trimestre","anio") else item.get("limit",12); result=result or query_semantic(dimensions,metric,filters,requested_limit); rows=result["datos"]
 item=dict(item)
 if item.get('top_per_group') and len(dimensions)==2:
  if len(rows)>=500:raise ValueError('El ranking supera la capacidad de detalle. Filtra el periodo o grupo para no mostrar un ranking incompleto.')
  top=max(1,min(int(item['top_per_group']),20));selected=[]
  for group in sorted({str(r['etiqueta']) for r in rows}):
   selected.extend(sorted((r for r in rows if str(r['etiqueta'])==group),key=lambda r:(-r['valor'],str(r['serie'])))[:top])
  return {'type':'bar','orientation':'horizontal','title':f'Top {top} de {DISPLAY[dimensions[1]]} por {DISPLAY[dimensions[0]]}','description':f'Ranking independiente por {DISPLAY[dimensions[0]]}, ordenado por {LABELS[metric].lower()}. Se muestran hasta {top} por grupo.','labels':[str(r['etiqueta'])+' · '+str(r['serie']) for r in selected],'datasets':[{'label':LABELS[metric],'values':[r['valor'] for r in selected],'color':PALETTE[0]}],'colors':PALETTE,'value_format':result['formato'],'source':'PostgreSQL RopaV','filters':dict(filters or {}),'ranking':{'top_per_group':top,'rows':selected},'semantic':{'modelo':'ventas','dimensiones':dimensions,'metrica':metric}}
 if metric in ("margen","ticket_promedio","clientes") and item.get("type") in ("pie","doughnut"):
  item["type"]="bar"
  item["orientation"]="horizontal"
 labels=list(dict.fromkeys(str(row["etiqueta"]) for row in rows))
 if dimensions[0]=="mes":
  title="Evolución mensual de "+LABELS[metric].lower()
  if len(dimensions)>1: title+=" por "+DISPLAY[dimensions[1]]
 else: title=LABELS[metric]+" por "+" y ".join(DISPLAY[d] for d in dimensions)
 if len(dimensions)==1:
  datasets=[{"label":result["etiqueta_metrica"],"values":[row["valor"] for row in rows],"color":PALETTE[0]}]
  if rows:
   leader=max(rows,key=lambda row:row["valor"]); total=sum(float(row["valor"]) for row in rows)
   leaders=[str(row["etiqueta"]) for row in rows if row["valor"]==leader["valor"]]
   description=" y ".join(leaders)+(" empatan en el primer puesto con " if len(leaders)>1 else " lidera con ")+format(leader["valor"],",.2f")
   if len(leaders)>1: description+=" cada uno"
   description+=(" %." if metric=="margen" else ((", "+format(leader["valor"]/total*100,".1f")+"% de lo mostrado"+(" cada uno." if len(leaders)>1 else ".")) if total and metric not in ("ticket_promedio","clientes") else "."))
  else: description="No se encontraron datos para los filtros solicitados."
 else:
  series=list(dict.fromkeys(str(row["serie"]) for row in rows)); lookup={(str(row["etiqueta"]),str(row["serie"])):row["valor"] for row in rows}
  datasets=[{"label":serie,"values":[lookup.get((label,serie),0) for label in labels],"color":PALETTE[i%len(PALETTE)]} for i,serie in enumerate(series)]
  description="Comparación de "+result["etiqueta_metrica"].lower()+" por "+DISPLAY[dimensions[0]]+" y "+DISPLAY[dimensions[1]]+"."
 return {"type":item.get("type","bar"),"orientation":item.get("orientation","vertical"),"title":title,"description":description,"labels":labels,"datasets":datasets,"colors":PALETTE[:max(len(labels),len(datasets))],"value_format":result["formato"],"source":"PostgreSQL RopaV","filters":dict(filters or {}),"semantic":{"modelo":"ventas","dimensiones":dimensions,"metrica":metric}}
