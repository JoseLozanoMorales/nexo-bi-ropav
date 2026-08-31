"""Six business objectives grounded in the inspected RopaVacana PBIT.

Read-only, parameterized queries against live public data. No LLM SQL and no
top-N truncation. Every chart carries the objective, dimensions and formula.
"""
import re
import unicodedata
from datetime import date
from copy import deepcopy

from db import connect
from semantic_analytics import BASE, DIMENSIONS
from weekly_analysis import SALE_CRITERION

LABELS = {"ingresos": "Ventas totales", "utilidad": "Margen total",
          "margen": "Margen %", "transacciones": "Transacciones",
          "unidades": "Unidades vendidas", "clientes": "Clientes unicos",
          "ticket_promedio": "Venta promedio", "crecimiento": "Crecimiento mensual %"}
FORMULAS = {
    "ingresos": "SUM(ventas[subtotal])",
    "utilidad": "SUM(ventas[margen_total]); margen_total = subtotal - costo_unitario × cantidad",
    "margen": "DIVIDE([Margen total], [Ventas totales]); se muestra × 100 como porcentaje",
    "transacciones": "DISTINCTCOUNT(ventas[id_venta])",
    "unidades": "SUM(ventas[cantidad])",
    "clientes": "DISTINCTCOUNT(ventas[fk_cliente])",
    "ticket_promedio": "DIVIDE([Ventas totales], [Transacciones])",
    "crecimiento": "DIVIDE([Ventas totales] - [Ventas mes anterior], [Ventas mes anterior]); × 100",
}
FORMATS = {k: "percent" if k in ("margen", "crecimiento") else
           "currency" if k in ("ingresos", "utilidad", "ticket_promedio") else "number" for k in LABELS}
COLORS = ["#11a99a", "#ff9f68", "#56c5d0", "#8576d4", "#e57b9b", "#4f86c6"]
DIM_LABELS = {"canal": "Canal", "tipo_dia": "Tipo de día", "dia_semana": "Día de semana",
              "dia": "Fecha", "mes": "Año-mes", "region": "Región", "categoria": "Categoría",
              "tipo_cliente": "Tipo de cliente", "tipo_venta": "Tipo de venta",
              "promocion": "Promoción", "tipo_descuento": "Tipo de descuento",
              "porcentaje_descuento": "Descuento %"}
OBJECTIVE_DIMENSIONS = {**DIMENSIONS,
    "tipo_dia": "CASE WHEN extract(isodow from v.fecha_venta) >= 6 THEN 'Fin de semana' ELSE 'Laborable' END",
    "tipo_venta": "CASE WHEN d.es_personalizado THEN 'Personalizado' ELSE 'Estándar' END",
    "dia_semana": "extract(isodow from v.fecha_venta)::int",
    "tipo_descuento": "COALESCE(prom.tipo_descuento,'Sin promoción')",
    "porcentaje_descuento": "prom.porcentaje_descuento"}
COST_MARGIN = "SUM(d.subtotal-d.cantidad*COALESCE(vp.precio_compra_override,p.precio_compra))"
SQL_METRICS = {
    "ingresos": "SUM(d.subtotal)", "utilidad": COST_MARGIN,
    "margen": f"100.0*{COST_MARGIN}/NULLIF(SUM(d.subtotal),0)",
    "transacciones": "COUNT(DISTINCT v.id_venta)", "unidades": "SUM(d.cantidad)",
    "clientes": "COUNT(DISTINCT v.id_cliente)",
    "ticket_promedio": "SUM(d.subtotal)/NULLIF(COUNT(DISTINCT v.id_venta),0)"}


def visual(kind, title, dimensions, metrics, purpose, **extra):
    return dict(type=kind, title=title, dimensions=dimensions, metrics=metrics, purpose=purpose, **extra)


OBJECTIVES = {
 1: dict(title="Ventas — Estacionalidad semanal",
    objective="Determinar cómo varía el comportamiento de compra entre días laborables y fines de semana en cada canal de venta.",
    kpis=["ingresos", "transacciones", "unidades", "ticket_promedio"],
    warnings=["Los totales no son promedios diarios: lunes a viernes aporta más días que el fin de semana. Laborable significa lunes–viernes, sin ajuste por festivos. No se mide afluencia de visitantes."],
    charts=[visual("bar", "Ventas por canal y tipo de día", ["canal", "tipo_dia"], ["ingresos"], "Comparar el ingreso entre laborables y fin de semana en cada canal."),
            visual("line", "Ventas por día de semana y canal", ["dia_semana", "canal"], ["ingresos"], "Localizar los días de mayor ingreso por canal."),
            visual("matrix", "Canal × tipo de día", ["canal", "tipo_dia"], ["ingresos", "transacciones", "unidades"], "Contrastar importe, número de compras y volumen sin confundirlos.")]),
 2: dict(title="Ventas — Tendencia mensual",
    objective="Analizar la evolución mensual de las ventas a lo largo del año, para anticipar los meses de mayor y menor demanda y planificar compras, personal y campañas con antelación.",
    kpis=["ingresos", "transacciones", "unidades", "crecimiento"],
    warnings=["Es análisis histórico, no un pronóstico. Se conserva año-mes para no mezclar años. El crecimiento compara meses calendario; periodos parciales se comparan con el mismo rango desplazado un mes. Sin base anterior o con base cero se muestra N/D."],
    charts=[visual("line", "Evolución diaria de ventas", ["dia"], ["ingresos"], "Observar la trayectoria dentro del periodo."),
            visual("bar", "Ventas mensuales", ["mes"], ["ingresos"], "Identificar máximos y mínimos de demanda por año-mes."),
            visual("table", "Ventas y crecimiento mensual", ["mes"], ["ingresos", "crecimiento"], "Cuantificar el cambio frente al mes calendario anterior.")]),
 3: dict(title="Región — Desempeño geográfico",
    objective="Identificar qué región del país (Costa, Sierra, Amazonía, Insular) genera mayores ingresos y en qué categorías, para orientar la inversión en logística y marketing regional.",
    kpis=["ingresos", "utilidad", "margen", "transacciones"], warnings=["Región no es provincia. Solo se muestran combinaciones con datos; ausencia de ventas no demuestra ausencia de demanda."],
    charts=[visual("bar", "Ventas y margen total por región", ["region"], ["ingresos", "utilidad"], "Comparar escala y rentabilidad absoluta por región."),
            visual("treemap", "Ventas por región y categoría", ["region", "categoria"], ["ingresos"], "Mostrar en qué categorías se concentra el ingreso de cada región.")]),
 4: dict(title="Clientes — Segmentación de rentabilidad",
    objective="Evaluar qué segmento de cliente (VIP, frecuente, ocasional) genera mayor margen de ganancia, para priorizar programas de fidelización y esfuerzo comercial en los segmentos más rentables.",
    kpis=["ingresos", "utilidad", "margen", "clientes"],
    warnings=["Se usa tipo_cliente, igual que la plantilla. No se inventa equivalencia entre VIP/frecuente/ocasional y los valores reales (por ejemplo VIP/Premium/Regular/Nuevo). La rentabilidad observada no es valor de vida del cliente."],
    charts=[visual("bar", "Margen total por tipo de cliente", ["tipo_cliente"], ["utilidad"], "Priorizar tipos por ganancia absoluta."),
            visual("pie", "Clientes únicos por tipo", ["tipo_cliente"], ["clientes"], "Distinguir tamaño del grupo de rentabilidad."),
            visual("table", "Rentabilidad de clientes", ["tipo_cliente"], ["ingresos", "utilidad", "margen", "clientes"], "Contrastar ingresos, margen absoluto, margen relativo y clientes únicos.")]),
 5: dict(title="Productos — Personalización vs. estándar",
    objective="Comparar la rentabilidad de la ropa personalizada frente a la venta estándar, y en qué categorías se concentra la demanda de personalización, para decidir si ampliar esa línea de negocio.",
    kpis=["utilidad", "margen", "unidades", "ingresos"],
    warnings=["USD y porcentajes se muestran en gráficos separados, no en una misma escala. Una venta con líneas estándar y personalizadas puede aparecer en ambos grupos; los conteos distintos no son aditivos."],
    charts=[visual("bar", "Margen total por tipo de venta", ["tipo_venta"], ["utilidad"], "Comparar la ganancia monetaria de las dos líneas."),
            visual("bar", "Margen porcentual por tipo de venta", ["tipo_venta"], ["margen"], "Comparar rentabilidad relativa en su propia escala."),
            visual("bar", "Ventas por categoría y tipo de venta", ["categoria", "tipo_venta"], ["ingresos"], "Localizar categorías con demanda de personalización.", orientation="horizontal"),
            visual("matrix", "Categoría × tipo de venta", ["categoria", "tipo_venta"], ["unidades", "margen"], "Comparar volumen y rentabilidad sin promediar porcentajes de filas.")]),
 6: dict(title="Promociones — Retorno de promociones",
    objective="Evaluar la rentabilidad generada por cada promoción aplicada, para decidir cuáles mantener, ajustar o descontinuar.",
    kpis=["ingresos", "utilidad", "margen", "transacciones"],
    warnings=["Margen observado no equivale a ROI ni impacto causal. Faltan inversión de campaña y contrafactual. Sin promoción se conserva como referencia descriptiva. La tarjeta vacía del PBIT se sustituye por KPIs definidos."],
    charts=[visual("bar", "Margen total por promoción", ["promocion"], ["utilidad"], "Comparar ganancia observada por promoción."),
            visual("bar", "Margen porcentual por promoción", ["promocion"], ["margen"], "Comparar margen relativo en una escala porcentual independiente."),
            visual("bar", "Transacciones por promoción", ["promocion"], ["transacciones"], "Contrastar frecuencia con rentabilidad."),
            visual("table", "Resultados de promociones", ["promocion", "tipo_descuento", "porcentaje_descuento"], ["ingresos", "utilidad", "margen", "transacciones"], "Revisar descuento, ventas y margen antes de decidir.")])
}


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(c))


def detect_objective(text):
    """Conservative routing; unrelated dashboards retain the generic planner."""
    text = plain(text)
    ids = set(re.findall(r"(?:objetivo|dashboard|tablero|pagina)\s*(?:numero\s*|n[º°.]?\s*|#\s*)?([1-6])\b", text))
    if len(ids) == 1:
        return int(next(iter(ids)))
    if len(ids) > 1:
        return None
    matches = []
    patterns = {1: r"estacionalidad semanal|fin(?:es)? de semana|dias laborables",
                2: r"tendencia mensual|evolucion mensual|meses de mayor y menor demanda",
                3: r"desempeno geografico|marketing regional|region.*categor|region.*ingres",
                4: r"segmentacion de rentabilidad|(?:cliente|segmento).*rentab|(?:cliente|segmento).*margen",
                5: r"personalizad|personalizacion",
                6: r"retorno de promociones|promocion(?:es)?.*(?:rentab|margen|retorno|mantener|ajustar|descontinuar)"}
    for number, pattern in patterns.items():
        if re.search(pattern, text): matches.append(number)
    return matches[0] if len(matches) == 1 else None


def objective_catalog():
    return {"fuente": "Objetivos del usuario + RopaVacana_App.pbit", "objetivos": [
        {"id": key, **deepcopy(value)} for key, value in OBJECTIVES.items()], "formulas": FORMULAS}


def validate_filters(filters):
    clean = {k: v for k, v in (filters or {}).items() if k in ("desde", "hasta", "region", "provincia", "canal")
             and v and str(v).strip().casefold() not in ("todo", "todos", "toda", "todas", "all")}
    for key in ("desde", "hasta"):
        if key in clean: clean[key] = date.fromisoformat(str(clean[key])).isoformat()
    if clean.get("desde", "0001") > clean.get("hasta", "9999"):
        raise ValueError("El final del periodo es anterior al inicio")
    return clean


def _where(filters):
    fields = {"desde": ("v.fecha_venta::date", ">="), "hasta": ("v.fecha_venta::date", "<="),
              "region": ("rg.nombre_region", "="), "provincia": ("pr.nombre", "="), "canal": ("cv.nombre_canal", "=")}
    clauses, values = ["v.estado_venta <> 'Cancelada'"], []
    for key, value in filters.items():
        field, operator = fields[key]
        clauses.append(f"{field} {operator} %s")
        values.append(value)
    return " AND ".join(clauses), values


def _query(conn, dimensions, metrics, filters):
    if any(d not in OBJECTIVE_DIMENSIONS for d in dimensions) or any(m not in SQL_METRICS for m in metrics):
        raise ValueError("Consulta fuera del catálogo de objetivos")
    where, params = _where(filters)
    selected = [f'{OBJECTIVE_DIMENSIONS[d]} AS "{d}"' for d in dimensions]
    selected += [f'{SQL_METRICS[m]} AS "{m}"' for m in metrics]
    grouping = " GROUP BY " + ",".join(str(i+1) for i in range(len(dimensions))) if dimensions else ""
    order = " ORDER BY " + ",".join(str(i+1) for i in range(len(dimensions))) if dimensions else ""
    rows = [dict(r) for r in conn.execute(f"SELECT {','.join(selected)} {BASE} WHERE {where}{grouping}{order}", params).fetchall()]
    for row in rows:
        for key in metrics:
            row[key] = round(float(row[key]), 6) if row[key] is not None else None
        if "porcentaje_descuento" in row and row["porcentaje_descuento"] is not None:
            row["porcentaje_descuento"] = float(row["porcentaje_descuento"])
    return rows


def previous_month(value):
    import calendar
    year, month = (value.year-1, 12) if value.month == 1 else (value.year, value.month-1)
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _growth(current, previous):
    return 100*(current-previous)/previous if current is not None and previous not in (None, 0) else None


def previous_window(start, end):
    """A full month compares to the full prior month, including unequal lengths."""
    import calendar
    lo, hi = previous_month(start), previous_month(end)
    if start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1]:
        hi = date(hi.year, hi.month, calendar.monthrange(hi.year, hi.month)[1])
    return lo.isoformat(), hi.isoformat()


def _label(value, dimension):
    if dimension == "dia_semana": return ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")[int(value)-1]
    return "N/D" if value is None else str(value)


def chart_from_rows(item, rows, number):
    dims, metrics = item["dimensions"], item["metrics"]
    chart = {"type": item["type"], "title": item["title"], "description": item["purpose"],
             "orientation": item.get("orientation", "vertical"), "source": "PostgreSQL RopaV · public",
             "objective_visual": True, "objective_id": number, "value_format": FORMATS[metrics[0]],
             "semantic": {"modelo": "ventas", "dimensiones": dims, "metrica": metrics[0], "metricas": metrics,
                          "formulas": {m: FORMULAS[m] for m in metrics}},
             "labels": [], "datasets": [], "colors": COLORS}
    if item["type"] in ("table", "matrix"):
        chart["columns"] = [{"key": d, "label": DIM_LABELS[d], "format": "text"} for d in dims]
        chart["columns"] += [{"key": m, "label": LABELS[m], "format": FORMATS[m]} for m in metrics]
        chart["rows"] = rows
        if item["type"] == "matrix":
            series = list(dict.fromkeys(row[dims[1]] for row in rows))
            lookup = {(r[dims[0]], r[dims[1]]): r for r in rows}
            chart["columns"] = [{"key": dims[0], "label": DIM_LABELS[dims[0]], "format": "text"}]
            chart["columns"] += [{"key": f"s{i}_{m}", "label": f"{s} · {LABELS[m]}", "format": FORMATS[m]} for i,s in enumerate(series) for m in metrics]
            chart["rows"] = [{dims[0]: label, **{f"s{i}_{m}": lookup.get((label,s), {}).get(m)
                               for i,s in enumerate(series) for m in metrics}}
                             for label in dict.fromkeys(r[dims[0]] for r in rows)]
        return chart
    if item["type"] == "treemap":
        chart["nodes"] = [{"group": str(r[dims[0]]), "label": str(r[dims[1]]), "value": r[metrics[0]]} for r in rows]
        return chart
    labels = list(dict.fromkeys(r[dims[0]] for r in rows))
    chart["labels"] = [_label(v, dims[0]) for v in labels]
    if len(dims) == 2:
        series = list(dict.fromkeys(r[dims[1]] for r in rows))
        lookup = {(r[dims[0]], r[dims[1]]): r[metrics[0]] for r in rows}
        chart["datasets"] = [{"label": str(s), "values": [lookup.get((v,s)) for v in labels], "color": COLORS[i%len(COLORS)]} for i,s in enumerate(series)]
    else:
        chart["datasets"] = [{"label": LABELS[m], "values": [r[m] for r in rows], "color": COLORS[i%len(COLORS)]} for i,m in enumerate(metrics)]
    chart["colors"] = [COLORS[i%len(COLORS)] for i in range(max(len(labels), len(chart["datasets"]))) ]
    return chart


def build_objective_dashboard(number, filters=None):
    if number not in OBJECTIVES: raise ValueError("Objetivo no válido (1–6)")
    definition, filters = OBJECTIVES[number], validate_filters(filters)
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        where, values = _where(filters)
        bounds = dict(conn.execute(f"SELECT MIN(v.fecha_venta::date) desde, MAX(v.fecha_venta::date) hasta {BASE} WHERE {where}", values).fetchone())
        kpis = _query(conn, [], [m for m in definition["kpis"] if m != "crecimiento"], filters)[0]
        cache, charts = {}, []
        previous = None
        start, end = filters.get("desde") or bounds["desde"], filters.get("hasta") or bounds["hasta"]
        if number == 2 and start and end:
            start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
            previous_start, previous_end = previous_window(start, end)
            previous_filters = {**filters, "desde": previous_start, "hasta": previous_end}
            previous = _query(conn, [], ["ingresos"], previous_filters)[0]["ingresos"]
            kpis["crecimiento"] = _growth(kpis["ingresos"], previous)
        for item in definition["charts"]:
            base_metrics = [m for m in item["metrics"] if m != "crecimiento"]
            key = (tuple(item["dimensions"]), tuple(base_metrics))
            if key not in cache: cache[key] = _query(conn, item["dimensions"], base_metrics, filters)
            rows = deepcopy(cache[key])
            if "crecimiento" in item["metrics"]:
                for row in rows:
                    import calendar
                    month_start = date.fromisoformat(row["mes"]+"-01")
                    month_end = date(month_start.year, month_start.month, calendar.monthrange(month_start.year, month_start.month)[1])
                    lo, hi = max(month_start, start), min(month_end, end)
                    previous_start, previous_end = previous_window(lo, hi)
                    prior_filters = {**filters, "desde": previous_start, "hasta": previous_end}
                    prior = _query(conn, [], ["ingresos"], prior_filters)[0]["ingresos"]
                    row["crecimiento"] = _growth(row["ingresos"], prior)
            charts.append(chart_from_rows(item, rows, number))
    used = list(dict.fromkeys(definition["kpis"] + [m for i in definition["charts"] for m in i["metrics"]]))
    warnings = list(definition["warnings"])
    if number == 2:
        warnings.append("El KPI de crecimiento compara todo el periodo seleccionado con ese periodo desplazado un mes. La tabla calcula cada mes por separado. Un mes sin registros no se rellena con cero.")
    warnings += [SALE_CRITERION,
        "Recreación funcional, no copia píxel a píxel. Fórmulas del PBIT aplicadas a datos actuales de public; la plantilla no contiene datos. Se excluyen canceladas aunque las medidas DAX originales no lo hacen explícitamente.",
        "Margen total = subtotal menos costo de producto, no beneficio neto. Se usa el costo actual disponible; no incluye todos los gastos operativos."]
    if not bounds["desde"]: warnings.insert(0, "No hay ventas no canceladas con estos filtros; N/D indica un agregado sin base, no un cero inventado.")
    return {"title": definition["title"], "subtitle": f"Objetivo {number} · {start or 'Sin datos'} a {end or 'Sin datos'} · PostgreSQL RopaV (public)",
            "objective_id": number, "objective": definition["objective"], "filters": filters, "warnings": warnings,
            "kpis": [{"label": LABELS[m], "value": kpis.get(m), "format": FORMATS[m]} for m in definition["kpis"]],
            "charts": charts, "measure_definitions": {LABELS[m]: FORMULAS[m] for m in used},
            "source": "PostgreSQL RopaV · public", "reference": "RopaVacana_App.pbit"}
