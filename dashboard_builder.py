"""Construccion determinista de dashboards adaptados al prompt."""
import re
import unicodedata
from copy import deepcopy
from mcp_server import call_tool
from semantic_analytics import chart_contract
from objective_dashboards import detect_objective, build_objective_dashboard

PALETTE=["#11a99a","#ff9f68","#56c5d0","#8576d4","#e57b9b","#f2c14e","#4f86c6","#72b01d","#d95d39","#6c5b7b"]
MONTHS=["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

def _plain(text):
 return "".join(c for c in unicodedata.normalize("NFKD",str(text).lower()) if not unicodedata.combining(c))

def _query(dimension,filters):
 return call_tool("consultar_analitica",{"dimension":dimension,**filters})["structuredContent"]

def _description(title,rows,metric):
 if not rows: return "No se encontraron datos para los filtros solicitados."
 leader=rows[0]; total=sum(float(r.get(metric,0) or 0) for r in rows)
 share=(float(leader.get(metric,0) or 0)/total*100) if total else 0
 return f"{leader.get('etiqueta','El primer elemento')} lidera con {float(leader.get(metric,0) or 0):,.2f}, equivalente al {share:.1f}% de lo mostrado."

def _chart(kind,title,rows,metric,label,orientation="vertical",fmt="moneda",description=None,limit=10):
 rows=rows[:limit]
 return {"type":kind,"orientation":orientation,"title":title,"description":description or _description(title,rows,metric),"labels":[str(r.get("etiqueta","")) for r in rows],"datasets":[{"label":label,"values":[r.get(metric,0) for r in rows],"color":"#11a99a"}],"colors":PALETTE[:len(rows)],"value_format":fmt,"source":"PostgreSQL RopaV"}

def _kpis(k):
 return [{"label":"Ingresos","value":k["ingresos"],"format":"currency"},{"label":"Utilidad","value":k["utilidad"],"format":"currency"},{"label":"Margen","value":k["margen"],"format":"percent"},{"label":"Transacciones","value":k["transacciones"],"format":"number"},{"label":"Unidades","value":k["unidades"],"format":"number"},{"label":"Clientes","value":k["clientes"],"format":"number"}]

def _period(filters):
 if filters.get("desde") and filters.get("hasta"): return f"{filters['desde']} a {filters['hasta']}"
 return "todo el periodo disponible"

def _comparison(prompt):
 years=sorted(set(re.findall(r"\b(20\d{2})\b",prompt)))
 return years[:2] if len(years)>=2 and any(x in _plain(prompt) for x in ("compar", "contra", "versus", "vs")) else []

def _comparison_dashboard(years):
 results=[]
 for year in years:
  f={"desde":f"{year}-01-01","hasta":f"{year}-12-31"}
  results.append((year,f,_query("resumen",f),_query("tendencia",f)))
 current=results[-1][2]["indicadores"]; previous=results[0][2]["indicadores"]
 growth=((current["ingresos"]-previous["ingresos"])/previous["ingresos"]*100) if previous["ingresos"] else 0
 labels=[str(y) for y,_,_,_ in results]
 annual={"type":"bar","orientation":"vertical","title":"Ingresos anuales comparados","description":f"Los ingresos variaron {growth:+.1f}% entre {years[0]} y {years[1]}.","labels":labels,"datasets":[{"label":"Ingresos","values":[r[2]["indicadores"]["ingresos"] for r in results],"color":"#11a99a"},{"label":"Utilidad","values":[r[2]["indicadores"]["utilidad"] for r in results],"color":"#ff9f68"}],"colors":PALETTE[:2],"value_format":"moneda","source":"PostgreSQL RopaV"}
 monthly={"type":"line","orientation":"vertical","title":"Evolución mensual comparativa","description":"Compara la estacionalidad mensual de ingresos de ambos años.","labels":MONTHS,"datasets":[],"colors":PALETTE[:2],"value_format":"moneda","source":"PostgreSQL RopaV"}
 for idx,(year,_,_,trend) in enumerate(results):
  values={int(r["etiqueta"][-2:]):r["ingresos"] for r in trend["datos"]}
  monthly["datasets"].append({"label":str(year),"values":[values.get(m,0) for m in range(1,13)],"color":PALETTE[idx]})
 last_year,last_filters=results[-1][0],results[-1][1]
 products=_query("producto",last_filters); channels=_query("canal",last_filters)
 return {"title":f"Dashboard comparativo {years[0]} vs {years[1]}","subtitle":"Comparación interanual · Fuente: PostgreSQL RopaV","filters":{"desde":f"{years[0]}-01-01","hasta":f"{years[1]}-12-31"},"kpis":[{"label":f"Ingresos {years[0]}","value":previous["ingresos"],"format":"currency"},{"label":f"Ingresos {years[1]}","value":current["ingresos"],"format":"currency"},{"label":"Variación ingresos","value":growth,"format":"percent"},{"label":f"Utilidad {years[1]}","value":current["utilidad"],"format":"currency"},{"label":f"Transacciones {years[1]}","value":current["transacciones"],"format":"number"},{"label":f"Unidades {years[1]}","value":current["unidades"],"format":"number"}],"charts":[annual,monthly,_chart("bar",f"Productos líderes en {last_year}",products["datos"],"ingresos","Ingresos","horizontal"),_chart("doughnut",f"Canales en {last_year}",channels["datos"],"ingresos","Ingresos")]}

KPI_LABELS={"ingresos":"Ingresos","utilidad":"Utilidad","margen":"Margen","transacciones":"Transacciones","unidades":"Unidades","clientes":"Clientes","ticket_promedio":"Ticket promedio","unidades_por_venta":"Unidades por venta"}
KPI_FORMATS={"ingresos":"currency","utilidad":"currency","margen":"percent","transacciones":"number","unidades":"number","clientes":"number","ticket_promedio":"currency","unidades_por_venta":"number"}
VALID_DIMENSIONS={"tendencia","producto","categoria","region","canal","cliente","cliente_individual","inventario","entrega"}
VALID_METRICS={"ingresos","utilidad","unidades"}
VALID_TYPES={"bar","line","area","pie","doughnut","scatter"}

def _planned_dashboard(filters,plan):
 summary=_query("resumen",filters); values=dict(summary["indicadores"])
 values["ticket_promedio"]=values["ingresos"]/values["transacciones"] if values["transacciones"] else 0
 values["unidades_por_venta"]=values["unidades"]/values["transacciones"] if values["transacciones"] else 0
 requested=list(dict.fromkeys(plan.get("kpis") or []))[:6]
 if len(requested)<3: requested=["ingresos","transacciones","clientes"]
 kpis=[{"label":KPI_LABELS[key],"value":values.get(key,0),"format":KPI_FORMATS[key]} for key in requested if key in KPI_LABELS]
 charts=[chart_contract(item,filters) for item in (plan.get("charts") or [])[:6]]
 if not charts: raise ValueError("El plan no produjo gráficos compatibles con la capa semántica")
 title=re.split(r"\s*[—–]\s*(?:nota|criterio)\b",str(plan.get("title") or "Dashboard dinámico"),maxsplit=1,flags=re.I)[0].strip()
 geography=" · ".join(f"{key.capitalize()}: {filters[key]}" for key in ("region","provincia","canal") if filters.get(key))
 return {"title":title[:90],"subtitle":f"Periodo: {_period(filters)}"+(" · "+geography if geography else "")+" · Fuente: PostgreSQL RopaV","filters":filters,"kpis":kpis,"charts":charts,"plan":deepcopy(plan)}
def _fallback_plan(prompt):
 text=_plain(prompt); charts=[]
 mapping=[("gener",["genero"],"doughnut"),("categoria",["categoria"],"bar"),("producto",["producto"],"bar"),("canal",["canal"],"doughnut"),("region",["region"],"bar"),("provincia",["provincia"],"bar"),("client",["cliente"],"bar"),("segment",["segmento_cliente"],"doughnut"),("talla",["talla"],"bar"),("color",["color_principal"],"bar"),("pago",["metodo_pago"],"doughnut"),("promocion",["promocion"],"bar")]
 metric="margen" if "margen" in text else "utilidad" if "utilidad" in text else "unidades" if any(x in text for x in ("unidades","mas vendido")) else "ingresos"
 if any(x in text for x in ("mensual","evolucion","tendencia")): charts.append({"dimensions":["mes"],"metric":metric,"type":"line","orientation":"vertical","title":"","limit":100})
 for token,dimensions,kind in mapping:
  if token in text: charts.append({"dimensions":dimensions,"metric":metric,"type":kind,"orientation":"horizontal" if kind=="bar" else "vertical","title":"","limit":20})
 if not charts: charts=[{"dimensions":["mes"],"metric":"ingresos","type":"line","orientation":"vertical","title":"","limit":100},{"dimensions":["producto"],"metric":"ingresos","type":"bar","orientation":"horizontal","title":"","limit":10}]
 return {"title":"Dashboard dinámico","kpis":["ingresos","utilidad","margen","transacciones","unidades","clientes"],"charts":charts[:6]}
def _inventory_sales_dashboard(filters,prompt):
 summary=_query("resumen",filters); products=_query("producto",filters); categories=_query("categoria",filters); trend=_query("tendencia",filters); inventory=_query("inventario",{})
 sold_names={str(row.get("etiqueta","")) for row in products["datos"]}; stock_rows=[row for row in inventory["datos"] if str(row.get("etiqueta","")) in sold_names]
 if not stock_rows:stock_rows=inventory["datos"][:10]
 stock_chart={"type":"bar","orientation":"horizontal","title":"Stock actual de productos comercializados","description":"Stock global actual de los productos que aparecen en las ventas filtradas; la base no localiza inventario por región.","labels":[str(row.get("etiqueta","")) for row in stock_rows[:12]],"datasets":[{"label":"Stock disponible","values":[row.get("ingresos",0) for row in stock_rows[:12]],"color":PALETTE[0]},{"label":"Stock mínimo","values":[row.get("utilidad",0) for row in stock_rows[:12]],"color":PALETTE[1]}],"colors":PALETTE[:2],"value_format":"numero","source":"PostgreSQL RopaV"}
 charts=[_chart("line","Evolución mensual de ingresos",trend["datos"],"ingresos","Ingresos",limit=100),_chart("bar","Productos comercializados por ingresos",products["datos"],"ingresos","Ingresos","horizontal"),stock_chart,_chart("bar","Ventas por categoría",categories["datos"],"ingresos","Ingresos","horizontal")]
 k=summary["indicadores"]; kpis=_kpis(k)[:4]+[{"label":"Productos comercializados","value":len(sold_names),"format":"number"},{"label":"Stock disponible asociado","value":sum(float(row.get("ingresos",0) or 0) for row in stock_rows),"format":"number"}]
 return {"title":"Dashboard de inventario y ventas","subtitle":f"Periodo: {_period(filters)} · Ventas con filtro solicitado; inventario global actual · Fuente: PostgreSQL RopaV","filters":filters,"kpis":kpis,"charts":charts}
def build_dashboard(filters,title=None,prompt="",plan=None):
 if plan: return _planned_dashboard(filters,plan)
 objective_id=detect_objective(prompt)
 if objective_id: return build_objective_dashboard(objective_id,filters)
 text=_plain(prompt)
 if "inventario" in text and any(token in text for token in ("venta","producto","comercializ")): return _inventory_sales_dashboard(filters,prompt)
 years=_comparison(prompt)
 if years: return _comparison_dashboard(years)
 plan=plan or _fallback_plan(prompt)
 if plan: return _planned_dashboard(filters,plan)
 text=_plain(prompt); summary=_query("resumen",filters); trend=_query("tendencia",filters); k=summary["indicadores"]
 products=_query("producto",filters); channels=_query("canal",filters); clients=_query("cliente",filters)
 period=_period(filters)
 if "producto" in text:
  categories=_query("categoria",filters)
  charts=[_chart("bar","Productos por ingresos",products["datos"],"ingresos","Ingresos","horizontal"),_chart("bar","Productos por unidades",products["datos"],"unidades","Unidades","horizontal","numero"),_chart("doughnut","Participación por categoría",categories["datos"],"ingresos","Ingresos"),_chart("line","Evolución mensual",trend["datos"],"ingresos","Ingresos")]
  dash_title="Dashboard de rendimiento de productos"
 elif "canal" in text:
  charts=[_chart("doughnut","Participación de ingresos por canal",channels["datos"],"ingresos","Ingresos"),_chart("bar","Utilidad por canal",channels["datos"],"utilidad","Utilidad"),_chart("bar","Unidades por canal",channels["datos"],"unidades","Unidades","horizontal","numero"),_chart("line","Evolución mensual",trend["datos"],"ingresos","Ingresos")]
  dash_title="Dashboard de canales de venta"
 elif "client" in text or "segment" in text:
  individuals=_query("cliente_individual",filters)
  charts=[_chart("bar","Clientes con mayores compras",individuals["datos"],"ingresos","Ingresos","horizontal"),_chart("doughnut","Ingresos por segmento",clients["datos"],"ingresos","Ingresos"),_chart("bar","Unidades por segmento",clients["datos"],"unidades","Unidades","horizontal","numero"),_chart("line","Evolución mensual",trend["datos"],"ingresos","Ingresos")]
  dash_title="Dashboard de clientes y segmentos"
 else:
  charts=[_chart("line","Evolución mensual de ingresos",trend["datos"],"ingresos","Ingresos",description=f"Comportamiento de ingresos durante {period}."),_chart("bar","Productos con mayores ingresos",products["datos"],"ingresos","Ingresos","horizontal"),_chart("doughnut","Participación por canal",channels["datos"],"ingresos","Ingresos"),_chart("bar","Ingresos por segmento",clients["datos"],"ingresos","Ingresos")]
  dash_title=title or "Dashboard ejecutivo de ventas"
 return {"title":dash_title,"subtitle":f"Periodo: {period} · Fuente: PostgreSQL RopaV","filters":filters,"kpis":_kpis(k),"charts":charts}
