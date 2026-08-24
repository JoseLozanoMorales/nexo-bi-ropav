-- =====================================================================
-- ETL DIMENSIONAL - RopaVacanaV2 -> dw
-- Ejecutar DESPUÉS de 01_ddl_dw_ropavacana.sql, sobre la misma BD que
-- contiene el esquema public restaurado desde RopaVacanaV2.sql.
-- Orden respetado por dependencias de FK (dimensiones "raíz" primero).
-- =====================================================================

BEGIN;

-- Vaciar en orden inverso a las dependencias (útil si se re-ejecuta el ETL)
TRUNCATE TABLE dw.fact_ventas;
TRUNCATE TABLE dw.dim_variante, dw.dim_admin, dw.dim_cliente,
               dw.dim_producto, dw.dim_promocion, dw.dim_metodo_pago,
               dw.dim_canal, dw.dim_talla, dw.dim_zona
    RESTART IDENTITY CASCADE;
TRUNCATE TABLE dw.dim_rol, dw.dim_categoria, dw.dim_proveedor,
               dw.dim_sistema_talla, dw.dim_color, dw.dim_ciudad
    RESTART IDENTITY CASCADE;
TRUNCATE TABLE dw.dim_provincia RESTART IDENTITY CASCADE;
TRUNCATE TABLE dw.dim_tiempo CASCADE;

-- ---------------------------------------------------------------------
-- 1) Geografía: provincia -> ciudad -> zona
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_provincia (id_provincia, nombre_provincia)
SELECT id_provincia, nombre
FROM public.provincia;

INSERT INTO dw.dim_ciudad (id_ciudad, nombre_ciudad, id_provincia)
SELECT id_ciudad, nombre, id_provincia
FROM public.ciudad;

INSERT INTO dw.dim_zona (id_zona, nombre_zona, costo_entrega, tiempo_entrega_min, id_ciudad)
SELECT id_zona, nombre, costo_entrega, tiempo_entrega_min, id_ciudad
FROM public.zona;

-- ---------------------------------------------------------------------
-- 2) Canal de venta
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_canal (id_canal, nombre_canal, costo_operativo, descripcion)
SELECT id_canal, nombre_canal, costo_operativo, descripcion
FROM public.canales_venta;

-- ---------------------------------------------------------------------
-- 3) Clientes (canal preferido denormalizado como texto)
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_cliente
    (id_cliente, nombre, edad, genero, tipo_cliente, frecuencia_compra,
     segmento_cliente, canal_preferido, id_zona)
SELECT c.id_cliente, c.nombre, c.edad, c.genero::text, c.tipo_cliente,
       c.frecuencia_compra, c.segmento_cliente, cv.nombre_canal, c.id_zona
FROM public.clientes c
LEFT JOIN public.canales_venta cv ON cv.id_canal = c.id_canal_preferido;

-- ---------------------------------------------------------------------
-- 4) Producto: categoría, proveedor -> producto
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_categoria (id_categoria, nombre_categoria)
SELECT id_categoria, nombre_categoria
FROM public.categorias;

INSERT INTO dw.dim_proveedor (id_proveedor, nombre, telefono, direccion)
SELECT id_proveedor, nombre, telefono, direccion
FROM public.proveedores;

INSERT INTO dw.dim_producto
    (id_producto, nombre_producto, precio_compra, precio_venta, margen_pct,
     margen_abs, estado_producto, fecha_ingreso, id_categoria, id_proveedor)
SELECT id_producto, nombre_producto, precio_compra, precio_venta, margen_pct,
       margen_abs, estado_producto::text, fecha_ingreso, id_categoria, id_proveedor
FROM public.productos;

-- ---------------------------------------------------------------------
-- 5) Variante: sistema_talla -> talla; color; producto -> variante
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_sistema_talla (id_sistema, nombre_sistema, descripcion)
SELECT id_sistema, nombre, descripcion
FROM public.sistemas_talla;

INSERT INTO dw.dim_talla (id_talla, etiqueta, orden, id_sistema)
SELECT id_talla, etiqueta, orden, id_sistema
FROM public.tallas;

INSERT INTO dw.dim_color (id_color, nombre_color, hex, es_compuesto)
SELECT id_color, nombre, hex, es_compuesto
FROM public.colores;

INSERT INTO dw.dim_variante
    (id_variante, sku, activo, tiempo_produccion_dias, color_secundario,
     id_producto, id_talla, id_color_principal)
SELECT vp.id_variante, vp.sku, vp.activo, vp.tiempo_produccion_dias,
       col_sec.nombre, vp.id_producto, vp.id_talla, vp.id_color_principal
FROM public.variantes_producto vp
LEFT JOIN public.colores col_sec ON col_sec.id_color = vp.id_color_secundario;

-- ---------------------------------------------------------------------
-- 6) Método de pago
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_metodo_pago (id_metodo_pago, nombre, activo)
SELECT id_metodo_pago, nombre, activo
FROM public.metodo_pago;

-- ---------------------------------------------------------------------
-- 7) Promoción (+ fila -1 "Sin promoción" para ventas sin promo aplicada)
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_promocion
    (id_promocion, nombre_promocion, tipo_descuento, porcentaje_descuento,
     fecha_inicio, fecha_fin)
VALUES (-1, 'Sin promoción', NULL, NULL, NULL, NULL);

INSERT INTO dw.dim_promocion
    (id_promocion, nombre_promocion, tipo_descuento, porcentaje_descuento,
     fecha_inicio, fecha_fin)
SELECT id_promocion, COALESCE(nombre_promocion, 'Sin nombre'), tipo_descuento,
       porcentaje_descuento, fecha_inicio, fecha_fin
FROM public.promociones;

-- ---------------------------------------------------------------------
-- 8) Vendedor / administrador (rol -> admin)
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_rol (id_rol, nombre_rol)
SELECT id_rol, nombre
FROM public.roles;

INSERT INTO dw.dim_admin (id_admin, nombre, cargo, id_rol)
SELECT id_admin, nombre, cargo, id_rol
FROM public.administradores;

-- ---------------------------------------------------------------------
-- 9) Dimensión tiempo: spine diario cubriendo el rango real de ventas
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_tiempo
    (fk_tiempo, fecha, anio, mes, nombre_mes, trimestre, dia, dia_semana,
     nombre_dia, semana_anio, es_fin_semana)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::int,
    d::date,
    EXTRACT(YEAR FROM d)::smallint,
    EXTRACT(MONTH FROM d)::smallint,
    TRIM(TO_CHAR(d, 'TMMonth')),
    EXTRACT(QUARTER FROM d)::smallint,
    EXTRACT(DAY FROM d)::smallint,
    EXTRACT(DOW FROM d)::smallint,
    TRIM(TO_CHAR(d, 'TMDay')),
    EXTRACT(WEEK FROM d)::smallint,
    EXTRACT(DOW FROM d) IN (0, 6)
FROM generate_series(
        (SELECT MIN(fecha_venta)::date FROM public.ventas),
        (SELECT MAX(fecha_venta)::date FROM public.ventas),
        interval '1 day'
     ) AS d;

-- ---------------------------------------------------------------------
-- 10) Tabla de hechos: fact_ventas (grano = detalle_venta)
-- ---------------------------------------------------------------------
INSERT INTO dw.fact_ventas
    (id_detalle, id_venta, fk_tiempo, fk_cliente, fk_variante, fk_canal,
     fk_metodo_pago, fk_promocion, fk_admin, estado_venta, cantidad,
     precio_unitario, subtotal, costo_unitario, costo_total, margen_total,
     es_personalizado)
SELECT
    dv.id_detalle,
    dv.id_venta,
    TO_CHAR(v.fecha_venta, 'YYYYMMDD')::int,
    v.id_cliente,
    dv.id_variante,
    v.id_canal,
    v.id_metodo_pago,
    COALESCE(v.id_promocion, -1),
    v.id_admin,
    v.estado_venta::text,
    dv.cantidad,
    dv.precio_unitario,
    dv.subtotal,
    COALESCE(vp.precio_compra_override, p.precio_compra)                         AS costo_unitario,
    COALESCE(vp.precio_compra_override, p.precio_compra) * dv.cantidad           AS costo_total,
    dv.subtotal - (COALESCE(vp.precio_compra_override, p.precio_compra) * dv.cantidad) AS margen_total,
    dv.es_personalizado
FROM public.detalle_ventas dv
JOIN public.ventas v             ON v.id_venta = dv.id_venta
JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
JOIN public.productos p          ON p.id_producto = vp.id_producto;

COMMIT;

-- ---------------------------------------------------------------------
-- Verificación rápida de conteos
-- ---------------------------------------------------------------------
SELECT 'fact_ventas' AS tabla, COUNT(*) FROM dw.fact_ventas
UNION ALL SELECT 'dim_cliente', COUNT(*) FROM dw.dim_cliente
UNION ALL SELECT 'dim_variante', COUNT(*) FROM dw.dim_variante
UNION ALL SELECT 'dim_producto', COUNT(*) FROM dw.dim_producto
UNION ALL SELECT 'dim_tiempo', COUNT(*) FROM dw.dim_tiempo;
