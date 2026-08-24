# Nexo BI — dashboards transaccionales de RopaV

Proyecto académico unificado que demuestra cómo cada nueva venta modifica inmediatamente los indicadores y dashboards. Incluye la aplicación transaccional, el servidor MCP y la integración con Power BI mediante un Data Warehouse dimensional sincronizado. Tableau queda visible como la siguiente fase del mismo programa.

## Ejecutar con Docker

Requiere Docker Desktop (o Docker Engine en Linux):

```bash
docker compose up --build
```

Abrir `http://127.0.0.1:8000`. La primera ejecución restaura automáticamente el backup en PostgreSQL 18 y conserva los cambios en un volumen persistente.

## Activar el chat OpenAI + MCP

1. Copiar `.env.example` como `.env`.
2. Escribir la clave en `OPENAI_API_KEY` dentro de `.env`. No pegarla en el código ni compartir ese archivo.
3. Ejecutar `docker compose up -d --build`.
4. Abrir la sección **IA + MCP** de Nexo BI.

El navegador nunca recibe la API key. La aplicación llama a OpenAI Responses API desde el servidor; el modelo descubre las herramientas publicadas por `mcp_server.py`, las invoca mediante JSON-RPC MCP y recibe datos de PostgreSQL. `OPENAI_MODEL` permite cambiar el modelo sin modificar el código.

Las consultas son automáticas. Para registrar una venta mediante el chat, la IA debe consultar primero el catálogo y solicitar una confirmación explícita antes de ejecutar la herramienta de escritura.

## Power BI

La aplicación crea el esquema `dw` del programa empresarial anterior y sincroniza cada venta o cancelación automáticamente. En Power BI Desktop conecta PostgreSQL a `localhost:5433`, base `RopaV`, esquema `dw`, usando **DirectQuery**. El reporte seguro se muestra en la sección Power BI de la aplicación; se puede reemplazar definiendo `POWER_BI_EMBED_URL` antes de iniciar Docker.

## Objetivos analíticos

1. Resumir ingresos, utilidad, margen, transacciones, unidades y clientes.
2. Analizar la evolución mensual de ventas y utilidad.
3. Identificar los productos de mayor rendimiento.
4. Evaluar la mezcla de categorías.
5. Comparar segmentos de clientes y provincias.
6. Medir la eficiencia de los canales comerciales.
7. Vigilar inventario, stock mínimo y alertas.
8. Analizar el estado de las entregas.

Los filtros de fecha, provincia y canal afectan las vistas comerciales. Una venta registrada se persiste en PostgreSQL, activa los triggers originales de inventario y actualiza los paneles sin recargar la página. El botón de eliminación cancela la venta para preservar la trazabilidad y reponer el stock mediante los triggers del modelo.

## Conectar el servidor MCP

Configuración de ejemplo para un cliente MCP:

```json
{
  "mcpServers": {
    "nexo-bi": {
      "command": "python",
      "args": ["D:\\Practicas R\\Proyecto final Negocios\\mcp_server.py"]
    }
  }
}
```

Herramientas expuestas:

- `consultar_indicadores`: devuelve KPIs, tendencias y desgloses con filtros opcionales.
- `registrar_venta`: inserta una transacción en la misma base usada por la web.
- `analizar_planteamiento`: interpreta un planteamiento y elige entre producto, categoría, región, canal, vendedor, tendencia o indicadores globales.

## Demostración sugerida

1. Mostrar el resumen y recorrer las siete vistas.
2. Aplicar un filtro regional.
3. Registrar una venta de importe visible.
4. Comprobar el cambio inmediato en ingresos, utilidad y ranking.
5. Abrir “Análisis adaptable MCP” y probar varios planteamientos.
6. Desde un cliente MCP, llamar `consultar_indicadores`, después `registrar_venta` y volver a consultar.
