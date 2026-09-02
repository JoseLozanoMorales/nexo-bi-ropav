# Tableau — RopaVacana

Integración de Tableau con Nexo BI. Documento independiente del `README.md` principal
(que cubre Docker, Power BI y MCP); esta carpeta cubre únicamente la parte de Tableau.

Requisito vigente del ingeniero: no basta una gráfica suelta por objetivo. **Cada uno
de los 5 objetivos es un dashboard completo**, con mínimo 4-5 gráficas que respondan
su pregunta de negocio y mínimo 4-5 métricas/KPIs visibles como tarjetas.

Se descartaron los objetivos de Clientes y Promociones planteados en una iteración
anterior (quedaron documentados en el historial de git si hace falta retomarlos); 5
objetivos cubren de sobra el mínimo exigido por la consigna.

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
   tablas transaccionales: una venta nueva aparece sin ningún paso intermedio en
   Desktop. **Para publicar en Tableau Public hay que convertir la conexión a
   Extracto** (Public no puede alcanzar un Postgres local desde internet), así que el
   dashboard publicado es una foto de los datos al momento de extraer, no en vivo.
5. Cada **dashboard** (no cada hoja suelta) se construye con una **Conexión SQL
   personalizada** por objetivo, pegando la consulta correspondiente de
   [`queries.sql`](./queries.sql) **sin el `;` final** — Tableau envuelve la consulta
   internamente y el punto y coma rompe esa envoltura. Un origen de datos por objetivo,
   luego varias hojas (una por gráfica) que comparten ese mismo origen, combinadas en
   un Dashboard.

## Objetivos y estado de publicación

| # | Objetivo | Pregunta de negocio | Variable de entorno | Estado |
|---|----------|----------------------|----------------------|--------|
| 1 | Ventas | Evolución mensual y fin de semana vs. laborable, por canal | `TABLEAU_EMBED_URL_VENTAS` | **Publicado** |
| 2 | Inventario | Qué tallas se agotan más rápido por categoría | `TABLEAU_EMBED_URL_INVENTARIO` | **Publicado** |
| 3 | Canal | Gasto promedio por canal y categoría | `TABLEAU_EMBED_URL_CANAL` | **Publicado** |
| 4 | Productos | Personalizado vs. estándar, ganancia por categoría | `TABLEAU_EMBED_URL_PRODUCTOS` | **Publicado** |
| 5 | Región | Costa/Sierra/Oriente, ingresos y categorías por región | `TABLEAU_EMBED_URL_REGION` | **Publicado** (mapa + 4 gráficas adicionales + KPIs) |

Los 5 objetivos ya están publicados en Tableau Public y embebidos en el sidebar de
Nexo BI (cada uno es un ítem independiente y seleccionable).

## KPIs y gráficas de cada dashboard

### Objetivo 1 — Ventas
- **KPIs:** ingresos totales, nº de ventas, ticket promedio, % ventas en fin de
  semana, canal líder.
- **Gráficas:** línea de evolución mensual de ingresos · barras fin de semana vs.
  laborable por canal · barras ranking de canales por ingresos · líneas por canal a
  través del tiempo · tabla cruzada mes × tipo de día con ticket promedio.

### Objetivo 2 — Inventario
- **KPIs:** unidades disponibles, % de tallas en riesgo, margen de stock promedio,
  categoría con más riesgo, unidades vendidas totales.
- **Gráficas:** barras de margen de stock por talla (color Riesgo/OK) · barras de
  stock disponible por categoría · tabla cruzada categoría × talla con semáforo ·
  dispersión unidades vendidas vs. margen de stock · ranking top 10 tallas con menor
  margen.

### Objetivo 3 — Canal
- **KPIs:** ingresos totales, gasto promedio por cliente, canal líder, categoría más
  rentable por canal, nº de ventas totales.
- **Gráficas:** barras agrupadas canal × ingresos por categoría · mapa de calor canal
  × categoría (gasto promedio) · barras ranking de canales por gasto promedio ·
  treemap de categorías dentro de cada canal · tabla detalle canal × categoría.

### Objetivo 4 — Productos
- **KPIs:** ganancia estimada total, % personalizado vs. estándar, ganancia
  promedio, nº de pedidos totales, categoría más rentable.
- **Gráficas:** barras apiladas ingresos por categoría (personalizado/estándar) ·
  barras ganancia estimada por categoría · circular de participación personalizado
  vs. estándar · barras ganancia promedio por categoría · tabla detalle categoría ×
  tipo de producto.

### Objetivo 5 — Región
- **KPIs:** ingresos totales, ticket promedio, nº de ventas, región líder, categoría
  líder.
- **Gráficas:** mapa por provincia (coloreado por región) · barras Costa/Sierra/Oriente
  por ingresos · barras apiladas provincia × categoría · ranking top 10 provincias ·
  treemap jerárquico región → provincia.

## Publicar y embeber en Nexo BI

1. Construir el dashboard completo del objetivo en Tableau (todas las hojas listadas
   arriba, combinadas en un Dashboard, no hojas sueltas). Tamaño recomendado: 1200×620
   (coincide con el alto fijo del iframe en la app).
2. Convertir el origen de datos a **Extracto** (Datos → clic en la conexión → Extracto)
   antes de publicar — Tableau Public no admite conexión en vivo a un Postgres local.
3. Publicar en **Servidor → Tableau Public → Guardar en Tableau Public**.
4. Copiar el enlace directo de la vista (no el snippet JS completo del botón
   Compartir), y agregarle los mismos parámetros que ya usan los 5 dashboards
   publicados: `?:embed=y&:showVizHome=no&:toolbar=yes`.
5. Definir la variable de entorno específica de ese objetivo en `.env`:

   ```bash
   TABLEAU_EMBED_URL_VENTAS=https://public.tableau.com/views/.../Dashboard1?:embed=y&:showVizHome=no&:toolbar=yes
   TABLEAU_EMBED_URL_INVENTARIO=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_CANAL=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_PRODUCTOS=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_REGION=https://public.tableau.com/views/...
   ```

6. `docker compose up -d app` (no hace falta `--build` si solo cambió el `.env`, ya
   que las variables de entorno se inyectan al recrear el contenedor). En el sidebar de
   Nexo BI, cada objetivo de Tableau es un ítem independiente; al seleccionarlo, la app
   llama a `GET /api/integraciones`, busca ese objetivo en `tableau.objetivos` y carga
   su `embed_url` en el iframe. Sin esa variable definida, muestra el estado vacío en
   vez de un iframe roto.

## Notas de verificación

Las 5 consultas de `queries.sql` (más la de resumen ejecutivo, opcional) fueron
verificadas contra el esquema real (`public`, base `RopaV`, vía `docker exec ...
psql`) y devuelven filas correctas. Se corrigieron 2 problemas reales encontrados
durante la verificación (detallados también como comentarios en `queries.sql`):

1. `public.promociones` no tiene columna `tipo_promocion` (esto aplicaba al objetivo
   de Promociones, descartado; se deja la nota por si se retoma).
2. Los objetivos que unen `detalle_ventas` para desglosar por categoría (3 y 5)
   sumaban `v.total_venta` o contaban `v.id_venta` sin `DISTINCT`. Como una venta con
   varias líneas aparece una vez por línea después del `JOIN`, eso duplicaba ingresos
   y conteos. Se corrigió sumando `dv.subtotal` (el importe de la línea, no de toda la
   venta) y usando `COUNT(DISTINCT v.id_venta)`.

Se recomienda volver a correr las queries una vez contra el contenedor activo antes de
cada avance de presentación, para confirmar que siguen devolviendo filas con los datos
actuales.
