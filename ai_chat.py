"""Orquestador OpenAI -> herramientas MCP -> PostgreSQL."""
import json, logging, os, re, unicodedata
from datetime import datetime, timedelta, timezone
from openai import OpenAI
from weekly_analysis import SALE_CRITERION, weekly_text
from mcp_server import respond
from dashboard_builder import build_dashboard
from objective_dashboards import detect_objective
from semantic_analytics import DIMENSIONS as SEMANTIC_DIMENSIONS, MEASURES as SEMANTIC_MEASURES
MODEL=os.getenv("OPENAI_MODEL","gpt-5-mini")
MAX_TOOL_ROUNDS=max(1,min(int(os.getenv("MAX_TOOL_ROUNDS","10")),20))
logger=logging.getLogger("nexo_bi.tools")
COLOMBIA_TZ=timezone(timedelta(hours=-5))
def _today():
 return datetime.now(COLOMBIA_TZ).date().isoformat()
def _system_instructions():
 return SYSTEM+"\n"+SALE_CRITERION+"\nAclara siempre ese criterio cuando informes ventas. Nunca llames todas las ventas a un conteo que excluye canceladas. Para estacionalidad semanal consulta consultar_semantica con dia_semana y canal, metrica transacciones. Usa los promedios calendario de estacionalidad_semanal; nunca dividas los totales históricos entre 5 o 2 para afirmar un promedio diario. No infieras ticket promedio, gasto por compra ni afluencia desde transacciones; requieren sus propias métricas. Si la herramienta no permite incluir canceladas, explica la limitación sin fingir haberlas consultado."+f"""
Fecha real actual en Colombia: {_today()}. Distingue siempre la fecha real de consulta de la fecha máxima disponible en los datos.
La última fecha con registros NO equivale a hoy. Para preguntas con hoy o a día de hoy consulta también consultar_periodos.
Di: a fecha actual X, con datos disponibles hasta Y. Ventas de hoy significa sólo X; a día de hoy significa acumulado hasta X. Nunca escribas que a día de hoy equivale al último registro Y; di que la consulta llega hasta X y que no existen registros posteriores a Y."""
SYSTEM="""Eres Nexo BI, analista de la tienda RopaV. Responde en espanol claro y conciso. Para cualquier cifra del negocio usa herramientas y nunca inventes valores. Elige la dimension apropiada. Para fechas disponibles usa consultar_periodos. Para productos mas vendidos usa dimension producto y orden unidades; para clientes individuales con mas compras usa dimension cliente_individual, orden unidades y el limite solicitado; nunca sustituyas clientes individuales por segmentos; para mayor facturacion usa orden ingresos. Distingue región de provincia: región sólo puede ser Costa, Sierra, Amazonía o Insular; provincia es Pichincha, Guayas, Azuay u otra provincia. Nunca sustituyas una por la otra. No envies region, provincia o canal cuando el usuario no los especifique; nunca uses Todos o Todas como valor de filtro. Copia exactamente filtros e indicadores y nunca afirmes que no hay ventas si transacciones es mayor que cero, cita como fuente PostgreSQL RopaV, explica el hallazgo y una recomendacion. Los importes de la base son USD. Puedes combinar consultas. Para preguntas sobre nombres de tablas, esquemas, columnas, campos o relaciones usa siempre consultar_esquema y responde con los metadatos reales; no digas que careces de acceso al esquema. Si el usuario pide un gráfico, gráfica o visualización, consulta inmediatamente la dimensión necesaria con consultar_analitica y no solicites confirmacion para consultas o graficos de solo lectura y no preguntes si desea generarlo: la aplicación lo mostrará en esa misma respuesta. Para histogramas del importe de ventas usa siempre consultar_distribucion_ventas y nunca consultar_analitica. Respeta exactamente el tipo solicitado: barras verticales u horizontales, líneas, área, pastel, dona/anillo o dispersión. No sustituyas un gráfico de pastel por barras. Cuando el usuario pida una recomendación de ropa o producto usa siempre recomendar_productos antes de responder. Recomienda SKU concretos disponibles, indicando producto, SKU, precio, stock, talla y color. Basa la justificación sólo en los datos devueltos y marca como inferencia cualquier adecuación deducida del nombre o categoría; nunca inventes material, transpirabilidad, grosor o temporada. Para registrar una venta consulta primero el catalogo, recopila todos los datos, resume la operacion y pide confirmacion explicita. Solo despues de que el usuario confirme claramente llama registrar_venta con confirmado_por_usuario=true. Nunca adivines identificadores. Mantén el contexto conversacional: expresiones como este año, ese año, el mismo periodo, ese trimestre o allí heredan los filtros y referentes establecidos en turnos anteriores; si el turno anterior fijó 2025, este año en el siguiente turno se refiere a 2025 y no al año calendario actual."""

def _continuation_message(text):
 plain=_plain_text(text).strip()
 tokens=r"(?:si|no|[12]|procede|hazlo|adelante|genera(?:lo)?|muestralo|muestrame(?:lo)?|continua|de acuerdo)"
 if re.fullmatch(rf"\s*{tokens}(?:[\s,!.]+{tokens})*[.!\s]*",plain,re.I): return True
 return len(plain.split())<=10 and bool(re.search(r"\b(agrega(?:lo)?|anade(?:lo)?|incluye(?:lo)?|filtra(?:lo)?|aplica(?:lo)?|usa(?:lo)?)\b",plain))

SYSTEM += "\nPara objetivos oficiales de Power BI consulta consultar_objetivos_dashboards: 1 semanal, 2 mensual, 3 región, 4 clientes, 5 personalización, 6 promociones. Si piden recrear uno usa generar_dashboard_objetivo, sin sustituirlo por un dashboard genérico. Son recreaciones funcionales, no archivos PBIX. Conserva advertencias y explica las fórmulas devueltas, no otras fórmulas de utilidad. No equipares margen de promociones con ROI causal."

def _request_text(messages):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if not users: return ""
 current=users[-1]
 if not _continuation_message(current): return current
 # Las continuaciones se resuelven sólo con peticiones del usuario.
 return " ".join(users[-5:])

def _current_date_args(messages,args):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if not users: return args
 plain=_plain_text(users[-1])
 if not re.search(r"\b(hoy|dia de hoy)\b",plain): return args
 today=_today()
 accumulated=bool(re.search(r"\b(a|al|hasta)\s+(?:el\s+)?(?:dia de )?hoy\b",plain))
 args["hasta"]=today
 if accumulated:
  if args.get("desde") and args["desde"]>today: args.pop("desde",None)
 else:
  args["desde"]=today
 return args
def _contextual_time_args(messages,args):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if len(users)<2: return args
 current=users[-1]; plain=_plain_text(current)
 if re.search(r"\b20\d{2}(?:-\d{2}-\d{2})?\b",current): return args
 relative=bool(re.search(r"\b(este|esta|ese|esa|mismo|misma|dicho|dicha|anterior)\s+(ano|periodo|rango|trimestre|mes|fecha)\b|\ben ese (?:ano|periodo|rango|trimestre|mes)\b",plain))
 if not relative: return args
 prior_users=" ".join(users[:-1])
 dates=re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b",prior_users)
 if len(dates)>=2 and re.search(r"\b(periodo|rango|fechas?)\b",plain):
  args["desde"],args["hasta"]=dates[-2],dates[-1]
  return args
 years=re.findall(r"\b(20\d{2})\b",prior_users)
 if not years: return args
 year=years[-1]
 quarters={"primer":(1,3),"primero":(1,3),"segundo":(4,6),"tercer":(7,9),"tercero":(7,9),"cuarto":(10,12)}
 if "trimestre" in plain:
  prior_plain=_plain_text(prior_users)
  matches=re.findall(r"\b(primer|primero|segundo|tercer|tercero|cuarto)\s+trimestre(?:\s+(?:de|del)\s+)?(20\d{2})?",prior_plain)
  if matches:
   name,qyear=matches[-1]; year=qyear or year; start,end=quarters[name]
   args["desde"]=f"{year}-{start:02d}-01"
   last_day=31 if end in (3,12) else 30
   args["hasta"]=f"{year}-{end:02d}-{last_day:02d}"
   return args
 args["desde"],args["hasta"]=f"{year}-01-01",f"{year}-12-31"
 return args
def _normalize_analytics_args(messages,args):
 args=_current_date_args(messages,args)
 args=_contextual_time_args(messages,args)
 text=_request_text(messages)
 if re.search(r"clientes?",text,re.I) and re.search(r"(m[aá]s\s+(?:compr|realiz)|mayor(?:es)?\s+compr)",text,re.I):
  args["dimension"]="cliente_individual"; args["orden"]="unidades"
  match=re.search(r"\b(\d{1,2})\s+clientes?\b",text,re.I)
  if match: args["limite"]=max(1,min(int(match.group(1)),20))
 return args
def _plain_text(text):
 return "".join(ch for ch in unicodedata.normalize("NFKD",str(text).lower()) if not unicodedata.combining(ch))
def _chart_request(messages):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if not users: return False,False,None
 current=_plain_text(users[-1]).strip()
 affirmative=_continuation_message(current)
 relevant=_plain_text(" ".join(users[-4:] if affirmative else users[-1:]))
 horizontal=bool(re.search(r"\bhorizontales?\b",relevant))
 chart_type=None
 patterns=[
  ("histogram",r"\bhistogramas?\b"),
  ("doughnut",r"\b(donas?|donuts?|anillos?)\b"),
  ("pie",r"\b(pastel(?:es)?|tortas?|pies?|circular(?:es)?)\b"),
  ("area",r"\bareas?\b"),
  ("scatter",r"\b(dispersion(?:es)?|scatters?|puntos?)\b"),
  ("line",r"\b(lineas?|lineal(?:es)?)\b"),
  ("bar",r"\b(barras?|columnas?)\b")
 ]
 for kind,pattern in patterns:
  if re.search(pattern,relevant): chart_type=kind; break
 if chart_type is None and re.search(r"\bdistribucion\b.*\b(importe|monto|total|ticket)\b.*\b(transaccion|venta)\b",relevant):
  chart_type="histogram"
 wants=bool(re.search(r"\b(grafic\w*|visualiza\w*|charts?|diagramas?)\b",relevant)) or chart_type is not None
 return wants,horizontal,chart_type

def _histogram_args(messages):
 text=_request_text(messages)
 args=_current_date_args(messages,_contextual_time_args(messages,{}))
 dates=re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b",text)
 if len(dates)>=2:
  args["desde"],args["hasta"]=dates[-2],dates[-1]
 else:
  years=re.findall(r"\b(20\d{2})\b",text)
  if years:
   year=years[-1]; args["desde"],args["hasta"]=f"{year}-01-01",f"{year}-12-31"
 match=re.search(r"\b(\d{1,2})\s+(?:intervalos?|bins?)\b",text,re.I)
 args["intervalos"]=max(2,min(int(match.group(1)),30)) if match else 10
 return args

def _histogram_text(data):
 stats=data.get("estadisticas",{}); filters=data.get("filtros",{})
 if not data.get("datos"):
  return "No hay transacciones no canceladas para construir el histograma con esos filtros. Fuente: PostgreSQL RopaV."
 return (f"Histograma del importe total por transacción: {stats.get('ventas',0)} ventas distribuidas en "
         f"{filters.get('intervalos',10)} intervalos. Importe mínimo: USD {stats.get('minimo',0):,.2f}; "
         f"máximo: USD {stats.get('maximo',0):,.2f}; promedio: USD {stats.get('promedio',0):,.2f}. "
         "Fuente: PostgreSQL RopaV.")
def _advanced_chart_kind(messages):
 text=_plain_text(_request_text(messages))
 if re.search(r"\b(caja(?:s)?(?: y)? bigotes|boxplots?)\b",text): return "boxplot"
 if re.search(r"\b(apilad\w*|stacked)\b",text): return "stacked_bar"
 if re.search(r"\b(mapa(?:s)? de calor|heatmaps?)\b",text): return "heatmap"
 if re.search(r"\bparetos?\b",text): return "pareto"
 if re.search(r"\b(dispersion(?:es)?|scatters?)\b",text) and "producto" in text: return "scatter"
 if re.search(r"\bingresos?\b",text) and re.search(r"\butilidad\b",text) and (re.search(r"\blineas?\b",text) or re.search(r"\b(mensual\w*|evolucion)\b",text)): return "multi_line"
 return None

def _advanced_filters(messages):
 args=_histogram_args(messages); args.pop("intervalos",None)
 text=_plain_text(_request_text(messages))
 for region in ("Costa","Sierra","Amazonía","Insular"):
  if re.search(rf"\b{re.escape(_plain_text(region))}\b",text): args["region"]=region
 for province in ("Pichincha","Guayas","Manabí","Los Ríos","El Oro","Azuay","Tungurahua","Loja","Chimborazo","Imbabura"):
  if _plain_text(province) in text: args["provincia"]=province
 for channel in ("WhatsApp","Redes Sociales","Tienda Física"):
  if _plain_text(channel) in text: args["canal"]=channel
 return args

def _advanced_chart(messages):
 kind=_advanced_chart_kind(messages)
 if not kind:return None
 args=_advanced_filters(messages); text=_plain_text(_request_text(messages))
 if kind=="boxplot":
  group="provincia" if re.search(r"(?:por|agrupad\w* por)\s+provincia",text) else "region" if re.search(r"(?:por|agrupad\w* por)\s+region",text) else "canal"
  args["agrupar_por"]=group; tool="consultar_boxplot_ventas"
 elif kind=="stacked_bar":
  args["periodo"]="mes" if re.search(r"\b(mes|mensual\w*)\b",text) else "trimestre"
  args["metrica"]="ingresos" if "ingreso" in text else "utilidad" if "utilidad" in text else "unidades"
  args["segmento"]="region" if re.search(r"(?:segmentad\w*|apilad\w*)\s+por\s+region",text) else "provincia" if re.search(r"(?:segmentad\w*|apilad\w*)\s+por\s+provincia",text) else "canal"
  args["grupo"]="categoria" if "categoria" in text else "producto" if "producto" in text else "provincia" if "provincia" in text and args["segmento"]!="provincia" else "region" if "region" in text and args["segmento"]!="region" else "total"
  tool="consultar_barras_apiladas"
 elif kind=="heatmap":
  args["metrica"]="ingresos" if "ingreso" in text else "utilidad" if "utilidad" in text else "unidades"; tool="consultar_mapa_calor"
 elif kind=="scatter":
  match=re.search(r"\b(?:top|limite|primeros?)\s*(\d{1,3})\b",text); args["limite"]=int(match.group(1)) if match else 50; tool="consultar_dispersion_productos"
 elif kind=="pareto":
  match=re.search(r"\b(?:top|limite|primeros?)\s*(\d{1,3})\b",text); args["limite"]=int(match.group(1)) if match else 20; tool="consultar_pareto"
 else:
  args["incluir_margen"]=bool(re.search(r"\bmargen\b",text)); tool="consultar_series_mensuales"
 result=mcp_request("tools/call",{"name":tool,"arguments":args},7)
 if result.get("isError"): raise RuntimeError(result.get("content",[{"text":"No se pudo construir el gráfico"}])[0]["text"])
 chart=result.get("structuredContent")
 if not isinstance(chart,dict) or not chart.get("type"): raise RuntimeError("La consulta avanzada no devolvió un gráfico renderizable")
 periods=mcp_request("tools/call",{"name":"consultar_periodos","arguments":{}},8).get("structuredContent",{}).get("rango",{})
 text_response=f"Gráfico {chart['title']} generado con datos reales. Periodo consultado: {args.get('desde','inicio disponible')} a {args.get('hasta','fin disponible')}. Datos disponibles hasta {periods.get('hasta','fecha no disponible')}. Fuente: PostgreSQL RopaV."
 return {"text":text_response,"tools":[{"name":tool,"arguments":args,"error":False,"cached":False},{"name":"consultar_periodos","arguments":{},"error":False,"cached":False}],"model":MODEL,"chart":chart}
def _chart(result,messages):
 d=result.get("structuredContent",{}); dim=d.get("dimension"); rows=d.get("datos"); filters=d.get("filtros",{})
 if not isinstance(rows,list) or not rows or dim=="resumen": return None
 rows=rows[:30]; titles={"histograma_ventas":"Distribución del importe por venta","tendencia":"Evolución de ventas","producto":"Ventas por producto","categoria":"Ventas por categoría","region":"Ventas por región","provincia":"Ventas por provincia","canal":"Ventas por canal","cliente":"Ventas por segmento","cliente_individual":"Clientes con más compras","inventario":"Inventario disponible","entrega":"Estado de entregas"}
 order=filters.get("orden")
 if dim=="histograma_ventas": sets=[{"label":"Número de ventas","values":[r.get("frecuencia",0) for r in rows],"color":"#11a99a"}]; fmt="numero"
 elif dim=="inventario": sets=[{"label":"Stock disponible","values":[r.get("ingresos",0) for r in rows],"color":"#11a99a"},{"label":"Stock mínimo","values":[r.get("utilidad",0) for r in rows],"color":"#ff9f68"}]; fmt="numero"
 elif dim=="entrega": sets=[{"label":"Entregas","values":[r.get("ingresos",0) for r in rows],"color":"#11a99a"}]; fmt="numero"
 elif order=="unidades": sets=[{"label":"Unidades vendidas","values":[r.get("unidades",0) for r in rows],"color":"#11a99a"}]; fmt="numero"
 elif order=="utilidad": sets=[{"label":"Utilidad","values":[r.get("utilidad",0) for r in rows],"color":"#ff9f68"}]; fmt="moneda"
 else: sets=[{"label":"Ingresos","values":[r.get("ingresos",0) for r in rows],"color":"#11a99a"}]; fmt="moneda"
 wants,horizontal,requested_type=_chart_request(messages)
 kind=requested_type or ("line" if dim=="tendencia" else "bar")
 colors=["#11a99a","#ff9f68","#56c5d0","#8576d4","#e57b9b","#f2c14e","#4f86c6","#72b01d","#d95d39","#6c5b7b","#2a9d8f","#e76f51"][:len(rows)]
 return {"type":kind,"orientation":"horizontal" if horizontal and kind=="bar" else "vertical","title":titles.get(dim,"Análisis de datos"),"labels":[str(r.get("etiqueta","")) for r in rows],"datasets":sets,"colors":colors,"value_format":fmt,"source":"PostgreSQL RopaV"}
def _validated_text(text,evidence):
 if not evidence: return text
 k=evidence.get("indicadores",{})
 if k.get("transacciones",0)>0 and re.search(r"(no hay|no existen|sin ventas|0 transacciones)",text,re.I):
  rows=evidence.get("datos",[]); lines=[f"{i+1}. {r.get('etiqueta','Dato')}: {r.get('unidades',0)} unidades, {r.get('ingresos',0):,.2f} USD" for i,r in enumerate(rows[:10])]
  return "La consulta si encontro ventas. Filtros: "+json.dumps(evidence.get("filtros",{}),ensure_ascii=False)+f". Indicadores: {k.get('transacciones')} transacciones, {k.get('unidades')} unidades, {k.get('ingresos'):,.2f} USD."+"\n\nResultados:\n"+"\n".join(lines)
 return text

def _recommendation_request(messages):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if not users:return False
 pattern=r"\b(recom(?:endar|endarias|endacion|iend\w*)|aconsej\w*|sugi(?:er|ere|ere\w*)|que\s+me\s+pongo|que\s+(?:ropa|prenda|producto)\s+(?:usar|elegir|comprar)|conviene\s+(?:usar|comprar))\b"
 current=_plain_text(users[-1])
 if re.search(pattern,current):return True
 return _continuation_message(current) and len(users)>1 and bool(re.search(pattern,_plain_text(users[-2])))

def _recommendation_args(messages):
 text=_request_text(messages); plain=_plain_text(text); args={"necesidad":text,"limite":3}
 count=re.search(r"\b([1-5])\s+(?:opciones?|productos?|prendas?|recomendaciones?)\b",plain)
 if count: args["limite"]=int(count.group(1))
 price=re.search(r"(?:maximo|hasta|menos de|presupuesto(?: de)?)\s*(?:usd|us\$|\$)?\s*(\d+(?:[.,]\d+)?)",plain)
 if price: args["precio_maximo"]=float(price.group(1).replace(",","."))
 size=re.search(r"\btalla\s+([a-z0-9]{1,4})\b",plain)
 if size: args["talla"]=size.group(1).upper()
 return args

def _recommendation_text(data):
 products=data.get("productos",[])
 if not products: return "No encontré productos con stock que cumplan esos criterios. Prueba quitando la talla o ampliando el presupuesto."
 lines=["Te recomiendo estas opciones reales disponibles en RopaV:"]
 for index,item in enumerate(products,1):
  reasons="; ".join(item.get("motivos",[]))
  lines.append(f"{index}. {item['producto']} — SKU {item['sku']}\n   Categoría: {item['categoria']} · Talla: {item['talla']} · Color: {item['color']}\n   Precio: USD {item['precio']:,.2f} · Stock: {item['stock']}\n   Motivo: {reasons}.")
 lines.append("Fuente: PostgreSQL RopaV.")
 lines.append("Nota: la adecuación se infiere del nombre y la categoría. La base no registra material, grosor, temporada ni transpirabilidad como atributos independientes.")
 return "\n\n".join(lines)
def _dashboard_request(messages):
 text=_plain_text(_request_text(messages))
 return bool(re.search(r"\b(dashboards?|tableros?|panel(?:es)?(?:\s+ejecutivos?)?)\b",text))
def _dashboard_filters(messages):
 text=_request_text(messages); filters=_advanced_filters(messages)
 plain=_plain_text(text); named_regions=[name for name in ("Costa","Sierra","Amazonía","Insular") if _plain_text(name) in plain]
 if len(named_regions)>1 and re.search(r"\b(compar\w*|versus|vs|contra)\b",plain): filters.pop("region",None)
 dates=re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b",text)
 if len(dates)>=2: filters.update({"desde":dates[0],"hasta":dates[1]})
 else:
  years=re.findall(r"\b(20\d{2})\b",text)
  if years: filters.update({"desde":years[-1]+"-01-01","hasta":years[-1]+"-12-31"})
 return filters

DASHBOARD_LABELS={"ingresos":"Ingresos","utilidad":"Utilidad","margen":"Margen","transacciones":"Transacciones","unidades":"Unidades","clientes":"Clientes","ticket_promedio":"Ticket promedio","unidades_por_venta":"Unidades por venta"}
DASHBOARD_FORMULAS={
 "ingresos":"SUM(subtotal de las líneas de venta)",
 "utilidad":"SUM(cantidad × (precio unitario - costo de compra))",
 "margen":"100 × utilidad / ingresos",
 "unidades":"SUM(cantidad vendida)",
 "transacciones":"COUNT(DISTINCT id_venta)",
 "clientes":"COUNT(DISTINCT id_cliente)",
 "ticket_promedio":"ingresos / transacciones",
 "unidades_por_venta":"unidades / transacciones"
}
def _dashboard_explanation(messages):
 users=[str(m.get("content","")) for m in messages if m.get("role")=="user"]
 if not users or not re.search(r"\b(medidas?|metricas?|formulas?|calculos?)\b",_plain_text(users[-1])):return None
 prior=next((m.get("dashboard") for m in reversed(messages[:-1]) if isinstance(m.get("dashboard"),dict)),None)
 if not prior:return None
 if prior.get("objective_id") and prior.get("measure_definitions"):
  lines=[f"Objetivo {prior['objective_id']}: {prior.get('objective','')}","Medidas de la recreación funcional de Power BI:"]
  lines += [f"- {name}: {formula}" for name,formula in prior["measure_definitions"].items()]
  lines += ["\nVisuales y propósito:"]+[f"- {chart['title']}: {chart.get('description','')}" for chart in prior.get("charts",[])]
  lines += ["\nCriterios y límites:"]+prior.get("warnings",[])
  return {"text":"\n".join(lines),"tools":[],"model":MODEL,"chart":None}
 metrics=[]
 for item in prior.get("kpis",[]):
  key=next((name for name,label in DASHBOARD_LABELS.items() if label.casefold()==str(item.get("label","")).casefold()),None)
  if key:metrics.append(key)
 chart_lines=[]
 for chart in prior.get("charts",[]):
  semantic=chart.get("semantic") or {}; metric=semantic.get("metrica"); dimensions=semantic.get("dimensiones") or []
  if metric:metrics.append(metric); chart_lines.append(f"- {chart.get('title','Gráfico')}: {metric} agrupado por {', '.join(dimensions)}.")
 metrics=list(dict.fromkeys(metrics)); formula_lines=[f"- {DASHBOARD_LABELS.get(metric,metric)}: {DASHBOARD_FORMULAS.get(metric,'agregación validada por la capa semántica')}." for metric in metrics]
 text="El dashboard no creó medidas DAX ni cálculos de Tableau; usó agregaciones SQL de la capa semántica.\n\nMedidas realmente utilizadas:\n"+"\n".join(formula_lines)
 if chart_lines:text+="\n\nAplicación en las gráficas:\n"+"\n".join(chart_lines)
 text+="\n\nTodos los cálculos excluyen ventas con estado Cancelada y respetan los filtros guardados en el dashboard. Fuente: PostgreSQL RopaV."
 return {"text":text,"tools":[],"model":MODEL,"chart":None}
DASHBOARD_PLAN_SCHEMA={
 "type":"object","properties":{
  "title":{"type":"string"},
  "kpis":{"type":"array","minItems":3,"maxItems":6,"items":{"type":"string","enum":["ingresos","utilidad","margen","transacciones","unidades","clientes","ticket_promedio","unidades_por_venta"]}},
  "charts":{"type":"array","minItems":2,"maxItems":6,"items":{"type":"object","properties":{
   "dimensions":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"string","enum":list(SEMANTIC_DIMENSIONS)}},
   "metric":{"type":"string","enum":list(SEMANTIC_MEASURES)},
   "type":{"type":"string","enum":["bar","line","area","pie","doughnut","scatter"]},
   "orientation":{"type":"string","enum":["vertical","horizontal"]},
   "title":{"type":"string"},
   "limit":{"type":"integer","minimum":2,"maximum":20}
  },"required":["dimensions","metric","type","orientation","title","limit"],"additionalProperties":False}}
 },"required":["title","kpis","charts"],"additionalProperties":False
}
DASHBOARD_PLANNER=f"""Diseña un dashboard de ventas estrictamente según la petición.
Combina TODAS las áreas solicitadas y no sustituyas dimensiones. Cada gráfico declara una o dos dimensiones reales.
Dimensiones disponibles: {', '.join(SEMANTIC_DIMENSIONS)}.
Métricas disponibles: {', '.join(SEMANTIC_MEASURES)}.
Usa mes + otra dimensión para tendencias segmentadas. Género usa genero; segmento comercial usa segmento_cliente.
Margen usa exclusivamente la métrica margen, nunca utilidad. Para tendencia usa línea/área; ranking barras horizontales; participación dona/pastel.
Los títulos son orientativos: el servidor los reemplaza por títulos derivados de la consulta real.
Selecciona de 3 a 6 KPI y de 2 a 6 gráficos. No inventes ni reemplaces una dimensión no disponible."""

def _dashboard_plan(prompt):
 if not os.getenv("OPENAI_API_KEY"): return None
 try:
  response=OpenAI().responses.create(model=MODEL,instructions=DASHBOARD_PLANNER,input=prompt,text={"format":{"type":"json_schema","name":"dashboard_plan","strict":True,"schema":DASHBOARD_PLAN_SCHEMA}})
  return json.loads(response.output_text)
 except Exception as error:
  logger.exception("No se pudo crear el plan dinámico del dashboard: %s",error)
  return None
def _fallback_text(data,reason):
 if not data: return "No pude completar el ciclo de herramientas. "+reason
 return "Recupere el ultimo resultado valido ("+reason+").\n\n"+json.dumps(data,ensure_ascii=False)[:6000]

def mcp_request(method,params=None,request_id=1):
 answer=respond({"jsonrpc":"2.0","id":request_id,"method":method,"params":params or {}})
 if not answer or "error" in answer: raise RuntimeError(str(answer))
 return answer["result"]
def openai_tools():
 return [{"type":"function","name":t["name"],"description":t["description"],"parameters":t["inputSchema"]} for t in mcp_request("tools/list")["tools"]]
def ask(messages):
 explanation=_dashboard_explanation(messages)
 if explanation:return explanation
 objective_id=detect_objective(_request_text(messages))
 if objective_id and (_dashboard_request(messages) or re.search(r"\b(crea|genera|recrea|construye)\w*\b",_plain_text(_request_text(messages)))):
  filters=_dashboard_filters(messages)
  named_regions=[name for name in ("costa","sierra","amazonia","insular") if name in _plain_text(_request_text(messages))]
  if len(named_regions)>1: filters.pop("region",None)
  args={"objetivo":objective_id,**filters}
  result=mcp_request("tools/call",{"name":"generar_dashboard_objetivo","arguments":args},6)
  if result.get("isError"): raise RuntimeError(result.get("content",[{}])[0].get("text","No se pudo construir el dashboard"))
  spec=result["structuredContent"]
  return {"text":f"Dashboard del objetivo {objective_id}: {spec['objective']}\nRecreación funcional de Power BI con datos reales. Consulta las notas del panel para criterios y limitaciones.","tools":[{"name":"generar_dashboard_objetivo","arguments":args,"error":False}],"model":MODEL,"chart":None,"dashboard":spec}
 advanced=_advanced_chart(messages)
 if advanced:return advanced
 if _recommendation_request(messages):
  args=_recommendation_args(messages); result=mcp_request("tools/call",{"name":"recomendar_productos","arguments":args},8); data=result.get("structuredContent",{})
  return {"text":_recommendation_text(data),"tools":[{"name":"recomendar_productos","arguments":args,"error":bool(result.get("isError"))}],"model":MODEL,"chart":None}
 wants_chart,_,requested_chart_type=_chart_request(messages)
 if wants_chart and requested_chart_type=="histogram":
  args=_histogram_args(messages)
  result=mcp_request("tools/call",{"name":"consultar_distribucion_ventas","arguments":args},9)
  data=result.get("structuredContent",{})
  chart=_chart(result,messages)
  if data.get("datos") and chart is None:
   raise RuntimeError("La consulta del histograma devolvió datos, pero no se pudo construir la visualización")
  return {"text":_histogram_text(data),"tools":[{"name":"consultar_distribucion_ventas","arguments":args,"error":bool(result.get("isError")),"cached":False}],"model":MODEL,"chart":chart}
 if _dashboard_request(messages):
  prompt=_request_text(messages); filters=_dashboard_filters(messages); plan=_dashboard_plan(prompt); spec=build_dashboard(filters,prompt=prompt,plan=plan)
  tools=[{"name":"consultar_semantica","arguments":{"dimensiones":chart["semantic"]["dimensiones"],"metrica":chart["semantic"]["metrica"],**filters},"error":False,"cached":False} for chart in spec["charts"] if chart.get("semantic")]
  return {"text":"Dashboard generado con datos de PostgreSQL RopaV.","tools":tools,"model":MODEL,"chart":None,"dashboard":spec}
 if not os.getenv("OPENAI_API_KEY"): raise RuntimeError("OPENAI_API_KEY no esta configurada")
 client=OpenAI(); history=[{"role":m["role"],"content":str(m["content"])[:6000]} for m in messages[-12:] if m.get("role") in ("user","assistant")]
 response=client.responses.create(model=MODEL,instructions=_system_instructions(),input=history,tools=openai_tools(),parallel_tool_calls=False)
 used=[]; chart=None; evidence=None; last_data=None; tool_cache={}; repeated_calls={}; weekly_evidence=None; sale_criterion=None
 for round_index in range(MAX_TOOL_ROUNDS):
  calls=[item for item in response.output if item.type=="function_call"]
  if not calls:
   answer=_validated_text(response.output_text,evidence)
   if weekly_evidence: answer=weekly_text(weekly_evidence)
   elif sale_criterion: answer+="\n\nCriterio de ventas: "+sale_criterion
   return {"text":answer,"tools":used,"model":MODEL,"chart":chart}
  outputs=[]
  for call in calls:
   args=json.loads(call.arguments or "{}")
   requested_type=_chart_request(messages)[2]; executed_name=call.name
   if call.name=="consultar_analitica": args=_normalize_analytics_args(messages,args)
   if requested_type=="histogram" and call.name=="consultar_analitica":
    text=_request_text(messages); match=re.search(r"\b(\d{1,2})\s+intervalos?\b",text,re.I)
    args={k:v for k,v in args.items() if k in ("desde","hasta")}; args["intervalos"]=int(match.group(1)) if match else 10; executed_name="consultar_distribucion_ventas"
   signature=executed_name+":"+json.dumps(args,sort_keys=True,ensure_ascii=False)
   cached=signature in tool_cache
   if cached:
    result=tool_cache[signature]; repeated_calls[signature]=repeated_calls.get(signature,0)+1
    logger.warning("Llamada MCP repetida: herramienta=%s ronda=%s repeticion=%s argumentos=%s",executed_name,round_index+1,repeated_calls[signature],json.dumps(args,ensure_ascii=False))
   else:
    result=mcp_request("tools/call",{"name":executed_name,"arguments":args},len(used)+10); tool_cache[signature]=result
    logger.warning("Llamada MCP: herramienta=%s ronda=%s argumentos=%s",executed_name,round_index+1,json.dumps(args,ensure_ascii=False))
   data=result.get("structuredContent") if not result.get("isError") else None
   if executed_name=="generar_dashboard_objetivo" and isinstance(data,dict):
    used.append({"name":executed_name,"arguments":args,"error":False,"cached":cached})
    return {"text":data["objective"],"tools":used,"model":MODEL,"chart":None,"dashboard":data}
   if data is not None: last_data=data
   if isinstance(data,dict):
    if data.get("criterio_ventas"): sale_criterion=data["criterio_ventas"]
    if data.get("estacionalidad_semanal"): weekly_evidence=data
   used.append({"name":executed_name,"arguments":args,"error":bool(result.get("isError")),"cached":cached})
   if _chart_request(messages)[0] and executed_name in ("consultar_analitica","consultar_distribucion_ventas") and not result.get("isError"): chart=_chart(result,messages) or chart
   if executed_name=="consultar_analitica" and not result.get("isError"): evidence=data
   if cached and repeated_calls[signature]>=2:
    return {"text":_fallback_text(last_data,"se detuvo una llamada repetida"),"tools":used,"model":MODEL,"chart":chart,"recovered":True}
   outputs.append({"type":"function_call_output","call_id":call.call_id,"output":json.dumps(result.get("structuredContent",result.get("content",result)),ensure_ascii=False)})
  response=client.responses.create(model=MODEL,instructions=_system_instructions(),previous_response_id=response.id,input=outputs,tools=openai_tools(),parallel_tool_calls=False)
 logger.warning("Maximo de rondas MCP alcanzado: %s",MAX_TOOL_ROUNDS)
 return {"text":_fallback_text(last_data,f"se alcanzo el maximo de {MAX_TOOL_ROUNDS} rondas"),"tools":used,"model":MODEL,"chart":chart,"recovered":True}
