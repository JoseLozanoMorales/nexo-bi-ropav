-- Fuentes de datos SQL personalizadas para Tableau, una por objetivo.
-- Esquema: public (conexión en vivo, PostgreSQL, base RopaV).
-- Cada bloque alimenta UN dashboard completo (mínimo 4-5 gráficas y 4-5
-- tarjetas KPI), no una sola gráfica suelta. Pegar cada query, SIN el ';'
-- final, en una "Conexión SQL personalizada" distinta dentro de Tableau.
--
-- Verificado contra el esquema real de RopaV (2026-08-30). Se corrigieron
-- 2 clases de error frente a la versión entregada por el ingeniero:
--   1) public.promociones no tiene columna "tipo_promocion" -> es
--      "tipo_descuento".
--   2) Varias queries unían detalle_ventas (una fila por línea de venta)
--      y luego sumaban/contaban v.total_venta o v.id_venta directamente.
--      Si una venta tiene más de una línea, eso duplica el total de esa
--      venta tantas veces como líneas tenga (fan-out). Se corrigió usando
--      SUM(dv.subtotal) en vez de SUM(v.total_venta), y COUNT(DISTINCT
--      v.id_venta) en vez de COUNT(v.id_venta), en los objetivos 3 y 5.
--
-- Se documentan 5 objetivos (Ventas, Inventario, Canal, Productos, Región),
-- que cubren el minimo exigido. Se descartaron los objetivos de Clientes y
-- Promociones que se habian planteado inicialmente.

-- =====================================================================
-- Objetivo 1 — VENTAS: fin de semana vs. laboral y evolución mensual
-- Pregunta de negocio: ¿cómo evolucionan las ventas mes a mes y qué
-- diferencia hay entre días laborables y fines de semana, por canal?
-- =====================================================================
SELECT
    DATE_TRUNC('month', fecha_venta)::date AS mes,
    CASE WHEN EXTRACT(ISODOW FROM fecha_venta) IN (6,7) THEN 'Fin de semana' ELSE 'Laborable' END AS tipo_dia,
    c.nombre_canal,
    COUNT(v.id_venta) AS num_ventas,
    SUM(v.total_venta) AS ingresos_totales,
    ROUND(AVG(v.total_venta), 2) AS ticket_promedio
FROM public.ventas v
JOIN public.canales_venta c ON c.id_canal = v.id_canal
WHERE v.estado_venta = 'Completada'
GROUP BY 1, 2, 3
ORDER BY 1;

-- =====================================================================
-- Objetivo 2 — INVENTARIO: tallas que se agotan más rápido por categoría
-- Pregunta de negocio: ¿qué tallas, dentro de cada categoría, están más
-- cerca de quedarse sin stock?
-- =====================================================================
SELECT
    cat.nombre_categoria,
    t.etiqueta AS talla,
    i.cantidad_disponible,
    i.cantidad_minima,
    (i.cantidad_disponible - i.cantidad_minima) AS margen_stock,
    CASE WHEN i.cantidad_disponible <= i.cantidad_minima THEN 'Riesgo' ELSE 'OK' END AS estado_stock,
    COALESCE(SUM(dv.cantidad), 0) AS unidades_vendidas
FROM public.inventario i
JOIN public.variantes_producto vp ON vp.id_variante = i.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
JOIN public.tallas t ON t.id_talla = vp.id_talla
LEFT JOIN public.detalle_ventas dv ON dv.id_variante = vp.id_variante
GROUP BY cat.nombre_categoria, t.etiqueta, i.cantidad_disponible, i.cantidad_minima
ORDER BY margen_stock ASC;

-- =====================================================================
-- Objetivo 3 — CANAL: gasto promedio por canal y categoría
-- Pregunta de negocio: ¿qué canal genera mayor gasto promedio por
-- cliente y en qué categorías?
-- Corrección: gasto_promedio_cliente usa SUM(dv.subtotal), no
-- SUM(v.total_venta) -- este último se duplicaba por el fan-out del
-- JOIN a detalle_ventas cuando una venta tiene varias líneas.
-- =====================================================================
SELECT
    c.nombre_canal,
    cat.nombre_categoria,
    COUNT(DISTINCT v.id_venta) AS num_ventas,
    SUM(dv.subtotal) AS ingresos,
    ROUND(AVG(dv.subtotal), 2) AS gasto_promedio_categoria,
    ROUND(SUM(dv.subtotal) / NULLIF(COUNT(DISTINCT v.id_cliente), 0), 2) AS gasto_promedio_cliente
FROM public.ventas v
JOIN public.canales_venta c ON c.id_canal = v.id_canal
JOIN public.detalle_ventas dv ON dv.id_venta = v.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
WHERE v.estado_venta = 'Completada'
GROUP BY c.nombre_canal, cat.nombre_categoria
ORDER BY ingresos DESC;

-- =====================================================================
-- Objetivo 4 — PRODUCTOS: personalizado vs. estándar, ganancia por categoría
-- Pregunta de negocio: ¿los productos personalizados dejan más ganancia
-- que los estándar, y en qué categorías?
-- =====================================================================
SELECT
    cat.nombre_categoria,
    CASE WHEN dv.es_personalizado THEN 'Personalizado' ELSE 'Estándar' END AS tipo_producto,
    COUNT(dv.id_detalle) AS num_pedidos,
    SUM(dv.subtotal) AS ingresos,
    SUM(dv.subtotal - (p.precio_compra * dv.cantidad)) AS ganancia_estimada,
    ROUND(AVG(dv.subtotal - (p.precio_compra * dv.cantidad)), 2) AS ganancia_promedio
FROM public.detalle_ventas dv
JOIN public.ventas v ON v.id_venta = dv.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
WHERE v.estado_venta = 'Completada'
GROUP BY cat.nombre_categoria, dv.es_personalizado
ORDER BY ganancia_estimada DESC;

-- =====================================================================
-- Objetivo 5 — REGIÓN: Costa, Sierra y Oriente
-- Pregunta de negocio: ¿qué región y provincia generan más ingresos, y
-- con qué mezcla de categorías?
-- Corrección: mismo fan-out que el objetivo 3 -- num_ventas,
-- ingresos_totales y ticket_promedio ahora usan DISTINCT/dv.subtotal.
-- =====================================================================
SELECT
    CASE
        WHEN prov.nombre IN ('Esmeraldas','Manabí','Santo Domingo de los Tsáchilas','Guayas','Santa Elena','Los Ríos','El Oro') THEN 'Costa'
        WHEN prov.nombre IN ('Pichincha','Imbabura','Carchi','Cotopaxi','Tungurahua','Chimborazo','Bolívar','Cañar','Azuay','Loja') THEN 'Sierra'
        WHEN prov.nombre IN ('Sucumbíos','Napo','Orellana','Pastaza','Morona Santiago','Zamora Chinchipe') THEN 'Oriente'
        ELSE 'Otro'
    END AS region,
    prov.nombre AS provincia,
    cat.nombre_categoria,
    COUNT(DISTINCT v.id_venta) AS num_ventas,
    SUM(dv.subtotal) AS ingresos_totales,
    ROUND(SUM(dv.subtotal) / NULLIF(COUNT(DISTINCT v.id_venta), 0), 2) AS ticket_promedio
FROM public.ventas v
JOIN public.clientes cl ON cl.id_cliente = v.id_cliente
JOIN public.direcciones d ON d.id_cliente = cl.id_cliente AND d.es_principal = true
JOIN public.zona z ON z.id_zona = d.id_zona
JOIN public.ciudad ciu ON ciu.id_ciudad = z.id_ciudad
JOIN public.provincia prov ON prov.id_provincia = ciu.id_provincia
JOIN public.detalle_ventas dv ON dv.id_venta = v.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
WHERE v.estado_venta = 'Completada'
GROUP BY region, prov.nombre, cat.nombre_categoria
ORDER BY ingresos_totales DESC;

-- =====================================================================
-- Extra (opcional) — Resumen ejecutivo global (KPIs de portada)
-- No es uno de los 7 objetivos exigidos; útil como hoja de portada del
-- workbook completo, con tarjetas KPI que resumen todo el negocio.
-- =====================================================================
SELECT COUNT(DISTINCT v.id_venta) AS transacciones, COUNT(DISTINCT v.id_cliente) AS clientes,
SUM(dv.cantidad) AS unidades_vendidas, SUM(dv.subtotal) AS ingresos_totales,
SUM(dv.cantidad * (dv.precio_unitario - COALESCE(vp.precio_compra_override, p.precio_compra)))
AS utilidad_total, ROUND(SUM(dv.cantidad * (dv.precio_unitario -
COALESCE(vp.precio_compra_override, p.precio_compra))) / NULLIF(SUM(dv.subtotal), 0) * 100, 2)
AS margen_pct FROM public.ventas v JOIN public.detalle_ventas dv ON dv.id_venta = v.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
WHERE v.estado_venta = 'Completada';
