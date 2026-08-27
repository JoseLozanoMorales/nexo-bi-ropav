-- Fuentes de datos SQL personalizadas para Tableau, una por objetivo.
-- Esquema: public (conexión en vivo, PostgreSQL, base RopaV).
-- Cada bloque corresponde a una hoja/dashboard publicado en Tableau.

-- =====================================================================
-- Objetivo 1: Tendencia de ventas en el tiempo
-- =====================================================================
SELECT DATE_TRUNC('month', fecha_venta)::date AS mes, COUNT(*) AS num_ventas,
SUM(total_venta) AS ingresos_totales FROM public.ventas
WHERE estado_venta = 'Completada' GROUP BY 1 ORDER BY 1;

-- =====================================================================
-- Objetivo 2: Desempeño de ventas por canal (online vs. física)
-- =====================================================================
SELECT c.nombre_canal, COUNT(v.id_venta) AS num_ventas, SUM(v.total_venta) AS
ingresos_totales, ROUND(AVG(v.total_venta), 2) AS ticket_promedio
FROM public.ventas v JOIN public.canales_venta c ON c.id_canal = v.id_canal
WHERE v.estado_venta = 'Completada' GROUP BY c.nombre_canal ORDER BY ingresos_totales DESC;

-- =====================================================================
-- Objetivo 3: Categorías/productos con mayor y menor rotación
-- =====================================================================
SELECT cat.nombre_categoria, p.nombre_producto, SUM(dv.cantidad) AS unidades_vendidas,
SUM(dv.subtotal) AS ingresos_generados FROM public.detalle_ventas dv
JOIN public.ventas v ON v.id_venta = dv.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
WHERE v.estado_venta = 'Completada'
GROUP BY cat.nombre_categoria, p.nombre_producto ORDER BY unidades_vendidas DESC;

-- =====================================================================
-- Objetivo 4: Distribución geográfica de ventas por provincia (mapa)
-- =====================================================================
SELECT prov.nombre AS provincia, COUNT(v.id_venta) AS num_ventas,
SUM(v.total_venta) AS ingresos_totales FROM public.ventas v
JOIN public.clientes cl ON cl.id_cliente = v.id_cliente
JOIN public.direcciones d ON d.id_cliente = cl.id_cliente AND d.es_principal = true
JOIN public.zona z ON z.id_zona = d.id_zona
JOIN public.ciudad ciu ON ciu.id_ciudad = z.id_ciudad
JOIN public.provincia prov ON prov.id_provincia = ciu.id_provincia
WHERE v.estado_venta = 'Completada' GROUP BY prov.nombre ORDER BY ingresos_totales DESC;

-- =====================================================================
-- Objetivo 5: Segmentación de clientes (frecuencia, recencia, valor)
-- =====================================================================
SELECT cl.id_cliente, cl.nombre, cl.segmento_cliente, cl.frecuencia_compra,
COUNT(v.id_venta) AS num_compras, SUM(v.total_venta) AS valor_total,
MAX(v.fecha_venta) AS ultima_compra FROM public.clientes cl
JOIN public.ventas v ON v.id_cliente = cl.id_cliente AND v.estado_venta = 'Completada'
GROUP BY cl.id_cliente, cl.nombre, cl.segmento_cliente, cl.frecuencia_compra
ORDER BY valor_total DESC;

-- =====================================================================
-- Objetivo 6: Nivel de inventario y riesgo de quiebre de stock
-- =====================================================================
SELECT cat.nombre_categoria, p.nombre_producto, vp.sku, i.cantidad_disponible,
i.cantidad_minima, (i.cantidad_disponible - i.cantidad_minima) AS margen_stock,
CASE WHEN i.cantidad_disponible <= i.cantidad_minima THEN 'Riesgo' ELSE 'OK' END AS
estado_stock FROM public.inventario i
JOIN public.variantes_producto vp ON vp.id_variante = i.id_variante
JOIN public.productos p ON p.id_producto = vp.id_producto
JOIN public.categorias cat ON cat.id_categoria = p.id_categoria
ORDER BY margen_stock ASC;

-- =====================================================================
-- Objetivo 7: Cumplimiento de entregas
-- =====================================================================
SELECT e.tipo_entrega, e.estado_entrega, z.nombre AS zona, COUNT(*) AS num_entregas
FROM public.entregas e JOIN public.zona z ON z.id_zona = e.id_zona
GROUP BY e.tipo_entrega, e.estado_entrega, z.nombre ORDER BY zona, e.tipo_entrega;

-- =====================================================================
-- Objetivo 8: Resumen ejecutivo (KPIs globales)
-- Cubre el objetivo 1 del README principal (ingresos, utilidad, margen,
-- transacciones, unidades, clientes). Misma fórmula de utilidad/margen
-- que usa la app en db.py, para que los números coincidan con el resto
-- del panel. Devuelve una sola fila: en Tableau se usa como tarjetas KPI
-- (Texto grande / "Big Number"), una por medida.
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
