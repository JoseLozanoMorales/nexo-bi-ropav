"""Read saved visual data locally. Never query, regenerate or mutate a visual."""
import math
import re
import unicodedata
import json


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower()) if not unicodedata.combining(c))


def interpretation_request(messages):
    text = plain(next((m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'), ''))
    visual_words = r'grafic\w*|dashboard\w*|tablero\w*|visualiza\w*|histograma\w*|boxplot\w*|pareto\w*|mapa de calor|dona\w*|pastel\w*'
    asks = bool(re.search(r'\b(interpreta\w*|explica\w*|conclusiones?|que significa\w*|que (?:se )?(?:observa|concluye|entiende)\w*)\b', text))
    asks |= bool(re.search(r'\b(analiza|analisis|que ves|que muestra|que destaca|por que)\b', text) and re.search(visual_words, text))
    asks |= bool(re.search(r'\b(que|cuales|como)\b.*\b(metricas?|medidas?|formulas?|filtros?)\b', text))
    asks |= bool(re.search(r'\b(?:analizalo|analizala|analiza (?:eso|esto))\b',text))
    # An explanation about how something was generated is not an instruction to generate it.
    actions = re.sub(r'\b(?:no|sin)\s+(?:vuelvas a\s+)?(?:gener\w*|cre\w*|dibuj\w*|repit\w*|cambi\w*|actualiz\w*)\b', '', text)
    modifies = re.search(r'(?:^|[.!?;:,]\s*|\b(?:y|tambien|por favor|ahora|puedes|quiero que)\s+)(genera|generame|generalo|crea|creame|crealo|dibuja|convierte|cambia|sustituye|reemplaza|actualiza|filtra|aplica|quita|agrega|anade)\b', actions)
    modifies = modifies or re.search(r'\b(?:quiero|necesito|dame|hazme|haz|muestrame)\s+(?:un|una|otro|otra|nuevo|nueva)\b[^.!?;]*(?:'+visual_words+r')',actions)
    return asks and not modifies


KINDS = {
    'histogram': r'histogramas?', 'boxplot': r'boxplots?|cajas?(?: y)? bigotes',
    'heatmap': r'mapas? de calor|heatmaps?', 'pareto': r'paretos?',
    'scatter': r'dispersion|scatter', 'doughnut': r'donas?|donuts?|anillos?',
    'pie': r'pastel(?:es)?|tortas?', 'stacked_bar': r'apilad\w*',
    'bar': r'barras?|columnas?', 'line': r'lineas?', 'area': r'areas?',
    'treemap': r'treemaps?|mapas? de arbol', 'matrix': r'matri(?:z|ces)',
    'table': r'tablas?',
}


def select_visual(messages):
    text = plain(messages[-1].get('content', ''))
    wants_dashboard = bool(re.search(r'\b(dashboards?|tableros?|paneles?)\b', text))
    requested = next((kind for kind, pattern in KINDS.items() if re.search(r'\b(?:'+pattern+r')\b', text)), None)
    if requested or re.search(r'\b(?:grafico|primer|segundo|tercer|cuarto|quinto|sexto)\b',text):
        wants_dashboard = False
    for message in reversed(messages[:-1]):
        if message.get('role') != 'assistant':
            continue
        dashboard = message.get('dashboard')
        chart = message.get('chart')
        if wants_dashboard:
            if isinstance(dashboard, dict):
                return 'dashboard', dashboard, None
            continue
        candidates = dashboard.get('charts', []) if isinstance(dashboard, dict) else [chart] if isinstance(chart, dict) else []
        candidates = [c for c in candidates if isinstance(c, dict)]
        if not candidates:
            if isinstance(dashboard, dict) and not requested and not re.search(r'\b(grafico|panel|primer|segundo|tercer|cuarto|quinto|sexto)\b',text):
                return 'dashboard', dashboard, None
            continue
        ordinal = re.search(r'\b(?:grafico|panel)\s*(\d+)\b', text)
        index = int(ordinal.group(1))-1 if ordinal else next((i for i, word in enumerate(('primer','segundo','tercer','cuarto','quinto','sexto')) if re.search(r'\b'+word+r'(?:o)?\b', text)), None)
        if index is not None:
            if 0 <= index < len(candidates):
                return 'chart', candidates[index], dashboard
            return 'missing', None, None
        named = [c for c in candidates if c.get('title') and plain(c['title']) in text]
        matches = named or ([c for c in candidates if c.get('type') == requested] if requested else candidates)
        if not matches:
            continue
        if len(matches) == 1:
            return 'chart', matches[0], dashboard
        if requested or re.search(r'\b(?:el|ese|este|un) grafico\b', text):
            return 'ambiguous', [c.get('title','Gráfico') for c in matches], None
        if isinstance(dashboard, dict):
            return 'dashboard', dashboard, None
    return 'missing', None, None


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def formatted(value, fmt='number'):
    v = number(value)
    if v is None: return 'N/D'
    return ('USD ' if fmt in ('currency','moneda') else '') + f'{v:,.2f}'.rstrip('0').rstrip('.') + ('%' if fmt=='percent' else '')


def extrema(pairs, fmt='number'):
    valid = [(str(label), number(value)) for label, value in pairs if number(value) is not None]
    if not valid:
        return 'No hay valores numéricos válidos para interpretar.'
    high, low = max(v for _,v in valid), min(v for _,v in valid)
    leaders = [label for label,v in valid if v==high]
    names = '; '.join(leaders[:6]) + (' (y otros)' if len(leaders)>6 else '')
    if high == low:
        return f'Los {len(valid)} valores válidos son iguales: {formatted(high,fmt)}.'
    return f'Máximo: {names}, {formatted(high,fmt)}'+(' cada uno (empate)' if len(leaders)>1 else '')+f'. Mínimo: {formatted(low,fmt)}.'


def chart_findings(chart):
    kind = chart.get('type')
    labels, datasets = chart.get('labels') or [], chart.get('datasets') or []
    fmt = chart.get('value_format','number')
    lines = []
    if kind == 'boxplot':
        for box in chart.get('boxes') or []:
            q1,q3 = number(box.get('q1')),number(box.get('q3'))
            lines.append(f"{box.get('label','Grupo')}: mediana {formatted(box.get('median'),fmt)}; 50% central entre {formatted(q1,fmt)} y {formatted(q3,fmt)}; {len(box.get('outliers') or [])} valores atípicos mostrados.")
        lines.append('Un valor atípico no implica por sí solo error ni fraude. La caja describe dispersión, no ventas totales.')
    elif kind == 'scatter':
        points = [p for p in chart.get('points') or [] if number(p.get('x')) is not None and number(p.get('y')) is not None]
        lines.append(f'{len(points)} puntos válidos mostrados.')
        lines.append(str(chart.get('x_label','Eje X'))+': '+extrema([(p.get('label','Punto'),p['x']) for p in points]))
        lines.append(str(chart.get('y_label','Eje Y'))+': '+extrema([(p.get('label','Punto'),p['y']) for p in points],fmt))
        lines.append('Estos extremos no demuestran correlación ni causalidad entre las variables.')
    elif kind == 'heatmap':
        pairs = [(str(y)+' / '+str(x),row[i]) for y,row in zip(chart.get('y_labels') or [],chart.get('matrix') or []) for i,x in enumerate(chart.get('x_labels') or labels) if i<len(row)]
        lines.append(extrema(pairs,fmt))
        lines.append('Cada celda corresponde al cruce de sus dos ejes; el color representa la magnitud, no una explicación de sus causas.')
    elif kind == 'treemap':
        nodes = chart.get('nodes') or []
        lines.append(extrema([(str(n.get('group',''))+' / '+str(n.get('label','')),n.get('value')) for n in nodes],fmt))
        lines.append('El área representa el valor de los elementos mostrados, no su crecimiento en el tiempo.')
    elif kind in ('table','matrix'):
        rows, cols = chart.get('rows') or [], chart.get('columns') or []
        dimensions = [c['key'] for c in cols if c.get('format')=='text']
        lines.append(f'{len(rows)} filas mostradas.')
        for col in cols:
            if col.get('format')!='text':
                pairs = [(' / '.join(str(r.get(k,'')) for k in dimensions) or f'Fila {i+1}', r.get(col['key'])) for i,r in enumerate(rows)]
                lines.append(str(col.get('label',col['key']))+': '+extrema(pairs,col.get('format','number')))
        lines.append('No se suman filas o porcentajes automáticamente: podrían contener totales o métricas no aditivas.')
    elif kind == 'stacked_bar':
        for stack in chart.get('stacks') or []:
            for dataset in stack.get('datasets') or []:
                lines.append(str(stack.get('label','Grupo'))+' — '+str(dataset.get('label','Serie'))+': '+extrema(zip(labels,dataset.get('values') or []),fmt))
        lines.append('Los segmentos se analizan por separado; no se confunden con categorías o periodos distintos.')
    elif kind == 'pareto':
        if datasets:
            lines.append(extrema(zip(labels,datasets[0].get('values') or []),fmt))
        if len(datasets)>1:
            cumulative = datasets[1].get('values') or []
            reached = next((i for i,v in enumerate(cumulative) if number(v) is not None and number(v)>=80),None)
            if reached is not None:
                lines.append(f'Los primeros {reached+1} de {len(labels)} elementos alcanzan {formatted(cumulative[reached],"percent")} del acumulado mostrado.')
        lines.append('El porcentaje se refiere sólo a los elementos mostrados, no necesariamente a todo el catálogo.')
    elif kind in ('bar','line','area','pie','doughnut'):
        for dataset in datasets:
            values = dataset.get('values') or []
            if len(values)!=len(labels):
                lines.append('La serie no tiene una correspondencia completa entre etiquetas y valores.')
                continue
            series_fmt = 'percent' if dataset.get('axis')=='right' and chart.get('secondary_axis') else fmt
            lines.append(str(dataset.get('label','Serie'))+': '+extrema(zip(labels,values),series_fmt))
            if any(number(v) is None for v in values):
                lines.append('Hay valores ausentes o no válidos; no se interpretan como cero.')
            if kind in ('line','area') and len(values)>1 and number(values[0]) is not None and number(values[-1]) is not None:
                delta=number(values[-1])-number(values[0])
                lines.append(f'Del primer punto ({labels[0]}) al último ({labels[-1]}), el cambio es {formatted(delta)}'+(' puntos porcentuales.' if series_fmt=='percent' else ' en las unidades de esa serie.'))
                lines.append('El cambio entre extremos no implica una subida o bajada continua.')
            if kind in ('pie','doughnut'):
                numeric=[number(v) for v in values]
                metric=(chart.get('semantic') or {}).get('metrica')
                if any(v is None or v<0 for v in numeric) or metric in ('margen','ticket_promedio','clientes') or fmt=='percent':
                    lines.append('No es válido deducir participaciones aditivas de esta serie.')
                elif sum(numeric)>0:
                    total=sum(numeric)
                    lines.append('Participación sobre lo mostrado: '+'; '.join(f'{label}: {v/total*100:.1f}%' for label,v in zip(labels,numeric))+'.')
                else:
                    lines.append('El total es cero; no hay porcentajes de participación definidos.')
    else:
        lines.append('No hay un análisis local disponible para este formato. No se ha regenerado ni sustituido la visualización.')
    return '\n'.join(lines) if lines else 'La visualización no contiene datos suficientes para interpretarla.'


def context_text(spec, parent=None):
    filters = spec.get('filters',spec.get('filtros'))
    if filters is None and isinstance(parent,dict):filters=parent.get('filters')
    lines = ['Filtros guardados: '+json.dumps(filters,ensure_ascii=False,sort_keys=True)] if filters is not None else ['El gráfico guardado no contiene metadatos de filtros; no se deducen a partir del título.']
    lines.append('Fuente: '+str(spec.get('source') or 'PostgreSQL RopaV')+'.')
    return '\n'.join(lines)


def interpret_selected(kind, spec, parent=None, histogram_reader=None):
    if kind=='missing':
        return 'No encuentro la visualización solicitada en este chat. Indica cuál quieres interpretar; no he generado otra.'
    if kind=='ambiguous':
        return 'Hay varios gráficos que coinciden. ¿Cuál quieres interpretar?\n'+'\n'.join(f'{i+1}. {title}' for i,title in enumerate(spec))
    if kind=='dashboard':
        parts=['Interpretación del dashboard guardado: '+str(spec.get('title','Dashboard')),context_text(spec)]
        if spec.get('kpis'):
            parts.append('Indicadores: '+'; '.join(str(k.get('label','Indicador'))+': '+formatted(k.get('value'),k.get('format','number')) for k in spec['kpis'])+'.')
        for i,chart in enumerate(spec.get('charts') or []):
            parts.append(f'{i+1}. '+str(chart.get('title','Gráfico'))+'\n'+read_chart(chart,histogram_reader))
        if spec.get('warnings'):parts.append('Límites del dashboard:\n'+'\n'.join(spec['warnings']))
        parts.append('No se suman los gráficos entre sí: pueden representar las mismas ventas con distintos desgloses.')
    else:
        parts=['Interpretación del gráfico guardado: '+str(spec.get('title','Gráfico')),read_chart(spec,histogram_reader),context_text(spec,parent)]
    parts.append('Se usan exclusivamente los datos guardados; no se volvió a consultar ni a generar la visualización. Las cifras describen lo mostrado y no demuestran causas.')
    return '\n\n'.join(parts)


def read_chart(chart, histogram_reader):
    if chart.get('type')=='histogram' and histogram_reader:
        return histogram_reader(chart) or 'El histograma guardado carece de frecuencias válidas; no se inventará una distribución.'
    return chart_findings(chart)
