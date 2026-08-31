# Tableau — RopaVacana

Integración de Tableau con Nexo BI. Documento independiente del `README.md` principal
(que cubre Docker, Power BI y MCP); esta carpeta cubre únicamente la parte de Tableau.

Requisito vigente del ingeniero: no basta una gráfica suelta por objetivo. **Cada uno
de los 7 objetivos es un dashboard completo**, con mínimo 4-5 gráficas que respondan
su pregunta de negocio y mínimo 4-5 métricas/KPIs visibles como tarjetas.

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
5. Cada **dashboard** (no cada hoja suelta) se construye con una **Conexión SQL
   personalizada** por objetivo, pegando la consulta correspondiente de
   [`queries.sql`](./queries.sql) **sin el `;` final** — Tableau envuelve la consulta
   internamente y el punto y coma rompe esa envoltura. Un origen de datos por objetivo,
   luego varias hojas (una por gráfica) que comparten ese mismo origen, combinadas en
   un Dashboard.

## Objetivos y estado de publicación

| # | Objetivo | Pregunta de negocio | Estado |
|---|----------|----------------------|--------|
| 1 | Ventas | Evolución mensual y fin de semana vs. laborable, por canal | Próxima iteración |
| 2 | Inventario | Qué tallas se agotan más rápido por categoría | Próxima iteración |
| 3 | Canal | Gasto promedio por canal y categoría | Próxima iteración |
| 4 | Productos | Personalizado vs. estándar, ganancia por categoría | Próxima iteración |
| 5 | Clientes | Rentabilidad por segmento, edad y género | Próxima iteración |
| 6 | Promociones | Rentabilidad de promociones aplicadas | Próxima iteración |
| 7 | Región | Costa/Sierra/Oriente, ingresos y categorías por región | **Publicado (solo mapa — ampliar a dashboard completo, ver abajo)** |

El objetivo 7 (antes numerado como "objetivo 4 · mapa de provincia" en la iteración
anterior) es el único publicado hasta ahora, y solo cubre 1 de las 5 gráficas mínimas
requeridas. Ver la sección siguiente para ampliarlo.

## Cómo ampliar el dashboard de Región (objetivo 7) — ya publicado

El mapa actual usa una query vieja de una sola dimensión (`provincia`). La nueva query
del objetivo 7 en `queries.sql` agrega `region` (Costa/Sierra/Oriente) y
`nombre_categoria`, para poder construir el dashboard completo:

1. En el workbook ya publicado, editar el origen de datos: reemplazar la Conexión SQL
   personalizada actual por la query nueva del **Objetivo 7** (con `region` y
   `nombre_categoria`).
2. El mapa que ya existe se mantiene igual (campo `provincia`, geocodificado
   automáticamente), pero ahora puede colorear/filtrar por `region`.
3. Agregar 4 hojas más al mismo dashboard, usando el mismo origen de datos:
   - Barras: `region` (Costa/Sierra/Oriente) × `ingresos_totales` — comparación macro.
   - Barras apiladas: `provincia` × `ingresos_totales`, color por `nombre_categoria`.
   - Ranking (barras horizontales) top 10 `provincia` por `ingresos_totales`.
   - Treemap jerárquico: `region` → `provincia` por `ingresos_totales`.
4. Tarjetas KPI (mínimo 4-5), como hojas de texto grande sobre el mismo origen sin
   desglosar por dimensión: `ingresos_totales` (SUM), `ticket_promedio` (promedio
   ponderado), `num_ventas` (SUM), región líder (usar un cálculo `INDEX()`/`RANK` o
   simplemente leer la barra más alta), categoría líder global.
5. Volver a publicar (Servidor → Guardar en Tableau Public) y actualizar
   `TABLEAU_EMBED_URL_REGION` en `.env` con el nuevo enlace si cambia.

## Los otros 6 objetivos — queries listas, dashboard pendiente de construir

Cada bloque de abajo resume qué construir en Tableau Desktop con la query ya
verificada de `queries.sql`. Un origen de datos (Custom SQL) por objetivo, luego una
hoja por gráfica, combinadas en un Dashboard, publicadas a Tableau Public, y el link
puesto en la variable de entorno indicada.

### Objetivo 1 — Ventas (`TABLEAU_EMBED_URL_VENTAS`)
- **KPIs:** ingresos totales, nº de ventas, ticket promedio, % ventas en fin de
  semana, canal líder.
- **Gráficas:** línea de evolución mensual de ingresos · barras fin de semana vs.
  laborable por canal · barras ranking de canales por ingresos · líneas por canal a
  través del tiempo · tabla cruzada mes × tipo de día con ticket promedio.

### Objetivo 2 — Inventario (`TABLEAU_EMBED_URL_INVENTARIO`)
- **KPIs:** unidades disponibles, % de tallas en riesgo, margen de stock promedio,
  categoría con más riesgo, unidades vendidas totales.
- **Gráficas:** barras de margen de stock por talla (color Riesgo/OK) · barras de
  stock disponible por categoría · tabla cruzada categoría × talla con semáforo ·
  dispersión unidades vendidas vs. margen de stock · ranking top 10 tallas con menor
  margen.

### Objetivo 3 — Canal (`TABLEAU_EMBED_URL_CANAL`)
- **KPIs:** ingresos totales, gasto promedio por cliente, canal líder, categoría más
  rentable por canal, nº de ventas totales.
- **Gráficas:** barras agrupadas canal × ingresos por categoría · mapa de calor canal
  × categoría (gasto promedio) · barras ranking de canales por gasto promedio ·
  treemap de categorías dentro de cada canal · tabla detalle canal × categoría.

### Objetivo 4 — Productos (`TABLEAU_EMBED_URL_PRODUCTOS`)
- **KPIs:** ganancia estimada total, % personalizado vs. estándar, ganancia
  promedio, nº de pedidos totales, categoría más rentable.
- **Gráficas:** barras apiladas ingresos por categoría (personalizado/estándar) ·
  barras ganancia estimada por categoría · dona de participación personalizado vs.
  estándar · barras ganancia promedio por categoría · tabla detalle categoría × tipo
  de producto.

### Objetivo 5 — Clientes (`TABLEAU_EMBED_URL_CLIENTES`)
- **KPIs:** ingresos totales, ticket promedio global, edad promedio, segmento más
  rentable, género con más ingresos.
- **Gráficas:** barras segmento × ingresos (color por género) · barras categoría ×
  ingresos por segmento · dispersión edad promedio vs. ingresos (tamaño = nº de
  compras) · barras ticket promedio por género · mapa de calor segmento × categoría.

### Objetivo 6 — Promociones (`TABLEAU_EMBED_URL_PROMOCIONES`)
- **KPIs:** ingresos con promoción, ganancia neta total, ticket promedio con promo,
  nº de ventas con promo, promoción más rentable.
- **Gráficas:** barras ranking de promociones por ganancia neta · barras ingresos por
  promoción (color tipo de descuento) · barras ganancia neta por tipo de descuento ·
  dispersión nº de ventas vs. ganancia neta por promo · tabla detalle de promociones.

## Publicar y embeber en Nexo BI

1. Construir el dashboard completo del objetivo en Tableau (todas las hojas listadas
   arriba, combinadas en un Dashboard, no hojas sueltas).
2. Publicar en **Tableau Public** (Servidor → Guardar en Tableau Public) o en Tableau
   Server/Cloud si se dispone de licencia.
3. Copiar el enlace de embebido (`Compartir → Insertar código` en Tableau Public, o el
   link directo de la vista).
4. Definir la variable de entorno específica de ese objetivo (ver cada sección arriba)
   antes de levantar Docker:

   ```bash
   # en .env
   TABLEAU_EMBED_URL_VENTAS=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_INVENTARIO=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_CANAL=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_PRODUCTOS=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_CLIENTES=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_PROMOCIONES=https://public.tableau.com/views/...
   TABLEAU_EMBED_URL_REGION=https://public.tableau.com/views/...
   ```

5. `docker compose up -d --build`. En el sidebar de Nexo BI, cada objetivo de Tableau
   es un ítem independiente; al seleccionarlo, la app llama a `GET /api/integraciones`,
   busca ese objetivo en `tableau.objetivos` y carga su `embed_url` en el iframe. Sin
   esa variable definida, muestra el estado vacío en vez de un iframe roto.

Se puede ir publicando de a un objetivo por vez: cada variable de entorno es
independiente, así que no hace falta terminar los 7 para ver los que ya estén listos.

## Notas de verificación

Las 7 consultas de `queries.sql` (más la de resumen ejecutivo, opcional) fueron
verificadas el 2026-08-30 contra el esquema real (`public`, base `RopaV`, vía
`docker exec ... psql`) y devuelven filas correctas. Se corrigieron 2 problemas reales
encontrados durante la verificación (detallados también como comentarios en
`queries.sql`):

1. `public.promociones` no tiene columna `tipo_promocion`; la columna real es
   `tipo_descuento`.
2. Los objetivos que unen `detalle_ventas` para desglosar por categoría (3, 5, 6, 7)
   sumaban `v.total_venta` o contaban `v.id_venta` sin `DISTINCT`. Como una venta con
   varias líneas aparece una vez por línea después del `JOIN`, eso duplicaba ingresos
   y conteos. Se corrigió sumando `dv.subtotal` (el importe de la línea, no de toda la
   venta) y usando `COUNT(DISTINCT v.id_venta)`.

Se recomienda volver a correr las queries una vez contra el contenedor activo antes de
cada avance de presentación, para confirmar que siguen devolviendo filas con los datos
actuales.
