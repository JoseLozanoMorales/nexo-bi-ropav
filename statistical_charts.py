"""Consultas y contratos deterministas para visualizaciones estadísticas avanzadas."""
from __future__ import annotations
import math
from collections import defaultdict
from db import connect

PALETTE=["#11a99a","#ff9f68","#56c5d0","#8576d4","#e57b9b","#f2c14e","#4f86c6","#72b01d","#d95d39","#6c5b7b"]
GEO_JOINS="""JOIN public.clientes cl ON cl.id_cliente=v.id_cliente
LEFT JOIN public.zona z ON z.id_zona=cl.id_zona
LEFT JOIN public.ciudad ci ON ci.id_ciudad=z.id_ciudad
LEFT JOIN public.provincia pr ON pr.id_provincia=ci.id_provincia
LEFT JOIN public.region rg ON rg.id_region=pr.id_region"""

def _where(filters,alias="v"):
 clauses=[f"{alias}.estado_venta<>'Cancelada'"]; values=[]
 mapping={"desde":(f"{alias}.fecha_venta::date",">="),"hasta":(f"{alias}.fecha_venta::date","<="),"region":("rg.nombre_region","="),"provincia":("pr.nombre","="),"canal":("cv.nombre_canal","=")}
 for key,(column,operator) in mapping.items():
  value=(filters or {}).get(key)
  if value and str(value).strip().casefold() not in ("todo","todos","toda","todas","all"):
   clauses.append(f"{column}{operator}%s"); values.append(value)
 return " AND ".join(clauses),values

def _quantile(values,probability):
 if not values:return 0
 position=(len(values)-1)*probability; low=math.floor(position); high=math.ceil(position)
 if low==high:return float(values[low])
 return float(values[low]+(values[high]-values[low])*(position-low))

def boxplot_sales(filters,group="canal"):
 groups={"canal":"cv.nombre_canal","provincia":"COALESCE(pr.nombre,'Sin provincia')","region":"COALESCE(rg.nombre_region,'Sin región')"}
 if group not in groups:raise ValueError("El boxplot sólo admite canal, provincia o región")
 where,values=_where(filters)
 with connect() as conn:
  rows=conn.execute(f"""SELECT {groups[group]} etiqueta,v.total_venta::float valor FROM public.ventas v
   JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} WHERE {where} ORDER BY 1,2""",values).fetchall()
 buckets=defaultdict(list)
 for row in rows:buckets[str(row["etiqueta"])].append(float(row["valor"]))
 boxes=[]
 for label,items in buckets.items():
  q1,median,q3=_quantile(items,.25),_quantile(items,.5),_quantile(items,.75);iqr=q3-q1;lower_bound,upper_bound=q1-1.5*iqr,q3+1.5*iqr
  normal=[value for value in items if lower_bound<=value<=upper_bound]
  boxes.append({"label":label,"min":round(min(normal),2),"q1":round(q1,2),"median":round(median,2),"q3":round(q3,2),"max":round(max(normal),2),"outliers":[round(value,2) for value in items if value<lower_bound or value>upper_bound],"count":len(items)})
 return {"type":"boxplot","orientation":"vertical","title":f"Distribución del importe por {group}","description":"Caja = rango intercuartílico; línea = mediana; bigotes = valores dentro de 1.5×IQR; puntos = atípicos.","labels":[item["label"] for item in boxes],"boxes":boxes,"datasets":[],"colors":PALETTE[:len(boxes)],"value_format":"moneda","source":"PostgreSQL RopaV","filters":filters}

def stacked_sales(filters,period="trimestre",group="categoria",segment="canal",metric="unidades"):
 periods={"mes":("to_char(date_trunc('month',v.fecha_venta),'YYYY-MM')","mes"),"trimestre":("concat(extract(year from v.fecha_venta)::int,'-T',extract(quarter from v.fecha_venta)::int)","trimestre")}
 groups={"categoria":("cat.nombre_categoria",True),"producto":("p.nombre_producto",True),"provincia":("COALESCE(pr.nombre,'Sin provincia')",False),"region":("COALESCE(rg.nombre_region,'Sin región')",False),"total":("'Total'",False)}
 segments={"canal":"cv.nombre_canal","region":"COALESCE(rg.nombre_region,'Sin región')","provincia":"COALESCE(pr.nombre,'Sin provincia')"}
 metrics={"unidades":("SUM(d.cantidad)::float","numero","Unidades"),"ingresos":("SUM(d.subtotal)::float","moneda","Ingresos"),"utilidad":("SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float","moneda","Utilidad")}
 if period not in periods or group not in groups or segment not in segments or metric not in metrics: raise ValueError("Configuración de barras apiladas no válida")
 period_sql,period_label=periods[period]; group_sql,needs_product=groups[group]; segment_sql=segments[segment]; metric_sql,value_format,metric_label=metrics[metric]
 where,values=_where(filters); product_joins=" JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto"; category_join=" JOIN public.categorias cat ON cat.id_categoria=p.id_categoria" if group=="categoria" else ""
 if not needs_product and metric!="utilidad": product_joins=""
 if metric=="utilidad" and not product_joins: product_joins=" JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto"
 with connect() as conn:
  rows=conn.execute(f"""SELECT {period_sql} periodo,{group_sql} grupo,{segment_sql} segmento,{metric_sql} valor FROM public.ventas v
   JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
   {product_joins}{category_join} WHERE {where} GROUP BY 1,2,3 ORDER BY 1,2,3""",values).fetchall()
 labels=list(dict.fromkeys(str(row["periodo"]) for row in rows)); group_labels=list(dict.fromkeys(str(row["grupo"]) for row in rows)); segment_labels=list(dict.fromkeys(str(row["segmento"]) for row in rows)); lookup={(str(row["periodo"]),str(row["grupo"]),str(row["segmento"])):float(row["valor"]) for row in rows}
 stacks=[{"label":group_label,"datasets":[{"label":segment_label,"values":[lookup.get((label,group_label,segment_label),0) for label in labels],"color":PALETTE[index%len(PALETTE)]} for index,segment_label in enumerate(segment_labels)]} for group_label in group_labels]
 title=f"{metric_label} por {period_label}, {group} y {segment}" if group!="total" else f"{metric_label} por {period_label}, segmentados por {segment}"
 return {"type":"stacked_bar","orientation":"vertical","title":title,"description":f"Cada periodo muestra {group if group!='total' else 'el total'}; los segmentos representan {segment}.","labels":labels,"stacks":stacks,"datasets":[],"colors":PALETTE[:len(segment_labels)],"value_format":value_format,"source":"PostgreSQL RopaV","filters":filters,"configuration":{"periodo":period,"grupo":group,"segmento":segment,"metrica":metric}}

def stacked_quarter_category_channel(filters):
 return stacked_sales(filters,"trimestre","categoria","canal","unidades")
def heatmap_month_province(filters,metric="unidades"):
 metrics={"unidades":("SUM(d.cantidad)::float","Unidades vendidas","numero"),"ingresos":("SUM(d.subtotal)::float","Ingresos","moneda"),"utilidad":("SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float","Utilidad","moneda")}
 if metric not in metrics: raise ValueError("El mapa de calor admite unidades, ingresos o utilidad")
 metric_sql,metric_label,value_format=metrics[metric]; where,values=_where(filters)
 with connect() as conn:
  rows=conn.execute(f"""SELECT to_char(date_trunc('month',v.fecha_venta),'YYYY-MM') mes,COALESCE(pr.nombre,'Sin provincia') provincia,{metric_sql} valor
   FROM public.ventas v JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
   JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto
   WHERE {where} GROUP BY 1,2 ORDER BY 1,2""",values).fetchall()
 x_labels=list(dict.fromkeys(str(row["mes"]) for row in rows));y_labels=list(dict.fromkeys(str(row["provincia"]) for row in rows));lookup={(str(row["mes"]),str(row["provincia"])):float(row["valor"]) for row in rows};matrix=[[lookup.get((month,province),0) for month in x_labels] for province in y_labels]
 return {"type":"heatmap","orientation":"vertical","title":f"{metric_label} por mes y provincia","description":f"Una mayor intensidad de color representa más {metric_label.lower()}.","labels":x_labels,"x_labels":x_labels,"y_labels":y_labels,"matrix":matrix,"datasets":[],"colors":["#e8f7f5","#11a99a"],"value_format":value_format,"source":"PostgreSQL RopaV","filters":filters,"metric":metric}

def product_scatter(filters,limit=50):
 where,values=_where(filters)
 with connect() as conn:
  rows=conn.execute(f"""SELECT p.nombre_producto etiqueta,SUM(d.cantidad)::float unidades,SUM(d.subtotal)::float ingresos,
   SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float utilidad FROM public.ventas v
   JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
   JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto
   WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT %s""",[*values,max(2,min(int(limit),100))]).fetchall()
 points=[{"label":str(row["etiqueta"]),"x":float(row["unidades"]),"y":float(row["ingresos"]),"utilidad":float(row["utilidad"]),"margen":round(float(row["utilidad"])/float(row["ingresos"])*100,2) if row["ingresos"] else 0} for row in rows]
 return {"type":"scatter","orientation":"vertical","title":"Unidades e ingresos por producto","description":"Cada punto es un producto: eje X = unidades vendidas; eje Y = ingresos.","labels":[p["label"] for p in points],"points":points,"datasets":[{"label":"Productos","color":PALETTE[0]}],"colors":PALETTE,"x_label":"Unidades","y_label":"Ingresos (USD)","value_format":"moneda","source":"PostgreSQL RopaV","filters":filters}
def pareto_products(filters,limit=20):
 where,values=_where(filters)
 with connect() as conn:
  rows=conn.execute(f"""SELECT p.nombre_producto etiqueta,SUM(d.subtotal)::float valor FROM public.ventas v
   JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
   JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto
   WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT %s""",[*values,max(2,min(int(limit),100))]).fetchall()
 labels=[str(row["etiqueta"]) for row in rows];amounts=[float(row["valor"]) for row in rows];total=sum(amounts);running=0;cumulative=[]
 for amount in amounts:running+=amount;cumulative.append(round(running/total*100,2) if total else 0)
 return {"type":"pareto","orientation":"vertical","title":"Pareto de productos por ingresos","description":"Barras: ingresos por producto. Línea: porcentaje acumulado sobre los productos mostrados.","labels":labels,"datasets":[{"label":"Ingresos","values":amounts,"color":PALETTE[0],"axis":"left"},{"label":"% acumulado","values":cumulative,"color":PALETTE[1],"axis":"right"}],"colors":PALETTE[:2],"value_format":"moneda","source":"PostgreSQL RopaV","filters":filters}

def monthly_income_profit(filters,include_margin=False):
 where,values=_where(filters)
 with connect() as conn:
  rows=conn.execute(f"""SELECT to_char(date_trunc('month',v.fecha_venta),'YYYY-MM') etiqueta,SUM(d.subtotal)::float ingresos,
   SUM(d.cantidad*(d.precio_unitario-COALESCE(vp.precio_compra_override,p.precio_compra)))::float utilidad FROM public.ventas v
   JOIN public.canales_venta cv ON cv.id_canal=v.id_canal {GEO_JOINS} JOIN public.detalle_ventas d ON d.id_venta=v.id_venta
   JOIN public.variantes_producto vp ON vp.id_variante=d.id_variante JOIN public.productos p ON p.id_producto=vp.id_producto
   WHERE {where} GROUP BY 1 ORDER BY 1""",values).fetchall()
 labels=[str(row["etiqueta"]) for row in rows];incomes=[float(row["ingresos"]) for row in rows];profits=[float(row["utilidad"]) for row in rows];datasets=[{"label":"Ingresos","values":incomes,"color":PALETTE[0],"axis":"left"},{"label":"Utilidad","values":profits,"color":PALETTE[1],"axis":"left"}]
 if include_margin:datasets.append({"label":"Margen (%)","values":[round(profit/income*100,2) if income else 0 for income,profit in zip(incomes,profits)],"color":PALETTE[3],"axis":"right"})
 return {"type":"line","orientation":"vertical","title":"Evolución mensual de ingresos, utilidad"+(" y margen" if include_margin else ""),"description":"Series mensuales; el margen utiliza el eje porcentual derecho." if include_margin else "Comparación mensual de ingresos y utilidad.","labels":labels,"datasets":datasets,"colors":PALETTE[:len(datasets)],"value_format":"moneda","secondary_axis":include_margin,"source":"PostgreSQL RopaV","filters":filters}
