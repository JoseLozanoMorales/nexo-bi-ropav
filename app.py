"""Aplicacion web transaccional. Ejecutar: python app.py"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from db import add_sale, catalog, dashboard, delete_sale, dw_status, init_db, sync_powerbi
from ai_chat import MODEL as OPENAI_MODEL, ask as ask_ai


ROOT = Path(__file__).parent
POWER_BI_EMBED_URL = os.getenv("POWER_BI_EMBED_URL", "https://app.powerbi.com/reportEmbed?reportId=7602737b-4a3d-4489-b108-ac24ef5ebc8a&autoAuth=true&ctid=edd334f8-81c6-4062-ad3a-87668a1e074e")

TABLEAU_OBJETIVOS = [
    {"id": "ventas", "numero": 1, "titulo": "Ventas: fin de semana vs. laboral y evolución mensual",
     "pregunta": "¿Cómo evolucionan las ventas mes a mes y qué diferencia hay entre días laborables y fines de semana, por canal?",
     "env": "TABLEAU_EMBED_URL_VENTAS"},
    {"id": "inventario", "numero": 2, "titulo": "Inventario: tallas que se agotan más rápido",
     "pregunta": "¿Qué tallas, dentro de cada categoría, están más cerca de quedarse sin stock?",
     "env": "TABLEAU_EMBED_URL_INVENTARIO"},
    {"id": "canal", "numero": 3, "titulo": "Canal: gasto promedio por canal y categoría",
     "pregunta": "¿Qué canal genera mayor gasto promedio por cliente y en qué categorías?",
     "env": "TABLEAU_EMBED_URL_CANAL"},
    {"id": "productos", "numero": 4, "titulo": "Productos: personalizado vs. estándar",
     "pregunta": "¿Los productos personalizados dejan más ganancia que los estándar, y en qué categorías?",
     "env": "TABLEAU_EMBED_URL_PRODUCTOS"},
    {"id": "region", "numero": 5, "titulo": "Región: Costa, Sierra y Oriente",
     "pregunta": "¿Qué región y provincia generan más ingresos, y con qué mezcla de categorías?",
     "env": "TABLEAU_EMBED_URL_REGION"},
]


def tableau_objetivos():
    objetivos = []
    for o in TABLEAU_OBJETIVOS:
        url = os.getenv(o["env"], "")
        objetivos.append({"id": o["id"], "numero": o["numero"], "titulo": o["titulo"],
                          "pregunta": o["pregunta"], "embed_url": url, "publicado": bool(url)})
    return objetivos


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            return self.send_json(dashboard(params))
        if parsed.path == "/api/catalogo":
            return self.send_json(catalog())
        if parsed.path == "/api/integraciones":
            return self.send_json({"powerbi": {"embed_url": POWER_BI_EMBED_URL, "dw": dw_status()},
                                   "mcp": {"activo": True, "ia_configurada": bool(os.getenv("OPENAI_API_KEY")), "modelo": OPENAI_MODEL},
                                   "tableau": {"objetivos": tableau_objetivos()}})
        if parsed.path == "/api/chat/status":
            return self.send_json({"ok": True, "ia_configurada": bool(os.getenv("OPENAI_API_KEY")),
                                   "modelo": OPENAI_MODEL, "mcp": True})
        path = ROOT / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
        if not path.is_file() or ROOT not in path.resolve().parents:
            return self.send_error(404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/powerbi/sincronizar":
            try:
                return self.send_json({"ok": True, **sync_powerbi()})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        if path == "/api/chat":
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length))
                messages = payload.get("messages", [])
                if not messages or messages[-1].get("role") != "user":
                    raise ValueError("Se requiere un mensaje del usuario")
                return self.send_json({"ok": True, **ask_ai(messages)})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, 400)
        if path != "/api/ventas":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            sale_id = add_sale(payload)
            self.send_json({"ok": True, "id": sale_id}, 201)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)

    def do_DELETE(self):
        try:
            sale_id = int(urlparse(self.path).path.removeprefix("/api/ventas/"))
            self.send_json({"ok": delete_sale(sale_id)})
        except ValueError:
            self.send_json({"ok": False, "error": "Identificador invalido"}, 400)


if __name__ == "__main__":
    init_db()
    address = ("0.0.0.0", 8000)
    print("Nexo BI disponible en http://0.0.0.0:8000")
    ThreadingHTTPServer(address, Handler).serve_forever()
