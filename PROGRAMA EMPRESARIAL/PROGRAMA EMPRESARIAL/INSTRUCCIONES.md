# App Transaccional RopaVacana — Guía rápida

## 1. Qué hace esta app

Es un formulario que se conecta directamente a tu PostgreSQL local (la misma
base `RopaVacanaV2` que usas en Power BI) y te deja:

1. **Registrar una venta nueva** (con sus productos/variantes), tal como lo
   haría el sistema real de la tienda — respeta todas las reglas que ya tiene
   tu base (descuento de stock, recálculo del total de la venta, etc.).
2. **Sincronizar** esos datos nuevos hacia el esquema `dw` (el Data Warehouse
   que ya construiste), de forma incremental — se puede correr varias veces
   sin duplicar nada.
3. **Ver una vista previa rápida** de ingresos/ventas por canal directo desde
   `dw`, y un espacio para embeber tu dashboard de Power BI una vez que lo
   publiques a la web.

La app corre en tu propia computadora; no envía datos a ningún servidor
externo.

## 2. Instalación (una sola vez)

Necesitas Python 3.9 o superior instalado. Abre una terminal en la carpeta
donde están estos archivos (`app.py`, `requirements.txt`) y ejecuta:

```
pip install -r requirements.txt
```

## 3. Ejecutar la app

```
streamlit run app.py
```

Esto abre una pestaña en tu navegador (normalmente en `http://localhost:8501`).

## 4. Conectarte a tu base de datos

En la barra lateral izquierda, llena:

- **Host**: `localhost` (ya viene por defecto)
- **Puerto**: `5432` (ya viene por defecto)
- **Base de datos**: `RopaVacanaV2` (ya viene por defecto)
- **Usuario**: el que usas en Power BI (por defecto `postgres`)
- **Contraseña**: la contraseña de ese usuario

Presiona **"Probar conexión"** para confirmar que todo está bien antes de
seguir.

## 5. Flujo de trabajo (versión en vivo, sin clics manuales en Power BI)

Con los cambios más recientes, la app ya no requiere que sincronices a mano:
al presionar **"Registrar venta"**, en la misma operación se inserta la
venta Y se sincroniza hacia `dw` (ambas cosas ocurren dentro de la misma
transacción de base de datos). La pestaña "Sincronizar con Data Warehouse"
ahora es solo un respaldo, no un paso obligatorio.

Para que Power BI también reaccione solo, sin que tú le des clic a
"Actualizar", hay que cambiar dos cosas en Power BI Desktop (una sola vez):

### 5.1 Reconectar las tablas de `dw` en modo DirectQuery

El modo "Importar" que usamos al principio copia los datos una sola vez y no
se entera de cambios nuevos por sí solo. Para verlos en vivo, Power BI debe
consultar la base directamente cada vez (DirectQuery). Importante: Power BI
no deja convertir una conexión ya hecha en "Importar" a "DirectQuery" — hay
que rehacer la conexión.

1. Antes de nada, guarda una copia de tu archivo actual (`Archivo > Guardar
   como`) por si quieres conservar la versión con datos importados.
2. En un archivo nuevo (o vaciando las consultas del actual): **Inicio >
   Obtener datos > Base de datos PostgreSQL**.
3. Ingresa el mismo servidor y base de datos de siempre, pero esta vez elige
   **Modo de conectividad de datos: DirectQuery** (en vez de "Importar").
4. Selecciona las mismas tablas de `dw` que ya conocías y carga.
5. Power BI vuelve a detectar las relaciones automáticamente (las mismas
   jerarquías de antes).
6. Vuelve a crear las medidas DAX que ya tenías (`Ingresos Totales`,
   `Ventas (conteo)`, etc.) — funcionan igual en DirectQuery, no cambian.
7. Arma de nuevo el gráfico del objetivo de prueba ("Ventas e ingresos por
   canal").

### 5.2 Activar la actualización automática de página

1. Haz clic en un espacio vacío de la página del reporte (no en un gráfico),
   para que se seleccione la página completa.
2. Abre el panel de formato de la página (ícono de pincel, sección "Page
   refresh" / "Actualización de página").
3. Activa el interruptor, elige **intervalo fijo** y pon el valor más bajo
   que te deje (por ejemplo 1 o 5 segundos).
4. En Power BI Desktop (sin publicar a un workspace) no hay restricción de
   intervalo mínimo — esa limitación de 30 minutos solo aplica cuando
   publicas a un workspace Pro sin Premium. Trabajando en Desktop, puedes ir
   tan rápido como quieras.

### 5.3 Probar el flujo completo

1. Deja Power BI Desktop abierto, con la página en la que armaste el
   gráfico, con la actualización automática activada.
2. En la app, ve a **"Registrar venta"**, arma una venta y presiona
   **"Registrar venta"**.
3. Sin tocar Power BI, espera unos segundos: la barra del canal
   correspondiente debería crecer sola.

Si algún producto no tiene stock suficiente, la base rechaza la venta
automáticamente y la app te lo muestra como un mensaje de error (esto es una
regla real de tu base, no un error de la app).

### 5.4 Dashboard en vivo dentro de la app (recomendado)

Se intentó incrustar el reporte real de Power BI dentro de la app usando
Power BI Embedded (API + token), pero requiere una capacidad de Microsoft
Fabric, y la prueba gratuita de Fabric está desactivada a nivel de tenant
para las cuentas de la universidad (no es algo que se pueda resolver desde
el lado del estudiante).

Por eso, la pestaña **"Dashboard"** de la app dibuja su propio gráfico del
KPI 1 (mismo objetivo, mismos campos: canal + estado_venta) leyendo directo
de `dw.fact_ventas`, con actualización automática cada pocos segundos
(configurable). No es literalmente el lienzo de Power BI, pero cumple el
requisito de ver el dashboard cambiar en tiempo real dentro de la app web,
sin depender de licencias ni de Azure. Al registrar una venta desde la
pestaña "Registrar venta", este gráfico refleja el cambio solo, sin que
toques nada.

## 6. Objetivo de prueba sugerido para la hoja nueva en Power BI

**Pregunta de negocio:** ¿Cuántas ventas y cuántos ingresos genera cada canal
de venta?

**Cómo armarla en Power BI** (reutiliza medidas que ya tienes):

1. Crea una hoja nueva en tu archivo de Power BI.
2. Inserta un gráfico de **columnas agrupadas** (o de barras).
3. Eje (Categoría): `dim_canal[nombre_canal]`.
4. Valores: `[Ingresos Totales]` y `[Ventas (conteo)]` (las medidas que ya
   creaste).
5. Título sugerido: "Ventas e ingresos por canal".

Con esto, cada vez que registres una venta nueva desde la app y sincronices,
la barra del canal correspondiente debería crecer al actualizar Power BI —
esa es la prueba de que todo el flujo (app → base transaccional → ETL
incremental → dw → Power BI) está funcionando.

## 7. Publicar el dashboard en la web (opcional, para más adelante)

En Power BI Desktop: **Archivo > Publicar > Publicar en la web**. Esto
requiere una cuenta de Microsoft/Power BI y genera un link público (cualquiera
con el link lo puede ver, sin iniciar sesión). Como tu base vive en tu propia
computadora, el reporte publicado no se va a actualizar solo — para eso se
necesita instalar el "Gateway de datos locales" de Microsoft. Ese es un paso
aparte que podemos abordar después de validar que el flujo local funciona
bien.
