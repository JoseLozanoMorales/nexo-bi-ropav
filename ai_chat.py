"""Orquestador OpenAI -> herramientas MCP -> PostgreSQL."""
import json, os
from openai import OpenAI
from mcp_server import respond
MODEL=os.getenv("OPENAI_MODEL","gpt-5-mini")
SYSTEM="""Eres Nexo BI, analista de la tienda RopaV. Responde en espanol claro y conciso. Para cualquier cifra del negocio usa herramientas y nunca inventes valores. Elige la dimension apropiada, cita como fuente PostgreSQL RopaV, explica el hallazgo y una recomendacion. Los importes de la base son USD. Puedes combinar consultas. Para registrar una venta consulta primero el catalogo, recopila todos los datos, resume la operacion y pide confirmacion explicita. Solo despues de que el usuario confirme claramente llama registrar_venta con confirmado_por_usuario=true. Nunca adivines identificadores."""
def mcp_request(method,params=None,request_id=1):
 answer=respond({"jsonrpc":"2.0","id":request_id,"method":method,"params":params or {}})
 if not answer or "error" in answer: raise RuntimeError(str(answer))
 return answer["result"]
def openai_tools():
 return [{"type":"function","name":t["name"],"description":t["description"],"parameters":t["inputSchema"]} for t in mcp_request("tools/list")["tools"]]
def ask(messages):
 if not os.getenv("OPENAI_API_KEY"): raise RuntimeError("OPENAI_API_KEY no esta configurada")
 client=OpenAI(); history=[{"role":m["role"],"content":str(m["content"])[:6000]} for m in messages[-12:] if m.get("role") in ("user","assistant")]
 response=client.responses.create(model=MODEL,instructions=SYSTEM,input=history,tools=openai_tools(),parallel_tool_calls=False)
 used=[]
 for _ in range(5):
  calls=[item for item in response.output if item.type=="function_call"]
  if not calls: return {"text":response.output_text,"tools":used,"model":MODEL}
  outputs=[]
  for call in calls:
   args=json.loads(call.arguments or "{}"); result=mcp_request("tools/call",{"name":call.name,"arguments":args},len(used)+10)
   used.append({"name":call.name,"arguments":args,"error":bool(result.get("isError"))})
   outputs.append({"type":"function_call_output","call_id":call.call_id,"output":json.dumps(result,ensure_ascii=False)})
  response=client.responses.create(model=MODEL,instructions=SYSTEM,previous_response_id=response.id,input=outputs,tools=openai_tools(),parallel_tool_calls=False)
 raise RuntimeError("Se alcanzo el limite de llamadas de herramientas")
