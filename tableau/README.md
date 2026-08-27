# Tableau — RopaVacana

Integración de Tableau con Nexo BI. Documento independiente del `README.md` principal
(que cubre Docker, Power BI y MCP); esta carpeta cubre únicamente la parte de Tableau.

## Conexión Tableau → PostgreSQL

Tableau se conecta en vivo al mismo contenedor `db` que ya usa Power BI, sin cambios de
infraestructura: `compose.yaml` ya expone el puerto de Postgres al host (`5433:5432`).

1. `docker compose up --build` (si no está corriendo).
2. En Tableau Desktop (o Tableau Public con una copia local de Postgres): **Conectar → PostgreSQL**.
3. Datos de conexión:
   - Servidor: `localhost` (o `127.0.0.1`)
   - Puerto: `5433`
   - Base de datos: `RopaV`
   - Usuario: `postgres`
   - Contraseña: la de `POSTGRES_PASSWORD` en `.env` (por defecto `prototipo_local`)
4. Esquema: `public`. A diferencia de Power BI (que lee el esquema dimensional `dw` vía
   DirectQuery y requiere el botón "Sincronizar"), Tableau consulta directamente las
   tablas transaccionales: una venta nueva aparece sin ningún paso intermedio.
5. Cada hoja se construye con **Conexión SQL personalizada**, pegando la consulta
   correspondiente de [`queries.sql`](./queries.sql).

## Objetivos y estado de publicación

| # | Objetivo | Query | Estado |
|---|----------|-------|--------|
| 1 | Tendencia de ventas en el tiempo | Objetivo 1 | Próxima iteración |
| 2 | Desempeño de ventas por canal | Objetivo 2 | Próxima iteración |
| 3 | Categorías/productos con mayor y menor rotación | Objetivo 3 | Próxima iteración |
| 4 | Distribución geográfica de ventas por provincia (mapa) | Objetivo 4 | **Publicado** |
| 5 | Segmentación de clientes por frecuencia/recencia/valor | Objetivo 5 | Próxima iteración |
| 6 | Nivel de inventario y riesgo de quiebre de stock | Objetivo 6 | Próxima iteración |
| 7 | Cumplimiento de entregas | Objetivo 7 | Próxima iteración |
| 8 | Resumen ejecutivo (KPIs globales: ingresos, utilidad, margen, transacciones, unidades, clientes) | Objetivo 8 | Próxima iteración |

Para el avance de hoy se priorizó el **objetivo 4** (mapa de provincia) por ser el
punto fuerte de Tableau frente a los gráficos de barras estándar del resto del panel.

El **objetivo 8** cubre el objetivo 1 del `README.md` principal (resumen de ingresos,
utilidad, margen, transacciones, unidades y clientes), que no tenía una hoja propia
en la tabla original de Tableau. Se recomienda armarlo como una hoja de tarjetas KPI
("Texto grande" / Big Number en Tableau), una tarjeta por medida, en vez de un gráfico
de barras — es la hoja de portada del dashboard.

## Publicar y embeber en Nexo BI

1. En Tableau, construir la hoja con la query del objetivo (usar el mapa de símbolos o
   relleno por `provincia` para el objetivo 4; Tableau geocodifica el nombre de
   provincia automáticamente si coincide con su base geográfica).
2. Publicar en **Tableau Public** (Servidor → Guardar en Tableau Public) o en Tableau
   Server/Cloud si se dispone de licencia.
3. Copiar el enlace de embebido (`Compartir → Insertar código` en Tableau Public, o el
   link directo de la vista).
4. Definir la variable de entorno `TABLEAU_EMBED_URL` con ese enlace antes de levantar
   Docker (mismo mecanismo que `POWER_BI_EMBED_URL`):

   ```bash
   # en .env
   TABLEAU_EMBED_URL=https://public.tableau.com/views/...
   ```

5. `docker compose up -d --build`. La pestaña **Tableau** de Nexo BI llama a
   `GET /api/integraciones`, lee `tableau.embed_url` y lo carga en el iframe — el mismo
   flujo que ya usa la pestaña de Power BI.

Sin esa variable definida, la pestaña muestra el estado vacío ("Configura el reporte de
Tableau") en vez de un iframe roto.

## Notas de verificación

Las 7 consultas de `queries.sql` fueron verificadas contra el esquema real (`public`) y
no requirieron reescritura. Se recomienda correrlas una vez contra el contenedor activo
(`docker compose up`) antes de la presentación, para confirmar que devuelven filas con
los datos actuales del backup restaurado.
