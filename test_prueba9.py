import unittest
from unittest.mock import patch
import ai_chat
from test_short_conversations import base_chart, ShortConversationTests
from forecasting import forecast

class Prueba9(unittest.TestCase):
 def chain(self,current,chart=None):
  return [{'role':'user','content':'Genera un histograma de ventas de 2024'}, {'role':'assistant','chart':chart or base_chart()}, {'role':'user','content':'Limita el intervalo al primer trimestre de 2024'}, {'role':'assistant','chart':chart or base_chart()}, {'role':'user','content':current}]
 def test_quarter_and_top(self):
  def query(d,m,f,l):
   self.assertEqual(f['hasta'],'2024-03-31')
   return {'dimensiones':d,'metrica':m,'etiqueta_metrica':m,'formato':'number','datos':[{'etiqueta':x,'valor':v} for x,v in [('2024-01',9),('2024-02',7),('2024-03',9),('2024-04',4)]]}
  with patch.object(ai_chat,'query_semantic',side_effect=query):r=ai_chat.ask(self.chain('Ahora hazte un gráfico de pastel sobre los 3 meses con mas ventas'))
  self.assertEqual(r['chart']['type'],'pie');self.assertEqual(len(r['chart']['labels']),3)
  self.assertEqual(r['chart']['semantic']['dimensiones'],['mes'])
 def test_client_type_not_metric(self):
  with patch.object(ai_chat,'query_semantic',side_effect=ShortConversationTests().semantic_result):
   r=ai_chat.ask(self.chain('Ahora crea un gráfico de barras con los tipos de clientes y las ventas de cada uno'))
  self.assertEqual(r['chart']['semantic']['dimensiones'],['tipo_cliente'])
  self.assertEqual(r['chart']['semantic']['metrica'],'transacciones')
 def test_no_stale_chart_after_new_answer(self):
  messages=self.chain('Compáralos')
  messages.insert(-1,{'role':'assistant','content':'Producto líder: X'})
  self.assertIsNone(ai_chat._prior_chart(messages))
 def test_no_stale_prediction(self):
  messages=[{'role':'user','content':'Pronostica ingresos tres meses'},{'role':'assistant','chart':{'forecast':{}}},{'role':'user','content':'Quiero una dona de ingresos por canal de 2025'},{'role':'assistant','chart':base_chart()},{'role':'user','content':'Cámbialo a pastel'}]
  self.assertFalse(ai_chat._prediction_request(messages))
  self.assertNotIn('Pronostica',ai_chat._request_text(messages))
 def test_download_latest_dashboard(self):
  messages=[{'role':'assistant','chart':base_chart()},{'role':'assistant','dashboard':{'title':'Actual','charts':[]}},{'role':'user','content':'Descárgalo'}]
  r=ai_chat.ask(messages);self.assertEqual(r['dashboard']['title'],'Actual');self.assertIsNone(r['chart'])
 def test_predictive_dashboard_has_no_historical_cards(self):
  data={'horizonte_meses':3,'metrica':'ingresos','dimension_segmento':None,'metodo':'Tendencia','limitacion':'Estimación','filtros':{},'datos':[{'periodo':'2026-01','serie':'Total','estimado':100,'inferior':80,'superior':120}]}
  with patch.object(ai_chat,'mcp_request',return_value={'structuredContent':data}):
   r=ai_chat.ask([{'role':'user','content':'Dashboard pronóstico de ingresos tres meses'}])
  self.assertEqual(r['dashboard']['kpis'][0]['value'],100)
  self.assertTrue(all(c.get('forecast') for c in r['dashboard']['charts']))
 def test_forecast_aligned_calendar(self):
  data={'datos':[{'etiqueta':p,'serie':s,'valor':10} for s,ps in [('A',['2025-01','2025-03','2025-04']),('B',['2025-01','2025-02','2025-03'])] for p in ps]}
  with patch('forecasting.query_semantic',return_value=data):r=forecast(segment='canal',horizon=1)
  self.assertEqual({x['periodo'] for x in r['datos']},{'2025-05'})

if __name__=='__main__':unittest.main()
