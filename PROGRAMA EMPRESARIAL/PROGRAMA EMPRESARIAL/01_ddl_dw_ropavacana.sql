-- =====================================================================
-- MODELO DIMENSIONAL (ESQUEMA COPO DE NIEVE) - RopaVacanaV2
-- Materia: Inteligencia de Negocios [20603]
-- Esquema destino: dw (Data Warehouse)
-- Fuente: esquema public (BD transaccional RopaVacanaV2)
-- =====================================================================
-- Proceso de negocio: VENTAS
-- Grano del hecho: una fila por línea de venta (detalle_venta), es decir,
--                   un producto/variante vendido dentro de una venta.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS dw;

-- =====================================================================
-- DIMENSIÓN TIEMPO
-- =====================================================================
CREATE TABLE dw.dim_tiempo (
    fk_tiempo        INTEGER PRIMARY KEY,        -- formato YYYYMMDD
    fecha             DATE NOT NULL,
    anio              SMALLINT NOT NULL,
    mes               SMALLINT NOT NULL,
    nombre_mes        VARCHAR(20) NOT NULL,
    trimestre         SMALLINT NOT NULL,
    dia               SMALLINT NOT NULL,
    dia_semana        SMALLINT NOT NULL,          -- 0=domingo ... 6=sábado
    nombre_dia        VARCHAR(20) NOT NULL,
    semana_anio       SMALLINT NOT NULL,
    es_fin_semana     BOOLEAN NOT NULL
);

-- =====================================================================
-- JERARQUÍA GEOGRÁFICA (copo de nieve): provincia -> ciudad -> zona
-- =====================================================================
CREATE TABLE dw.dim_provincia (
    id_provincia      INTEGER PRIMARY KEY,
    nombre_provincia  VARCHAR(100) NOT NULL
);

CREATE TABLE dw.dim_ciudad (
    id_ciudad         INTEGER PRIMARY KEY,
    nombre_ciudad     VARCHAR(100) NOT NULL,
    id_provincia      INTEGER NOT NULL REFERENCES dw.dim_provincia(id_provincia)
);

CREATE TABLE dw.dim_zona (
    id_zona            INTEGER PRIMARY KEY,
    nombre_zona        VARCHAR(100) NOT NULL,
    costo_entrega      NUMERIC(8,2),
    tiempo_entrega_min INTEGER,
    id_ciudad          INTEGER NOT NULL REFERENCES dw.dim_ciudad(id_ciudad)
);

-- =====================================================================
-- DIMENSIÓN CANAL DE VENTA
-- =====================================================================
CREATE TABLE dw.dim_canal (
    id_canal          INTEGER PRIMARY KEY,
    nombre_canal      VARCHAR(100) NOT NULL,
    costo_operativo   NUMERIC(10,2),
    descripcion       TEXT
);

-- =====================================================================
-- DIMENSIÓN CLIENTE (snowflake: referencia a dim_zona; canal preferido
-- se denormaliza como atributo de texto para evitar una segunda relación
-- activa con dim_canal -- "rol dimension" -- dentro de Power BI)
-- =====================================================================
CREATE TABLE dw.dim_cliente (
    id_cliente             INTEGER PRIMARY KEY,
    nombre                 VARCHAR(100) NOT NULL,
    edad                   INTEGER,
    genero                 VARCHAR(20) NOT NULL,
    tipo_cliente           VARCHAR(50),
    frecuencia_compra      VARCHAR(50),
    segmento_cliente       VARCHAR(20),
    canal_preferido        VARCHAR(100),       -- denormalizado desde canales_venta
    id_zona                INTEGER NOT NULL REFERENCES dw.dim_zona(id_zona)
);

-- =====================================================================
-- JERARQUÍA DE PRODUCTO (copo de nieve): categoria / proveedor -> producto
-- =====================================================================
CREATE TABLE dw.dim_categoria (
    id_categoria      INTEGER PRIMARY KEY,
    nombre_categoria  VARCHAR(100) NOT NULL
);

CREATE TABLE dw.dim_proveedor (
    id_proveedor      INTEGER PRIMARY KEY,
    nombre            VARCHAR(100) NOT NULL,
    telefono          VARCHAR(15),
    direccion         TEXT
);

CREATE TABLE dw.dim_producto (
    id_producto       INTEGER PRIMARY KEY,
    nombre_producto   VARCHAR(100) NOT NULL,
    precio_compra     NUMERIC(10,2) NOT NULL,
    precio_venta      NUMERIC(10,2) NOT NULL,
    margen_pct        NUMERIC(8,2),
    margen_abs        NUMERIC(10,2),
    estado_producto   VARCHAR(20) NOT NULL,
    fecha_ingreso     DATE,
    id_categoria      INTEGER NOT NULL REFERENCES dw.dim_categoria(id_categoria),
    id_proveedor      INTEGER NOT NULL REFERENCES dw.dim_proveedor(id_proveedor)
);

-- =====================================================================
-- JERARQUÍA DE VARIANTE (copo de nieve): sistema_talla -> talla; color
-- El color secundario se denormaliza como atributo de texto (mismo motivo
-- que canal_preferido: evita una segunda relación activa con dim_color).
-- =====================================================================
CREATE TABLE dw.dim_sistema_talla (
    id_sistema        SMALLINT PRIMARY KEY,
    nombre_sistema    VARCHAR(40) NOT NULL,
    descripcion       TEXT
);

CREATE TABLE dw.dim_talla (
    id_talla          SMALLINT PRIMARY KEY,
    etiqueta          VARCHAR(10) NOT NULL,
    orden             SMALLINT NOT NULL,
    id_sistema        SMALLINT NOT NULL REFERENCES dw.dim_sistema_talla(id_sistema)
);

CREATE TABLE dw.dim_color (
    id_color          SMALLINT PRIMARY KEY,
    nombre_color      VARCHAR(40) NOT NULL,
    hex               CHAR(7),
    es_compuesto      BOOLEAN NOT NULL
);

CREATE TABLE dw.dim_variante (
    id_variante              INTEGER PRIMARY KEY,
    sku                      VARCHAR(32) NOT NULL,
    activo                   BOOLEAN NOT NULL,
    tiempo_produccion_dias   SMALLINT,
    color_secundario         VARCHAR(40),        -- denormalizado, puede ser NULL
    id_producto              INTEGER NOT NULL REFERENCES dw.dim_producto(id_producto),
    id_talla                 SMALLINT NOT NULL REFERENCES dw.dim_talla(id_talla),
    id_color_principal       SMALLINT NOT NULL REFERENCES dw.dim_color(id_color)
);

-- =====================================================================
-- DIMENSIÓN MÉTODO DE PAGO
-- =====================================================================
CREATE TABLE dw.dim_metodo_pago (
    id_metodo_pago    INTEGER PRIMARY KEY,
    nombre            VARCHAR(100) NOT NULL,
    activo            BOOLEAN
);

-- =====================================================================
-- DIMENSIÓN PROMOCIÓN (incluye fila -1 "Sin promoción" para ventas sin
-- promoción aplicada, ya que id_promocion es NULLABLE en el origen)
-- =====================================================================
CREATE TABLE dw.dim_promocion (
    id_promocion         INTEGER PRIMARY KEY,
    nombre_promocion     VARCHAR(100) NOT NULL,
    tipo_descuento       VARCHAR(50),
    porcentaje_descuento NUMERIC(5,2),
    fecha_inicio         DATE,
    fecha_fin            DATE
);

-- =====================================================================
-- DIMENSIÓN VENDEDOR/ADMINISTRADOR (copo de nieve: rol)
-- =====================================================================
CREATE TABLE dw.dim_rol (
    id_rol            SMALLINT PRIMARY KEY,
    nombre_rol        VARCHAR(40) NOT NULL
);

CREATE TABLE dw.dim_admin (
    id_admin          INTEGER PRIMARY KEY,
    nombre            VARCHAR(100) NOT NULL,
    cargo             VARCHAR(50),
    id_rol            SMALLINT REFERENCES dw.dim_rol(id_rol)
);

-- =====================================================================
-- TABLA DE HECHOS: fact_ventas
-- Grano: 1 fila = 1 línea de detalle de venta (id_detalle)
-- =====================================================================
CREATE TABLE dw.fact_ventas (
    id_detalle        INTEGER PRIMARY KEY,        -- degenerada, natural de detalle_ventas
    id_venta          INTEGER NOT NULL,            -- degenerada, natural de ventas

    -- Claves foráneas a dimensiones
    fk_tiempo         INTEGER NOT NULL REFERENCES dw.dim_tiempo(fk_tiempo),
    fk_cliente        INTEGER NOT NULL REFERENCES dw.dim_cliente(id_cliente),
    fk_variante       INTEGER NOT NULL REFERENCES dw.dim_variante(id_variante),
    fk_canal          INTEGER NOT NULL REFERENCES dw.dim_canal(id_canal),
    fk_metodo_pago    INTEGER NOT NULL REFERENCES dw.dim_metodo_pago(id_metodo_pago),
    fk_promocion      INTEGER NOT NULL REFERENCES dw.dim_promocion(id_promocion),
    fk_admin          INTEGER NOT NULL REFERENCES dw.dim_admin(id_admin),

    -- Atributo degenerado (estado de la venta; baja cardinalidad)
    estado_venta      VARCHAR(20) NOT NULL,

    -- Medidas
    cantidad          INTEGER NOT NULL,
    precio_unitario   NUMERIC(10,2) NOT NULL,
    subtotal          NUMERIC(12,2) NOT NULL,
    costo_unitario    NUMERIC(10,2) NOT NULL,
    costo_total       NUMERIC(12,2) NOT NULL,
    margen_total       NUMERIC(12,2) NOT NULL,
    es_personalizado  BOOLEAN NOT NULL
);

CREATE INDEX idx_fact_ventas_tiempo    ON dw.fact_ventas(fk_tiempo);
CREATE INDEX idx_fact_ventas_cliente   ON dw.fact_ventas(fk_cliente);
CREATE INDEX idx_fact_ventas_variante  ON dw.fact_ventas(fk_variante);
CREATE INDEX idx_fact_ventas_canal     ON dw.fact_ventas(fk_canal);
CREATE INDEX idx_fact_ventas_promocion ON dw.fact_ventas(fk_promocion);
CREATE INDEX idx_fact_ventas_admin     ON dw.fact_ventas(fk_admin);
CREATE INDEX idx_fact_ventas_venta     ON dw.fact_ventas(id_venta);
