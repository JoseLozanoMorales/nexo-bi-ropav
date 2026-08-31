"""No-network regressions: every visual's interpretation is a read-only terminal route."""
import unittest
from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import patch
import ai_chat
from visual_interpretation import chart_findings, select_visual


def fixtures():
    base=dict(title='Ingresos por canal',source='Prueba local',value_format='currency',
              filters={'desde':'2025-01-01','hasta':'2025-12-31','region':'Costa'},
              labels=['A','B'],datasets=[dict(label='Ingresos',values=[80,20])])
    charts=[dict(base,type=kind) for kind in ('bar','line','area','pie','doughnut')]
    charts += [dict(base,type='bar',orientation='horizontal'),
               dict(base,type='histogram',labels=['0–10','10–20']),
               dict(base,type='boxplot',boxes=[dict(label='A',q1=10,median=15,q3=20,min=5,max=25,outliers=[35])]),
               dict(base,type='scatter',points=[dict(label='A',x=10,y=80),dict(label='B',x=5,y=20)],x_label='Unidades',y_label='Ingresos'),
               dict(base,type='heatmap',x_labels=['Ene','Feb'],y_labels=['A','B'],matrix=[[80,20],[30,10]]),
               dict(base,type='stacked_bar',stacks=[dict(label='Grupo',datasets=base['datasets'])]),
               dict(base,type='pareto',datasets=base['datasets']+[dict(label='% acumulado',values=[80,100],axis='right')]),
               dict(base,type='line',secondary_axis=True,datasets=base['datasets']+[dict(label='Margen',axis='right',values=[10,20])]),
               dict(base,type='treemap',objective_visual=True,nodes=[dict(group='Grupo',label='A',value=80),dict(group='Grupo',label='B',value=20)]),
               dict(base,type='bar',objective_visual=True,datasets=[dict(label='Variación',values=[-10,20])])]
    charts += [dict(base,type=kind,objective_visual=True,columns=[dict(key='name',label='Nombre',format='text'),dict(key='value',label='Ingresos',format='currency')],rows=[dict(name='A',value=80),dict(name='B',value=20)]) for kind in ('table','matrix')]
    return charts


class VisualInterpretation(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack()
        for name in ('OpenAI','mcp_request','_dashboard_plan','build_dashboard','_planned_dashboard','query_semantic'):
            self.stack.enter_context(patch.object(ai_chat,name,side_effect=AssertionError('Interpretar no debe ejecutar '+name)))
        self.addCleanup(self.stack.close)

    def response(self,visual,prompt='Interpreta lo que se ve'):
        key='dashboard' if 'charts' in visual else 'chart'
        messages=[dict(role='assistant',content='Resultado guardado',**{key:visual}),dict(role='user',content=prompt)]
        original=deepcopy(messages)
        response=ai_chat.ask(messages)
        self.assertEqual(messages,original)
        self.assertFalse(response.get('chart'))
        self.assertFalse(response.get('dashboard'))
        self.assertEqual(response['tools'],[])
        self.assertEqual(response['model'],'Análisis local')
        return response['text']

    def test_all_17_variants(self):
        for chart in fixtures():
            with self.subTest(type=chart['type'],objective=chart.get('objective_visual')):
                text=self.response(chart)
                self.assertIn('Interpretación',text)
                self.assertNotIn('No hay un análisis local disponible',text)
                self.assertIn('Costa',text)

    def test_dashboard_all_panels(self):
        for objective in (False,True):
            dashboard=dict(title='Ventas y clientes',filters={'region':'Costa'},kpis=[dict(label='Ingresos',value=100,format='currency')],charts=fixtures(),warnings=['Datos históricos, no predicción.'])
            if objective:dashboard.update(objective_id=1,measure_definitions={'Ingresos':'SUM(subtotal)'})
            text=self.response(dashboard,'Interpreta este dashboard')
            self.assertIn('17.',text)
            self.assertIn('Costa',text)
            self.assertIn('Datos históricos',text)
            self.assertIn('No se suman los gráficos',text)

    def test_newest_dashboard_not_old_histogram(self):
        messages=[dict(role='assistant',content='',chart=fixtures()[6]),
                  dict(role='assistant',content='',dashboard=dict(title='El reciente',charts=fixtures()[:2])),
                  dict(role='user',content='Explícamelo')]
        response=ai_chat.ask(messages)
        self.assertIn('El reciente',response['text'])
        self.assertNotIn('intervalo con mayor frecuencia',response['text'])

    def test_explicit_panel_and_ambiguity(self):
        charts=fixtures()[:2]
        charts[0]['title']='Ranking por canal';charts[1]['title']='Evolución mensual'
        dash=dict(title='Dashboard',charts=charts)
        self.assertIn('Evolución mensual',self.response(dash,'Explica el segundo gráfico del dashboard'))
        self.assertIn('Cuál',self.response(dash,'Interpreta ese gráfico'))
        self.assertIn('no he generado',self.response(dash,'Explica el gráfico 8'))

    def test_metadata(self):
        chart=fixtures()[0];chart['semantic']=dict(metrica='ingresos',dimensiones=['canal'])
        text=self.response(chart,'Qué filtros y métricas se usaron en este gráfico')
        self.assertIn('Costa',text);self.assertIn('ingresos',text)
        dash=dict(title='Dashboard',charts=[chart],filters={'region':'Sierra'},kpis=[])
        self.assertIn('Sierra',self.response(dash,'Explica los filtros del dashboard'))

    def test_invalid_empty_unknown(self):
        self.assertIn('No hay valores numéricos',self.response(dict(type='bar',labels=['A'],datasets=[dict(values=[None])])))
        self.assertIn('no se interpretan como cero',self.response(dict(type='bar',labels=['A','B'],datasets=[dict(values=[None,2])])))
        self.assertIn('No hay un análisis local',self.response(dict(type='nuevo_tipo')))
        answer=ai_chat.ask([dict(role='user',content='Interpreta el histograma')])
        self.assertIn('No encuentro',answer['text'])

    def test_statistics_do_not_sum_nonadditive_metrics(self):
        ch=fixtures()[4];ch['semantic']={'metrica':'margen'};ch['value_format']='percent'
        self.assertIn('No es válido',self.response(ch))
        ch=fixtures()[12]
        self.assertIn('10 puntos porcentuales',self.response(ch))
        ch=fixtures()[0];ch['datasets'][0]['values']=[20,20]
        self.assertIn('son iguales',self.response(ch))

    def test_creation_and_explanation_are_distinct(self):
        for prompt in ('Genera un dashboard y explica los resultados','Cambia el histograma a 15 intervalos y explica','Aplica Costa y luego interpreta','Quiero un dashboard de ventas y explica sus resultados','Dame un gráfico de dona y su interpretación'):
            self.assertFalse(ai_chat._interpretation_request([dict(role='user',content=prompt)]))
        for prompt in ('Explica cómo se genera este dashboard','Explica por qué cambia la línea','No generes otro dashboard; interpreta este','Analiza el mapa de calor'):
            messages=[dict(role='user',content=prompt)]
            self.assertTrue(ai_chat._interpretation_request(messages))
            self.assertFalse(ai_chat._dashboard_request(messages))
            self.assertFalse(ai_chat._chart_request(messages)[0])
            self.assertIsNone(ai_chat._advanced_chart_kind(messages))


if __name__=='__main__':unittest.main()
