"""Servidor MCP de Nexo BI: stdio y puente interno para el chat."""
from __future__ import annotations
import json, sys
from chat_evidence import cancellation_counts, validate_dates
from weekly_analysis import SALE_CRITERION
from objective_dashboards import objective_catalog, build_objective_dashboard
from datetime import date
from db import add_sale, catalog, dashboard, init_db, database_schema, sales_periods, sales_histogram, regions_catalog
from recommendations import recommend_products
from semantic_analytics import semantic_catalog, query_semantic, DIMENSIONS as SEMANTIC_DIMENSIONS, MEASURES as SEMANTIC_MEASURES
from statistical_charts import boxplot_sales, heatmap_month_province, monthly_income_profit, pareto_products, stacked_quarter_category_channel, stacked_sales, product_scatter
from forecasting import forecast

DIMENSIONS=["resumen","tendencia","producto","categoria","region","provincia","canal","cliente","cliente_individual","inventario","entrega"]
TOOLS=[
 {"name":"consultar_pronostico","description":"Proyecta una métrica mensual con tendencia lineal local, intervalos aproximados y limitaciones explícitas. No es causal ni una garantía.","inputSchema":{"type":"object","required":["metrica"],"properties":{"metrica":{"type":"string","enum":list(SEMANTIC_MEASURES)},"segmento":{"type":"string","enum":list(SEMANTIC_DIMENSIONS)},"horizonte_meses":{"type":"integer","minimum":1,"maximum":24},"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"personalizado":{"type":"string","enum":["Sí","No"]}},"additionalProperties":False}},
 {"name":"consultar_regiones","description":"Consulta el catálogo maestro de regiones. Puede incluir conteos de ventas sin eliminar regiones con cero ventas; distingue regiones registradas de regiones con actividad.","inputSchema":{"type":"object","properties":{"incluir_ventas":{"type":"boolean"},"incluir_canceladas":{"type":"boolean"},"desde":{"type":"string"},"hasta":{"type":"string"}},"additionalProperties":False}},
 {"name":"consultar_cancelaciones","description":"Cuenta TODAS las ventas, canceladas, no canceladas y sin estado por canal, con totales y comprobación. Solo lectura; úsala para comparar estados o incluir canceladas.","inputSchema":{"type":"object","properties":{k:{"type":"string"} for k in ("desde","hasta","region","provincia","canal")},"additionalProperties":False}},
 {"name":"consultar_objetivos_dashboards","description":"Los seis objetivos oficiales de RopaVacana: pregunta de negocio, medidas, gráficos, tablas y matrices de referencia Power BI.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"generar_dashboard_objetivo","description":"Recrea un dashboard con datos reales y fórmulas del PBIT. Objetivos: 1 semanal, 2 mensual, 3 regiones, 4 clientes, 5 personalización, 6 promociones. Solo lectura.","inputSchema":{"type":"object","required":["objetivo"],"properties":{"objetivo":{"type":"integer","minimum":1,"maximum":6},"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"}},"additionalProperties":False}},
 {"name":"consultar_analitica","description":"Consulta indicadores reales de RopaV y una dimension. Usa resumen para KPIs, tendencia para meses, inventario para stock y entrega para logistica.","inputSchema":{"type":"object","required":["dimension"],"properties":{"dimension":{"type":"string","enum":DIMENSIONS},"desde":{"type":"string","description":"Fecha YYYY-MM-DD"},"hasta":{"type":"string","description":"Fecha YYYY-MM-DD"},"region":{"type":"string","description":"Región exacta: Costa, Sierra, Amazonía o Insular"},"provincia":{"type":"string","description":"Provincia exacta"},"canal":{"type":"string","description":"Canal exacto"},"orden":{"type":"string","enum":["ingresos","unidades","utilidad"],"description":"Para productos mas vendidos usa unidades"},"limite":{"type":"integer","minimum":1,"maximum":20,"description":"Cantidad maxima de resultados"}},"additionalProperties":False}},
 {"name":"consultar_distribucion_ventas","description":"Construye un histograma real del importe total por transaccion usando ventas individuales no canceladas e intervalos iguales.","inputSchema":{"type":"object","properties":{"desde":{"type":"string","description":"Fecha YYYY-MM-DD"},"hasta":{"type":"string","description":"Fecha YYYY-MM-DD"},"intervalos":{"type":"integer","minimum":2,"maximum":30,"default":10}},"additionalProperties":False}},
 {"name":"consultar_periodos","description":"Obtiene el rango exacto y los meses con ventas registradas no canceladas.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"consultar_esquema","description":"Consulta metadatos reales de PostgreSQL RopaV. Lista tablas, describe columnas de una tabla o muestra relaciones por claves foraneas. Usala para preguntas sobre esquema, tablas, columnas, campos y relaciones.","inputSchema":{"type":"object","required":["accion"],"properties":{"accion":{"type":"string","enum":["listar_tablas","describir_tabla","listar_relaciones"]},"esquema":{"type":"string","enum":["public","dw"]},"tabla":{"type":"string","description":"Nombre exacto; requerido al describir una tabla"}},"additionalProperties":False}},
 {"name":"consultar_catalogo","description":"Obtiene productos/SKU con stock, clientes, canales, administradores y metodos de pago validos.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"consultar_modelo_semantico","description":"Lista las dimensiones y métricas reales disponibles para análisis dinámico de ventas.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"consultar_semantica","description":"Agrupa una métrica real por una o dos dimensiones validadas del modelo de ventas.","inputSchema":{"type":"object","required":["dimensiones","metrica"],"properties":{"dimensiones":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"string","enum":list(SEMANTIC_DIMENSIONS)}},"metrica":{"type":"string","enum":list(SEMANTIC_MEASURES)},"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"personalizado":{"type":"string","enum":["Sí","No"]},"limite":{"type":"integer","minimum":2,"maximum":500}},"additionalProperties":False}},
 {"name":"consultar_boxplot_ventas","description":"Calcula una caja y bigotes real del importe por transacción, agrupada por canal, provincia o región.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"agrupar_por":{"type":"string","enum":["canal","provincia","region"]}},"additionalProperties":False}},
 {"name":"consultar_barras_apiladas","description":"Construye barras apiladas configurables por mes o trimestre, dimensión de grupo, segmento y métrica.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"periodo":{"type":"string","enum":["mes","trimestre"]},"grupo":{"type":"string","enum":["total","categoria","producto","region","provincia"]},"segmento":{"type":"string","enum":["canal","region","provincia"]},"metrica":{"type":"string","enum":["unidades","ingresos","utilidad"]}},"additionalProperties":False}},
 {"name":"consultar_mapa_calor","description":"Construye una matriz mensual por provincia para unidades, ingresos o utilidad.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"metrica":{"type":"string","enum":["unidades","ingresos","utilidad"]}},"additionalProperties":False}},
 {"name":"consultar_dispersion_productos","description":"Construye un scatter real por producto con unidades en X e ingresos en Y.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"limite":{"type":"integer","minimum":2,"maximum":100}},"additionalProperties":False}},
 {"name":"consultar_pareto","description":"Ordena productos por ingresos y calcula el porcentaje acumulado para un Pareto.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"limite":{"type":"integer","minimum":2,"maximum":100}},"additionalProperties":False}},
 {"name":"consultar_series_mensuales","description":"Construye series mensuales de ingresos y utilidad, opcionalmente margen en eje secundario.","inputSchema":{"type":"object","properties":{"desde":{"type":"string"},"hasta":{"type":"string"},"region":{"type":"string"},"provincia":{"type":"string"},"canal":{"type":"string"},"incluir_margen":{"type":"boolean"}},"additionalProperties":False}}, {"name":"recomendar_productos","description":"Recomienda de 1 a 5 SKU reales con stock para una necesidad, ocasión o clima. Devuelve producto, SKU, categoría, talla, color, precio, stock, motivos y limitaciones. Úsala siempre que el usuario pida una recomendación de ropa o producto.","inputSchema":{"type":"object","required":["necesidad"],"properties":{"necesidad":{"type":"string","description":"Necesidad completa del usuario, por ejemplo ropa para el calor"},"limite":{"type":"integer","minimum":1,"maximum":5,"default":3},"precio_maximo":{"type":"number","minimum":0},"talla":{"type":"string"}},"additionalProperties":False}},
 {"name":"registrar_venta","description":"Registra una venta real y actualiza inventario y dashboards. Solo tras confirmacion explicita y despues de consultar el catalogo.","inputSchema":{"type":"object","required":["fecha","id_variante","id_cliente","id_canal","id_admin","id_metodo_pago","cantidad","precio","confirmado_por_usuario"],"properties":{"fecha":{"type":"string"},"id_variante":{"type":"integer"},"id_cliente":{"type":"integer"},"id_canal":{"type":"integer"},"id_admin":{"type":"integer"},"id_metodo_pago":{"type":"integer"},"cantidad":{"type":"integer","minimum":1},"precio":{"type":"number","minimum":0},"es_personalizado":{"type":"boolean"},"confirmado_por_usuario":{"type":"boolean"}},"additionalProperties":False}}
]
def text_result(data):
 if isinstance(data,dict) and ("indicadores" in data or "transacciones" in data or data.get("modelo")=="ventas"):
  data.setdefault("criterio_ventas",SALE_CRITERION)
 return {"content":[{"type":"text","text":json.dumps(data,ensure_ascii=False)}],"structuredContent":data}
def call_tool(name,args):
 validate_dates(args)
 if name=="consultar_pronostico": return text_result(forecast(args.get("metrica","ingresos"),args.get("segmento"),{k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal","personalizado")},args.get("horizonte_meses",3)))
 if name=="consultar_regiones": return text_result(regions_catalog(bool(args.get("incluir_ventas")),bool(args.get("incluir_canceladas")),args.get("desde"),args.get("hasta")))
 if name=="consultar_cancelaciones": return text_result(cancellation_counts(args))
 if name=="consultar_objetivos_dashboards": return text_result(objective_catalog())
 if name=="generar_dashboard_objetivo": return text_result(build_objective_dashboard(args.get("objetivo"),{k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")}))
 if name=="consultar_boxplot_ventas": return text_result(boxplot_sales({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},args.get("agrupar_por","canal")))
 if name=="consultar_barras_apiladas": return text_result(stacked_sales({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},args.get("periodo","trimestre"),args.get("grupo","categoria"),args.get("segmento","canal"),args.get("metrica","unidades")))
 if name=="consultar_mapa_calor": return text_result(heatmap_month_province({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},args.get("metrica","unidades")))
 if name=="consultar_dispersion_productos": return text_result(product_scatter({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},args.get("limite",50)))
 if name=="consultar_pareto": return text_result(pareto_products({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},args.get("limite",20)))
 if name=="consultar_series_mensuales": return text_result(monthly_income_profit({k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal")},bool(args.get("incluir_margen",False))))
 if name=="consultar_distribucion_ventas": return text_result(sales_histogram(args.get("desde"),args.get("hasta"),args.get("intervalos",10)))
 if name=="consultar_periodos": return text_result(sales_periods())
 if name=="consultar_esquema": return text_result(database_schema(args.get("accion","listar_tablas"),args.get("esquema"),args.get("tabla")))
 if name=="consultar_analitica":
  dimension=args.get("dimension","resumen"); filters={k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal","orden","limite") and str(v).strip().casefold() not in ("todo","todos","toda","todas","all")}; data=dashboard(filters)
  if dimension not in DIMENSIONS: raise ValueError("Dimension no valida")
  return text_result({"fuente":"PostgreSQL RopaV","dimension":dimension,"filtros":filters,"indicadores":data["kpi"],"datos":data["kpi"] if dimension=="resumen" else data[dimension],"nota_inventario":"En inventario, ingresos=stock disponible y utilidad=stock minimo."})
 if name=="consultar_catalogo": return text_result(catalog())
 if name=="recomendar_productos": return text_result(recommend_products(args.get("necesidad",""),args.get("limite",3),args.get("precio_maximo"),args.get("talla")))
 if name=="consultar_modelo_semantico": return text_result(semantic_catalog())
 if name=="consultar_semantica": return text_result(query_semantic(args.get("dimensiones"),args.get("metrica"),{k:v for k,v in args.items() if k in ("desde","hasta","region","provincia","canal","personalizado")},args.get("limite",12)))
 if name=="registrar_venta":
  if args.pop("confirmado_por_usuario",False) is not True: raise ValueError("Se requiere confirmacion explicita")
  args.setdefault("fecha",date.today().isoformat()); sale_id=add_sale(args)
  return text_result({"registrada":True,"id_venta":sale_id,"indicadores_actualizados":dashboard()["kpi"]})
 raise ValueError(f"Herramienta desconocida: {name}")
def respond(message):
 method,request_id=message.get("method"),message.get("id")
 if method=="initialize": result={"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"nexo-bi-ropav","version":"2.0.0"}}
 elif method=="tools/list": result={"tools":TOOLS}
 elif method=="tools/call":
  p=message.get("params",{})
  try: result=call_tool(p.get("name",""),p.get("arguments",{}))
  except Exception as exc: result={"isError":True,"content":[{"type":"text","text":str(exc)}]}
 elif method in ("notifications/initialized","ping"): result={} if method=="ping" else None
 else: return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"Metodo no encontrado"}}
 return None if request_id is None else {"jsonrpc":"2.0","id":request_id,"result":result}
def main():
 init_db()
 for line in sys.stdin:
  try:
   answer=respond(json.loads(line))
   if answer is not None: print(json.dumps(answer,ensure_ascii=False),flush=True)
  except Exception as exc: print(json.dumps({"jsonrpc":"2.0","id":None,"error":{"code":-32603,"message":str(exc)}}),flush=True)
if __name__=="__main__": main()
