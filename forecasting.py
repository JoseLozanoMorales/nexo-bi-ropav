"""Pronósticos locales, reproducibles y explícitamente no causales."""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math

from semantic_analytics import query_semantic, LABELS, CURRENCY, PALETTE
from api_errors import SafeRequestError

ADDITIVE={"ingresos","utilidad","unidades","transacciones","clientes"}

def _next_month(value):
    year,month=map(int,value.split("-")); month+=1
    if month==13: year,month=year+1,1
    return f"{year:04d}-{month:02d}"

def _linear(values,horizon):
    n=len(values); xs=list(range(n)); xbar=sum(xs)/n; ybar=sum(values)/n
    denominator=sum((x-xbar)**2 for x in xs)
    slope=sum((x-xbar)*(y-ybar) for x,y in zip(xs,values))/denominator if denominator else 0
    intercept=ybar-slope*xbar
    residuals=[y-(intercept+slope*x) for x,y in zip(xs,values)]
    rmse=math.sqrt(sum(r*r for r in residuals)/max(1,n-2)) if n>2 else 0
    forecasts=[]
    for step in range(horizon):
        value=intercept+slope*(n+step); spread=1.96*rmse*math.sqrt(1+(step+1)/max(1,n))
        forecasts.append((value,value-spread,value+spread))
    return forecasts,slope,rmse

def forecast(measure="ingresos",segment=None,filters=None,horizon=3):
    if measure not in LABELS: raise ValueError("Métrica predictiva no permitida")
    if segment=="mes": segment=None
    dimensions=["mes"]+([segment] if segment else [])
    history=query_semantic(dimensions,measure,filters or {},500)
    if len(history['datos'])>=500:raise SafeRequestError('La historia supera el límite de extracción. Reduce el periodo o los segmentos antes de pronosticar.')
    buckets=defaultdict(list)
    for row in history["datos"]:
        buckets[str(row.get("serie","Total"))].append((str(row["etiqueta"]),float(row["valor"])))
    if not buckets: raise ValueError("No hay historia mensual para calcular el pronóstico")
    start=min(p for items in buckets.values() for p,_ in items)
    end=max(p for items in buckets.values() for p,_ in items)
    calendar=[]; cursor=start
    while cursor<=end:
        calendar.append(cursor);cursor=_next_month(cursor)
    horizon=int(horizon)
    if not 1<=horizon<=24: raise SafeRequestError("El pronóstico admite entre 1 y 24 meses; no se ha cambiado el horizonte solicitado.")
    rows=[]; diagnostics=[]
    for series,items in buckets.items():
        items=sorted(items); observed=dict(items)
        if measure in ('margen','ticket_promedio') and any(p not in observed for p in calendar):raise SafeRequestError('Faltan meses para calcular una tendencia fiable de porcentajes o promedios. Reduce el periodo o cambia la métrica.')
        values=[observed.get(p,0) for p in calendar]
        if len(values)<3: continue
        estimates,slope,rmse=_linear(values[-24:],horizon); period=end
        for point,(value,lower,upper) in enumerate(estimates,1):
            period=_next_month(period)
            if measure in ADDITIVE and measure!='utilidad': value,lower,upper=max(0,value),max(0,lower),max(0,upper)
            if measure=="margen": value,lower,upper=min(100,max(0,value)),min(100,max(0,lower)),min(100,max(0,upper))
            rows.append({"periodo":period,"serie":series,"estimado":round(value,2),"inferior":round(lower,2),"superior":round(upper,2)})
        diagnostics.append({"serie":series,"observaciones":len(values),"pendiente_mensual":round(slope,2),"rmse":round(rmse,2)})
    if not rows: raise ValueError("Se requieren al menos tres meses históricos por serie para pronosticar")
    return {"fuente":"PostgreSQL RopaV","tipo":"pronostico","metrica":measure,"dimension_segmento":segment,
            "horizonte_meses":horizon,"filtros":dict(filters or {}),"datos":rows,"diagnostico":diagnostics,
            "metodo":"Tendencia lineal por mínimos cuadrados sobre hasta 24 observaciones mensuales; intervalo aproximado de 95% basado en el error residual.",
            "limitacion":"Es una proyección estadística descriptiva, no una garantía ni una estimación causal. Meses sin registros se asumen sin actividad para conteos e importes; una carga incompleta invalidaría esa suposición. No incorpora campañas, inventario futuro ni factores externos."}

def forecast_chart(result,kind="line"):
    rows=result["datos"]; periods=list(dict.fromkeys(r["periodo"] for r in rows)); series=list(dict.fromkeys(r["serie"] for r in rows))
    lookup={(r["periodo"],r["serie"]):r for r in rows}; colors=PALETTE[:max(2,len(series))]
    datasets=[{"label":s,"values":[lookup.get((p,s),{}).get("estimado",0) for p in periods],"color":colors[i%len(colors)]} for i,s in enumerate(series)]
    metric=result["metrica"]; fmt="moneda" if metric in CURRENCY else "porcentaje" if metric=="margen" else "numero"
    title=f"Pronóstico de {LABELS[metric].lower()}"+(f" por {result['dimension_segmento']}" if result.get("dimension_segmento") else "")
    base={"type":kind,"orientation":"vertical","title":title,"description":result["metodo"]+" "+result["limitacion"],"labels":periods,
          "datasets":datasets,"colors":colors,"value_format":fmt,"source":"PostgreSQL RopaV · proyección local","filters":result["filtros"],
          "forecast":{"method":result["metodo"],"limitation":result["limitacion"],"horizon_months":result["horizonte_meses"],"intervals":rows},
          "semantic":{"modelo":"pronostico_ventas","dimensiones":["mes"]+([result["dimension_segmento"]] if result.get("dimension_segmento") else []),"metrica":metric}}
    final=periods[-1]; final_rows=[r for r in rows if r["periodo"]==final]
    if kind in ("pie","doughnut"):
        if not result.get("dimension_segmento") or metric not in ADDITIVE: raise ValueError("Pastel y dona predictivos requieren una dimensión y una métrica aditiva")
        base.update(labels=[r["serie"] for r in final_rows],datasets=[{"label":f"Estimado {final}","values":[r["estimado"] for r in final_rows],"color":colors[0]}])
    elif kind=="scatter":
        base.update(points=[{"label":r["serie"],"x":r["inferior"],"y":r["estimado"],"superior":r["superior"]} for r in final_rows],x_label="Límite inferior (95%)",y_label="Estimación",datasets=[{"label":final,"color":colors[0]}])
    elif kind=="heatmap":
        base.update(x_labels=periods,y_labels=series,matrix=[[lookup.get((p,s),{}).get("estimado",0) for p in periods] for s in series],datasets=[],colors=["#e8f7f5","#11a99a"])
    elif kind=="stacked_bar":
        base.update(stacks=[{"label":"Pronóstico","datasets":datasets}],datasets=[])
    elif kind=="pareto":
        ordered=sorted(final_rows,key=lambda r:r["estimado"],reverse=True); total=sum(r["estimado"] for r in ordered); running=0; cumulative=[]
        for row in ordered: running+=row["estimado"]; cumulative.append(round(100*running/total,2) if total else 0)
        base.update(labels=[r["serie"] for r in ordered],datasets=[{"label":"Estimado","values":[r["estimado"] for r in ordered],"color":colors[0],"axis":"left"},{"label":"% acumulado","values":cumulative,"color":colors[1],"axis":"right"}])
    elif kind in ("histogram","boxplot"):
        values=sorted(r["estimado"] for r in final_rows)
        if len(values)<2: raise ValueError(f"{kind} predictivo requiere varias series comparables")
        if kind=="boxplot":
            def q(p):
                pos=(len(values)-1)*p; lo=int(pos); hi=min(lo+1,len(values)-1); return values[lo]+(values[hi]-values[lo])*(pos-lo)
            base.update(labels=[final],boxes=[{"label":final,"min":values[0],"q1":round(q(.25),2),"median":round(q(.5),2),"q3":round(q(.75),2),"max":values[-1],"outliers":[],"count":len(values)}],datasets=[])
        else:
            bins=min(10,max(2,round(math.sqrt(len(values))))); low,high=min(values),max(values); width=(high-low)/bins or 1; counts=[0]*bins
            for value in values: counts[min(int((value-low)/width),bins-1)]+=1
            labels=[f"{low+i*width:.2f}–{low+(i+1)*width:.2f}" for i in range(bins)]
            base.update(type="histogram",labels=labels,datasets=[{"label":"Número de series","values":counts,"color":colors[0]}],prediction_visual="histogram")
    return base
