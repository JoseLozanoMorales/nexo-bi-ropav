"""Servidor MCP de Nexo BI: stdio y puente interno para el chat."""
from __future__ import annotations
import json, sys
from datetime import date
from db import add_sale, catalog, dashboard, init_db

DIMENSIONS=["resumen","tendencia","producto","categoria","region","canal","cliente","inventario","entrega"]
TOOLS=[
 {"name":"consultar_analitica","description":"Consulta indicadores reales de RopaV y una dimension. Usa resumen para KPIs, tendencia para meses, inventario para stock y entrega para logistica.","inputSchema":{"type":"object","required":["dimension"],"properties":{"dimension":{"type":"string","enum":DIMENSIONS},"desde":{"type":"string","description":"Fecha YYYY-MM-DD"},"hasta":{"type":"string","description":"Fecha YYYY-MM-DD"},"region":{"type":"string","description":"Provincia exacta"},"canal":{"type":"string","description":"Canal exacto"}},"additionalProperties":False}},
 {"name":"consultar_catalogo","description":"Obtiene productos/SKU con stock, clientes, canales, administradores y metodos de pago validos.","inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
 {"name":"registrar_venta","description":"Registra una venta real y actualiza inventario y dashboards. Solo tras confirmacion explicita y despues de consultar el catalogo.","inputSchema":{"type":"object","required":["fecha","id_variante","id_cliente","id_canal","id_admin","id_metodo_pago","cantidad","precio","confirmado_por_usuario"],"properties":{"fecha":{"type":"string"},"id_variante":{"type":"integer"},"id_cliente":{"type":"integer"},"id_canal":{"type":"integer"},"id_admin":{"type":"integer"},"id_metodo_pago":{"type":"integer"},"cantidad":{"type":"integer","minimum":1},"precio":{"type":"number","minimum":0},"es_personalizado":{"type":"boolean"},"confirmado_por_usuario":{"type":"boolean"}},"additionalProperties":False}}
]
def text_result(data): return {"content":[{"type":"text","text":json.dumps(data,ensure_ascii=False)}],"structuredContent":data}
def call_tool(name,args):
 if name=="consultar_analitica":
  dimension=args.get("dimension","resumen"); filters={k:v for k,v in args.items() if k in ("desde","hasta","region","canal") and v}; data=dashboard(filters)
  if dimension not in DIMENSIONS: raise ValueError("Dimension no valida")
  return text_result({"fuente":"PostgreSQL RopaV","dimension":dimension,"filtros":filters,"indicadores":data["kpi"],"datos":data["kpi"] if dimension=="resumen" else data[dimension],"nota_inventario":"En inventario, ingresos=stock disponible y utilidad=stock minimo."})
 if name=="consultar_catalogo": return text_result(catalog())
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
