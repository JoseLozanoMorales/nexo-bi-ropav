"""Calendar-normalized weekly counts; no inference about basket value."""
from datetime import date, timedelta
import json

SALE_CRITERION = "Ventas no canceladas: se excluye estado_venta = 'Cancelada'. Transacciones cuenta id_venta distintos, no líneas de detalle."
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def weekly_summary(rows, dimensions, start, end):
    start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
    if end < start:
        raise ValueError("El final del periodo es anterior al inicio")
    counts = [0] * 7
    for offset in range((end - start).days + 1):
        counts[(start + timedelta(days=offset)).weekday()] += 1
    day_key = "etiqueta" if dimensions[0] == "dia_semana" else "serie"
    group_key = "serie" if day_key == "etiqueta" else "etiqueta"
    groups = {}
    for row in rows:
        day = DAYS.index(str(row[day_key]).strip())
        group = str(row[group_key]) if len(dimensions) == 2 else "Todos los canales"
        values = groups.setdefault(group, [0, 0])
        values[0 if day < 5 else 1] += row["valor"]
    denominators = [sum(counts[:5]), sum(counts[5:])]
    return {"desde": start.isoformat(), "hasta": end.isoformat(),
            "dias_laborables": denominators[0], "dias_fin_semana": denominators[1],
            "nota": "Días calendario inclusivos, incluidos días sin ventas. Laborables significa lunes a viernes, sin ajuste por festivos ni horarios de apertura.",
            "grupos": [{"grupo": group, "transacciones": sum(values),
                        "laborables": values[0], "fin_semana": values[1],
                        "promedio_laborable": values[0] / denominators[0] if denominators[0] else None,
                        "promedio_fin_semana": values[1] / denominators[1] if denominators[1] else None}
                       for group, values in sorted(groups.items())]}


def weekly_text(result, include_criterion=False):
    summary = result["estacionalidad_semanal"]
    day_count = lambda n: f"{n} día" + ("s" if n != 1 else "")
    lines = ["Estacionalidad semanal — transacciones.",
             f"Periodo: {summary['desde']} a {summary['hasta']}. Fuente: PostgreSQL RopaV (esquema public).",
             "Filtros: " + json.dumps(result.get("filtros", {}), ensure_ascii=False),
             f"Denominadores: {day_count(summary['dias_laborables'])} de lunes a viernes y {day_count(summary['dias_fin_semana'])} de sábado a domingo. {summary['nota']}"]
    if include_criterion: lines.append(SALE_CRITERION)
    for group in summary["grupos"]:
        average = lambda value: "No aplicable (sin días en el periodo)" if value is None else f"{value:.3f} transacciones/día"
        noun = 'transacción' if group['transacciones'] == 1 else 'transacciones'
        lines.append(f"{group['grupo']}: {group['transacciones']:g} {noun}.\n"
                     f"- Lunes–viernes: {group['laborables']:g}; promedio: {average(group['promedio_laborable'])}.\n"
                     f"- Sábado–domingo: {group['fin_semana']:g}; promedio: {average(group['promedio_fin_semana'])}.")
    if not summary["grupos"]:
        lines.append("No hay transacciones con estos filtros.")
    lines.append("Estos resultados describen frecuencia de transacciones, no ticket promedio, importe gastado ni afluencia de visitantes. No permiten concluir diferencias en esas métricas.")
    return "\n\n".join(lines)
