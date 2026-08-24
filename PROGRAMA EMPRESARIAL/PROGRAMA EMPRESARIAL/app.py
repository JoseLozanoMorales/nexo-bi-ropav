"""
App transaccional RopaVacana
-----------------------------
Formulario para registrar ventas nuevas en la base transaccional (esquema public)
y sincronizarlas hacia el Data Warehouse (esquema dw) para que Power BI las refleje.

Cómo ejecutar:
    pip install -r requirements.txt
    streamlit run app.py

La app se conecta a TU PostgreSQL local (la misma base RopaVacanaV2 que usas
en Power BI). No mueve ni copia datos fuera de tu máquina.
"""

import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import date, datetime, time
from urllib.parse import urlparse, parse_qs

st.set_page_config(page_title="RopaVacana - App Transaccional", layout="wide")

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def get_connection():
    return psycopg2.connect(
        host=st.session_state.db_host,
        port=st.session_state.db_port,
        dbname=st.session_state.db_name,
        user=st.session_state.db_user,
        password=st.session_state.db_pass,
    )


def fetch_df(query, params=None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sincronización incremental hacia dw (compartida por el registro de venta
# automático y por el botón manual "Sincronizar ahora")
# ---------------------------------------------------------------------------
def sincronizar_dw(cur):
    """Ejecuta la sincronización incremental dentro de una transacción ya
    abierta (no hace commit/rollback, eso lo maneja quien la llama).
    Devuelve un dict con los conteos de filas afectadas."""

    # 1) Completar dim_tiempo con fechas de venta faltantes
    cur.execute(
        """
        INSERT INTO dw.dim_tiempo
            (fk_tiempo, fecha, anio, mes, nombre_mes, trimestre, dia,
             dia_semana, nombre_dia, semana_anio, es_fin_semana)
        SELECT DISTINCT
            TO_CHAR(v.fecha_venta::date, 'YYYYMMDD')::int,
            v.fecha_venta::date,
            EXTRACT(YEAR FROM v.fecha_venta)::smallint,
            EXTRACT(MONTH FROM v.fecha_venta)::smallint,
            TRIM(TO_CHAR(v.fecha_venta, 'TMMonth')),
            EXTRACT(QUARTER FROM v.fecha_venta)::smallint,
            EXTRACT(DAY FROM v.fecha_venta)::smallint,
            EXTRACT(DOW FROM v.fecha_venta)::smallint,
            TRIM(TO_CHAR(v.fecha_venta, 'TMDay')),
            EXTRACT(WEEK FROM v.fecha_venta)::smallint,
            EXTRACT(DOW FROM v.fecha_venta) IN (0, 6)
        FROM public.ventas v
        WHERE NOT EXISTS (
            SELECT 1 FROM dw.dim_tiempo dt
            WHERE dt.fk_tiempo = TO_CHAR(v.fecha_venta::date, 'YYYYMMDD')::int
        )
        """
    )
    nuevas_fechas = cur.rowcount

    # 2) Insertar hechos nuevos (líneas de venta no sincronizadas)
    cur.execute(
        """
        INSERT INTO dw.fact_ventas
            (id_detalle, id_venta, fk_tiempo, fk_cliente, fk_variante,
             fk_canal, fk_metodo_pago, fk_promocion, fk_admin,
             estado_venta, cantidad, precio_unitario, subtotal,
             costo_unitario, costo_total, margen_total, es_personalizado)
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
            COALESCE(vp.precio_compra_override, p.precio_compra),
            COALESCE(vp.precio_compra_override, p.precio_compra) * dv.cantidad,
            dv.subtotal - (COALESCE(vp.precio_compra_override, p.precio_compra) * dv.cantidad),
            dv.es_personalizado
        FROM public.detalle_ventas dv
        JOIN public.ventas v ON v.id_venta = dv.id_venta
        JOIN public.variantes_producto vp ON vp.id_variante = dv.id_variante
        JOIN public.productos p ON p.id_producto = vp.id_producto
        WHERE NOT EXISTS (
            SELECT 1 FROM dw.fact_ventas f WHERE f.id_detalle = dv.id_detalle
        )
        """
    )
    nuevos_hechos = cur.rowcount

    # 3) Refrescar estado_venta de hechos ya existentes
    cur.execute(
        """
        UPDATE dw.fact_ventas f
        SET estado_venta = v.estado_venta::text
        FROM public.ventas v
        WHERE v.id_venta = f.id_venta
          AND f.estado_venta <> v.estado_venta::text
        """
    )
    estados_actualizados = cur.rowcount

    return {
        "nuevas_fechas": nuevas_fechas,
        "nuevos_hechos": nuevos_hechos,
        "estados_actualizados": estados_actualizados,
    }


with st.sidebar:
    st.header("Conexión a PostgreSQL")
    st.session_state.setdefault("db_host", "localhost")
    st.session_state.setdefault("db_port", "5432")
    st.session_state.setdefault("db_name", "RopaVacanaV2")
    st.session_state.setdefault("db_user", "postgres")
    st.session_state.setdefault("db_pass", "")

    st.session_state.db_host = st.text_input("Host", st.session_state.db_host)
    st.session_state.db_port = st.text_input("Puerto", st.session_state.db_port)
    st.session_state.db_name = st.text_input("Base de datos", st.session_state.db_name)
    st.session_state.db_user = st.text_input("Usuario", st.session_state.db_user)
    st.session_state.db_pass = st.text_input(
        "Contraseña", st.session_state.db_pass, type="password"
    )

    if st.button("Probar conexión"):
        try:
            conn = get_connection()
            conn.close()
            st.success("Conexión exitosa.")
        except Exception as e:
            st.error(f"No se pudo conectar: {e}")

st.title("RopaVacana - App Transaccional")
st.caption(
    "Registra ventas nuevas: cada venta se sincroniza automáticamente hacia "
    "dw. Si además dejas Power BI Desktop en DirectQuery con actualización "
    "automática de página, el dashboard cambia solo, sin que toques nada."
)

if "carrito" not in st.session_state:
    st.session_state.carrito = []

tab_venta, tab_sync, tab_dash, tab_azure = st.tabs(
    [
        "Registrar venta",
        "Sincronizar con Data Warehouse",
        "Dashboard",
        "Prueba: login Azure AD",
    ]
)

# ---------------------------------------------------------------------------
# TAB 1: Registrar venta
# ---------------------------------------------------------------------------
with tab_venta:
    st.subheader("1. Datos generales de la venta")

    try:
        clientes_df = fetch_df(
            "SELECT id_cliente, nombre FROM public.clientes ORDER BY nombre"
        )
        canales_df = fetch_df(
            "SELECT id_canal, nombre_canal FROM public.canales_venta ORDER BY nombre_canal"
        )
        metodos_df = fetch_df(
            "SELECT id_metodo_pago, nombre FROM public.metodo_pago "
            "WHERE activo IS DISTINCT FROM false ORDER BY nombre"
        )
        admins_df = fetch_df(
            "SELECT id_admin, nombre FROM public.administradores ORDER BY nombre"
        )
        promos_df = fetch_df(
            "SELECT id_promocion, nombre_promocion FROM public.promociones "
            "ORDER BY nombre_promocion"
        )
        productos_df = fetch_df(
            "SELECT id_producto, nombre_producto FROM public.productos "
            "WHERE estado_producto = 'Activo' ORDER BY nombre_producto"
        )
    except Exception as e:
        st.error(
            f"No se pudieron cargar los catálogos desde la base de datos: {e}\n\n"
            "Revisa la conexión en la barra lateral."
        )
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        cliente_sel = st.selectbox(
            "Cliente",
            options=clientes_df["id_cliente"] if not clientes_df.empty else [],
            format_func=lambda i: clientes_df.set_index("id_cliente").loc[i, "nombre"]
            if not clientes_df.empty
            else i,
        )
        canal_sel = st.selectbox(
            "Canal de venta",
            options=canales_df["id_canal"] if not canales_df.empty else [],
            format_func=lambda i: canales_df.set_index("id_canal").loc[i, "nombre_canal"]
            if not canales_df.empty
            else i,
        )
    with col2:
        metodo_sel = st.selectbox(
            "Método de pago",
            options=metodos_df["id_metodo_pago"] if not metodos_df.empty else [],
            format_func=lambda i: metodos_df.set_index("id_metodo_pago").loc[i, "nombre"]
            if not metodos_df.empty
            else i,
        )
        admin_sel = st.selectbox(
            "Administrador / vendedor",
            options=admins_df["id_admin"] if not admins_df.empty else [],
            format_func=lambda i: admins_df.set_index("id_admin").loc[i, "nombre"]
            if not admins_df.empty
            else i,
        )
    with col3:
        promo_options = [None] + (
            list(promos_df["id_promocion"]) if not promos_df.empty else []
        )
        promo_sel = st.selectbox(
            "Promoción (opcional)",
            options=promo_options,
            format_func=lambda i: "Sin promoción"
            if i is None
            else promos_df.set_index("id_promocion").loc[i, "nombre_promocion"],
        )
        estado_sel = st.selectbox(
            "Estado de la venta",
            options=["Completada", "Cancelada", "Pendiente", "Devuelta"],
        )

    usar_fecha_actual = st.checkbox("Usar fecha y hora actuales", value=True)
    if usar_fecha_actual:
        fecha_venta_dt = datetime.now()
    else:
        fecha_custom = st.date_input("Fecha de la venta", value=date.today())
        fecha_venta_dt = datetime.combine(fecha_custom, time(12, 0))

    st.divider()
    st.subheader("2. Agregar productos a la venta")

    if productos_df.empty:
        st.warning("No hay productos activos en la base de datos.")
    else:
        pcol1, pcol2 = st.columns([1, 2])
        with pcol1:
            producto_sel = st.selectbox(
                "Producto",
                options=productos_df["id_producto"],
                format_func=lambda i: productos_df.set_index("id_producto").loc[
                    i, "nombre_producto"
                ],
            )
        variantes_df = fetch_df(
            """
            SELECT vp.id_variante, vp.sku, t.etiqueta AS talla, c.nombre AS color,
                   COALESCE(vp.precio_venta_override, p.precio_venta) AS precio_venta,
                   COALESCE(i.cantidad_disponible, 0) AS stock
            FROM public.variantes_producto vp
            JOIN public.productos p ON p.id_producto = vp.id_producto
            JOIN public.tallas t ON t.id_talla = vp.id_talla
            JOIN public.colores c ON c.id_color = vp.id_color_principal
            LEFT JOIN public.inventario i ON i.id_variante = vp.id_variante
            WHERE vp.id_producto = %s AND vp.activo
            ORDER BY t.orden, c.nombre
            """,
            (int(producto_sel),),
        )

        if variantes_df.empty:
            st.warning("Este producto no tiene variantes activas.")
        else:
            with pcol2:
                variante_sel = st.selectbox(
                    "Variante (SKU - talla - color - stock disponible)",
                    options=variantes_df["id_variante"],
                    format_func=lambda i: (
                        f"{variantes_df.set_index('id_variante').loc[i, 'sku']} - "
                        f"Talla {variantes_df.set_index('id_variante').loc[i, 'talla']} - "
                        f"{variantes_df.set_index('id_variante').loc[i, 'color']} "
                        f"(stock: {int(variantes_df.set_index('id_variante').loc[i, 'stock'])})"
                    ),
                )

            fila_variante = variantes_df.set_index("id_variante").loc[variante_sel]
            vcol1, vcol2, vcol3 = st.columns(3)
            with vcol1:
                cantidad_in = st.number_input("Cantidad", min_value=1, value=1, step=1)
            with vcol2:
                precio_in = st.number_input(
                    "Precio unitario",
                    min_value=0.0,
                    value=float(fila_variante["precio_venta"]),
                    step=0.5,
                    format="%.2f",
                )
            with vcol3:
                personalizado_in = st.checkbox("Es personalizado", value=False)

            if st.button("Agregar al carrito"):
                st.session_state.carrito.append(
                    {
                        "id_variante": int(variante_sel),
                        "descripcion": (
                            f"{fila_variante['sku']} - Talla {fila_variante['talla']} - "
                            f"{fila_variante['color']}"
                        ),
                        "cantidad": int(cantidad_in),
                        "precio_unitario": float(precio_in),
                        "es_personalizado": bool(personalizado_in),
                        "stock_disponible": int(fila_variante["stock"]),
                    }
                )
                st.rerun()

    st.divider()
    st.subheader("3. Carrito de la venta")

    if not st.session_state.carrito:
        st.info("Todavía no has agregado productos a esta venta.")
    else:
        for idx, item in enumerate(st.session_state.carrito):
            ccol1, ccol2, ccol3, ccol4, ccol5 = st.columns([3, 1, 1, 1, 1])
            ccol1.write(item["descripcion"])
            ccol2.write(f"Cant: {item['cantidad']}")
            ccol3.write(f"P.U.: ${item['precio_unitario']:.2f}")
            ccol4.write("Personalizado" if item["es_personalizado"] else "Estándar")
            if ccol5.button("Quitar", key=f"quitar_{idx}"):
                st.session_state.carrito.pop(idx)
                st.rerun()

        total_estimado = sum(
            i["cantidad"] * i["precio_unitario"] for i in st.session_state.carrito
        )
        st.write(f"**Total estimado: ${total_estimado:,.2f}**")

        if st.button("Registrar venta", type="primary"):
            conn = get_connection()
            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.ventas
                            (fecha_venta, estado_venta, id_cliente, id_canal,
                             id_promocion, id_admin, id_metodo_pago)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id_venta
                        """,
                        (
                            fecha_venta_dt,
                            estado_sel,
                            int(cliente_sel),
                            int(canal_sel),
                            int(promo_sel) if promo_sel is not None else None,
                            int(admin_sel),
                            int(metodo_sel),
                        ),
                    )
                    id_venta_nueva = cur.fetchone()[0]

                    for item in st.session_state.carrito:
                        cur.execute(
                            """
                            INSERT INTO public.detalle_ventas
                                (id_venta, cantidad, precio_unitario,
                                 es_personalizado, id_variante)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                id_venta_nueva,
                                item["cantidad"],
                                item["precio_unitario"],
                                item["es_personalizado"],
                                item["id_variante"],
                            ),
                        )
                    conteos = sincronizar_dw(cur)

                conn.commit()
                st.success(
                    f"Venta #{id_venta_nueva} registrada con "
                    f"{len(st.session_state.carrito)} línea(s) y sincronizada "
                    f"a dw ({conteos['nuevos_hechos']} hecho(s) nuevo(s), "
                    f"{conteos['nuevas_fechas']} fecha(s) nueva(s)). Si tienes "
                    "Power BI con DirectQuery y actualización automática de "
                    "página, el gráfico ya debería reflejarlo en segundos."
                )
                st.session_state.carrito = []
            except psycopg2.errors.RaiseException as e:
                conn.rollback()
                st.error(
                    "No se pudo registrar la venta: no hay stock suficiente para "
                    f"alguna de las variantes. Detalle de la base de datos: {e}"
                )
            except Exception as e:
                conn.rollback()
                st.error(f"Ocurrió un error al registrar la venta: {e}")
            finally:
                conn.close()

# ---------------------------------------------------------------------------
# TAB 2: Sincronizar con Data Warehouse
# ---------------------------------------------------------------------------
with tab_sync:
    st.subheader("Sincronizar ventas nuevas hacia el esquema dw")
    st.info(
        "Desde ahora, 'Registrar venta' ya sincroniza automáticamente. Usa "
        "este botón solo como respaldo (por ejemplo, si insertaste datos por "
        "otro medio o quieres forzar una revisión)."
    )
    st.markdown(
        "- Agrega a `dw.dim_tiempo` las fechas de venta que todavía no existan.\n"
        "- Inserta en `dw.fact_ventas` las líneas de venta (`detalle_ventas`) que "
        "todavía no se hayan sincronizado.\n"
        "- Actualiza el `estado_venta` de los hechos ya sincronizados, por si una "
        "venta cambió de estado (por ejemplo, se canceló después de registrarse)."
    )

    if st.button("Sincronizar ahora", type="primary"):
        conn = get_connection()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                conteos = sincronizar_dw(cur)
            conn.commit()
            st.success(
                f"Sincronización completa: {conteos['nuevas_fechas']} fecha(s) "
                f"nueva(s) en dim_tiempo, {conteos['nuevos_hechos']} línea(s) de "
                f"venta nueva(s) en fact_ventas, "
                f"{conteos['estados_actualizados']} estado(s) actualizado(s)."
            )
        except Exception as e:
            conn.rollback()
            st.error(f"Ocurrió un error durante la sincronización: {e}")
        finally:
            conn.close()

# ---------------------------------------------------------------------------
# TAB 3: Dashboard en vivo
# ---------------------------------------------------------------------------
with tab_dash:
    st.subheader("Dashboard de Power BI (reporte real, embebido)")
    st.caption(
        "Reporte de Power BI Service en DirectQuery, conectado a través del "
        "Gateway de datos locales. La primera vez te va a pedir iniciar "
        "sesión con tu cuenta institucional."
    )
    st.info(
        "Después de registrar una venta, vuelve aquí y dale clic al ícono "
        "de **actualizar (⟳)** dentro del reporte de abajo. Como es "
        "DirectQuery, el dato nuevo aparece al instante, sin recargar toda "
        "la pantalla."
    )

    embed_url = st.text_input(
        "Link seguro de Power BI (Archivo > Insertar informe > Sitio web o portal)",
        value=st.session_state.get(
            "pbi_embed_url",
            "https://app.powerbi.com/reportEmbed?reportId=7602737b-4a3d-4489-b108-ac24ef5ebc8a&autoAuth=true&ctid=edd334f8-81c6-4062-ad3a-87668a1e074e",
        ),
        key="pbi_embed_url",
    )
    if embed_url:
        st.components.v1.iframe(embed_url, height=600)
    else:
        st.info("Pega aquí el link seguro que generaste desde Power BI Service.")

    st.divider()
    st.subheader("Respaldo: KPI 1 dibujado por la app (se actualiza solo)")
    st.caption(
        "Mismo objetivo, mismos campos y mismas medidas que el gráfico de "
        "arriba (canal, estado_venta). Este gráfico lo dibuja la propia "
        "app, leyendo directo de dw, y sí se refresca solo cada pocos "
        "segundos — úsalo como referencia rápida mientras confirmas el "
        "cambio en el reporte de Power BI de arriba."
    )

    col_auto, col_int = st.columns([1, 2])
    with col_auto:
        auto_on = st.toggle("Actualizar automáticamente", value=True)
    with col_int:
        intervalo_seg = st.slider(
            "Cada cuántos segundos", min_value=2, max_value=30, value=3
        )

    if auto_on:
        st_autorefresh(interval=intervalo_seg * 1000, key="kpi1_autorefresh")

    try:
        kpi1_df = fetch_df(
            """
            SELECT dc.nombre_canal AS canal,
                   COUNT(DISTINCT CASE WHEN f.estado_venta = 'Completada'
                                        THEN f.id_venta END) AS ventas_completadas,
                   COUNT(DISTINCT CASE WHEN f.estado_venta = 'Cancelada'
                                        THEN f.id_venta END) AS ventas_canceladas
            FROM dw.fact_ventas f
            JOIN dw.dim_canal dc ON dc.id_canal = f.fk_canal
            GROUP BY dc.nombre_canal
            ORDER BY ventas_completadas DESC
            """
        )
    except Exception as e:
        kpi1_df = pd.DataFrame()
        st.error(f"No se pudo leer el esquema dw: {e}")

    if kpi1_df.empty:
        st.warning(
            "Todavía no hay datos en dw.fact_ventas. Registra una venta en la "
            "pestaña 'Registrar venta' (se sincroniza sola) y vuelve aquí."
        )
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=kpi1_df["canal"],
                x=kpi1_df["ventas_completadas"],
                name="Ventas Completadas",
                orientation="h",
                marker_color="#1f77b4",
                text=kpi1_df["ventas_completadas"],
                textposition="outside",
            )
        )
        fig.add_trace(
            go.Bar(
                y=kpi1_df["canal"],
                x=kpi1_df["ventas_canceladas"],
                name="Ventas canceladas",
                orientation="h",
                marker_color="#0b2b4a",
                text=kpi1_df["ventas_canceladas"],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="Ventas Completadas y Canceladas por Canal",
            xaxis_title="Ventas Completadas y Ventas canceladas",
            yaxis_title="Canal de venta",
            barmode="group",
            height=420,
            margin=dict(l=10, r=10, t=60, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Última lectura: {datetime.now().strftime('%H:%M:%S')}"
            + (
                f" · se refresca cada {intervalo_seg}s"
                if auto_on
                else " · actualización automática desactivada"
            )
        )

# ---------------------------------------------------------------------------
# TAB 4: Prueba de login Azure AD (solo para reproducir el error de
# consentimiento del administrador y mostrárselo en vivo)
# ---------------------------------------------------------------------------
with tab_azure:
    st.subheader("Prueba: login con Azure AD (reproduce el error de consentimiento)")
    st.caption(
        "Esta pestaña es solo para la demostración con el administrador. No es "
        "necesaria para que el resto de la app funcione — el Dashboard de arriba "
        "ya funciona sin esto. Al hacer clic en el botón, el navegador intenta "
        "iniciar sesión pidiendo los permisos de la app RopaVacanaEmbed "
        "(User.Read y Report.Read.All). Si el administrador todavía no dio su "
        "consentimiento, aparece el error 'Se necesita la aprobación del "
        "administrador'."
    )

    colA, colB = st.columns(2)
    with colA:
        tenant_id_in = st.text_input(
            "Tenant ID (Directorio)",
            value="edd334f8-81c6-4062-ad3a-87668a1e074e",
        )
    with colB:
        client_id_in = st.text_input(
            "Client ID (Application ID de RopaVacanaEmbed)", value=""
        )

    if not client_id_in:
        st.info(
            "Pega aquí el 'Application (client) ID' de la app RopaVacanaEmbed "
            "(está en Azure Portal > Registros de aplicaciones > RopaVacanaEmbed "
            "> Información general)."
        )
    else:
        login_html = f"""
        <div style="font-family: sans-serif;">
          <button id="loginBtn" style="padding:10px 16px; font-size:14px; cursor:pointer;">
            Iniciar sesión con Azure AD (probar permisos)
          </button>
          <pre id="log" style="background:#111;color:#0f0;padding:10px;margin-top:10px;height:260px;overflow:auto;font-size:12px;"></pre>
        </div>
        <script>
          const logEl = document.getElementById('log');
          function log(msg) {{
            logEl.textContent += msg + "\\n";
            logEl.scrollTop = logEl.scrollHeight;
          }}
          document.getElementById('loginBtn').disabled = true;
          log("Cargando librería MSAL...");
        </script>
        <script
          src="https://cdn.jsdelivr.net/npm/@azure/msal-browser@3.7.1/lib/msal-browser.min.js"
          onload="document.getElementById('loginBtn').disabled = false; document.getElementById('log').textContent += 'MSAL cargado correctamente (jsDelivr).\\n';"
          onerror="document.getElementById('log').textContent += 'ERROR: jsDelivr tampoco cargó. Probando unpkg...\\n'; (function(){{ var s=document.createElement('script'); s.src='https://unpkg.com/@azure/msal-browser@3.7.1/lib/msal-browser.min.js'; s.onload=function(){{ document.getElementById('loginBtn').disabled=false; document.getElementById('log').textContent += 'MSAL cargado correctamente (unpkg).\\n'; }}; s.onerror=function(){{ document.getElementById('log').textContent += 'ERROR: ningun CDN cargó. Es un bloqueo de red/firewall, no del código.\\n'; }}; document.body.appendChild(s); }})();"
        ></script>
        <script>
          const msalConfig = {{
            auth: {{
              clientId: "{client_id_in}",
              authority: "https://login.microsoftonline.com/{tenant_id_in}",
              redirectUri: "http://localhost:8501"
            }}
          }};

          document.getElementById('loginBtn').addEventListener('click', async () => {{
            const logEl2 = document.getElementById('log');
            function log2(msg) {{
              logEl2.textContent += msg + "\\n";
              logEl2.scrollTop = logEl2.scrollHeight;
            }}
            if (typeof msal === 'undefined') {{
              log2("ERROR: la librería MSAL todavía no está cargada.");
              return;
            }}
            const msalInstance = new msal.PublicClientApplication(msalConfig);
            log2("Inicializando MSAL...");
            try {{
              await msalInstance.initialize();
              log2("Abriendo ventana de login...");
              const result = await msalInstance.loginPopup({{
                scopes: ["User.Read", "https://analysis.windows.net/powerbi/api/Report.Read.All"],
                prompt: "select_account"
              }});
              log2("Login exitoso. Cuenta: " + result.account.username);
              log2("Pidiendo token específico de Power BI (esta es la prueba real "
                   + "de si el consentimiento del administrador ya quedó activo)...");
              const tokenResponse = await msalInstance.acquireTokenSilent({{
                scopes: ["https://analysis.windows.net/powerbi/api/Report.Read.All"],
                account: result.account
              }});
              log2("¡TOKEN OBTENIDO! El consentimiento del administrador está "
                   + "activo. Expira: " + tokenResponse.expiresOn);
              log2("accessToken (primeros 25 caracteres): "
                   + tokenResponse.accessToken.substring(0, 25) + "...");
            }} catch (err) {{
              log2("ERROR: " + (err.errorCode || err.name || "desconocido"));
              log2(err.message || String(err));
            }}
          }});
        </script>
        """
        st.components.v1.html(login_html, height=380)
