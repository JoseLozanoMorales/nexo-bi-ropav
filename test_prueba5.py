import unittest
from copy import deepcopy
from unittest.mock import patch
from chat_evidence import explicit_dates, cancellation_counts, weekly_chart
from semantic_analytics import query_semantic, chart_contract
from ai_chat import _chart, _chart_request, _edit_dashboard, ask, _validated_text


class Prueba5(unittest.TestCase):
 def test_dates(self):
  self.assertEqual(explicit_dates('del 6 al 7 de enero de 2024'),{'desde':'2024-01-06','hasta':'2024-01-07'})
  self.assertEqual(explicit_dates('únicamente para el 8 de enero de 2024')['hasta'],'2024-01-08')
  self.assertEqual(explicit_dates('del 1 al 7 de enero de 2030')['hasta'],'2030-01-07')
  with self.assertRaises(ValueError): explicit_dates('del 31 de diciembre de 2025 al 1 de enero de 2025')

 def test_cancelled_reconcile(self):
  data=cancellation_counts({'desde':'2024-01-05','hasta':'2025-12-29'})
  self.assertEqual(data['totales'],dict(todas=340,canceladas=10,no_canceladas=330,sin_estado=0))
  self.assertTrue(data['comprobacion'])

 def test_weekend_and_empty(self):
  r=query_semantic(['dia_semana','canal'],'transacciones',explicit_dates('del 6 al 7 de enero de 2024'))
  self.assertEqual(r['estacionalidad_semanal']['dias_laborables'],0)
  self.assertEqual(r['estacionalidad_semanal']['dias_fin_semana'],2)
  self.assertEqual(weekly_chart(r)['type'],'bar')
  r=query_semantic(['dia_semana','canal'],'transacciones',explicit_dates('del 1 al 7 de enero de 2030'))
  self.assertEqual(r['datos'],[])

 def test_semantic_chart(self):
  r=query_semantic(['canal'],'transacciones',{'desde':'2025-01-01','hasta':'2025-12-31'})
  ch=_chart({'structuredContent':r},[{'role':'user','content':'Barras horizontales de transacciones por canal'}])
  self.assertEqual(ch['orientation'],'horizontal')
  self.assertEqual(sorted(ch['datasets'][0]['values']),[89,94,94])
  ch=_chart({'structuredContent':r},[{'role':'user','content':'Convierte esa información en dona'}])
  self.assertEqual(ch['type'],'doughnut')
  self.assertEqual(sum(ch['datasets'][0]['values']),277)

 def test_nonadditive_margin(self):
  chart=chart_contract({'dimensions':['categoria'],'metric':'margen','type':'doughnut'},{'desde':'2025-01-01','hasta':'2025-12-31'})
  self.assertEqual(chart['type'],'bar')
  self.assertNotIn('de lo mostrado',chart['description'])

 def test_edit_and_export(self):
  plan={'title':'Ventas 2025','kpis':['ingresos','transacciones','margen'],'charts':[
   dict(dimensions=['mes'],metric='ingresos',type='line',title='Ingresos mensuales'),
   dict(dimensions=['canal'],metric='transacciones',type='bar',title='Transacciones por canal'),
   dict(dimensions=['categoria'],metric='margen',type='bar',title='Margen por categoría')]}
  from dashboard_builder import _planned_dashboard
  original=_planned_dashboard({'desde':'2025-01-01','hasta':'2025-12-31'},plan)
  snapshot=deepcopy(original)
  updated=_edit_dashboard(original,'Sustituye únicamente el gráfico de ingresos mensuales por ventas segmentadas por género del cliente')['dashboard']
  self.assertEqual(updated['charts'][0]['semantic']['dimensiones'],['genero'])
  self.assertEqual(updated['charts'][1:],original['charts'][1:])
  self.assertEqual(original,snapshot)
  regional=_edit_dashboard(updated,'Aplica Costa a todo el dashboard')['dashboard']
  self.assertEqual(regional['filters']['region'],'Costa')
  self.assertEqual(len(regional['charts']),3)
  self.assertEqual(regional['charts'][2]['type'],'bar')
  exported=ask([{'role':'assistant','content':'Dashboard','dashboard':regional},{'role':'user','content':'Prepara su descarga como imagen'}])
  self.assertEqual(exported['dashboard'],regional)

 def test_latest_type(self):
  self.assertEqual(_chart_request([{'role':'user','content':'Dona de ventas'},{'role':'user','content':'Usa barras verticales'}])[2],'bar')

 def test_explanation_not_replaced(self):
  text='No hay datos de visitas para calcular conversión.'
  self.assertEqual(_validated_text(text,{'indicadores':{'transacciones':10}}),text)

 def test_dates_override_model_arguments(self):
  from types import SimpleNamespace
  import ai_chat
  call=SimpleNamespace(type='function_call',name='consultar_semantica',call_id='1',arguments='{"dimensiones":["canal"],"metrica":"transacciones","desde":"2024-01-05","hasta":"2025-12-29"}')
  with patch.dict(ai_chat.os.environ,{'OPENAI_API_KEY':'fake-for-mock'}),patch.object(ai_chat,'OpenAI') as client,patch.object(ai_chat,'openai_tools',return_value=[]),patch.object(ai_chat,'mcp_request',return_value={'structuredContent':{}}) as tool:
   client.return_value.responses.create.side_effect=[SimpleNamespace(output=[call],id='1'),SimpleNamespace(output=[],output_text='Resultado')]
   ask([{'role':'user','content':'Analiza del 6 al 7 de enero de 2024'}])
   args=tool.call_args.args[1]['arguments']
   self.assertEqual(args['desde'],'2024-01-06')
   self.assertEqual(args['hasta'],'2024-01-07')


if __name__=='__main__':unittest.main()
