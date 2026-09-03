"""Normaliza la posición de detalles técnicos en respuestas conversacionales."""
import re

TECHNICAL = re.compile(
    r"^\s*(?:consulta\s*\(|consulta\s+(?:realizada|t[eé]cnica|y\s+par[aá]metros)|"
    r"filtros?(?:\s+(?:usados|exactos|aplicados))?|par[aá]metros?(?:\s+de\s+la\s+consulta)?|"
    r"detalles?\s*\(\s*filtros?|indicadores?\s*\(\s*copiado)", re.I)

def parameters_last(text):
    """Move self-contained technical paragraphs to the end, preserving content."""
    if not isinstance(text,str) or not text.strip(): return text
    blocks=re.split(r"\n\s*\n",text.strip())
    narrative=[]; technical=[]; following=False
    for block in blocks:
        heading=re.sub(r'^\s*(?:#{1,6}\s*)?(?:\*\*)?', '', block)
        if TECHNICAL.match(heading):
            technical.append(block); following=True
        elif following and re.match(r'^\s*(?:\{|\[|```|[-*]\s)',block):
            technical.append(block)
        else:
            narrative.append(block); following=False
    if not technical or not narrative: return text
    return "\n\n".join(narrative+technical)
