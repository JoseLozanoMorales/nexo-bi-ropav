import unittest
from unittest.mock import patch
from copy import deepcopy
import ai_chat
from db import sales_histogram

class Prueba7(unittest.TestCase):
 def test_interpretation_is_not_creation(self):
  for name in ['histograma','histogramas','boxplot','mapa de calor','dona','barras horizontales','Pareto']:
   messages=[dict(role='user',content='Dime tu interpretación de lo que se ve en el '+name)]
   self.assertFalse(ai_chat._chart_request(messages)[0],name)
   self.assertIsNone(ai_chat._advanced_chart_kind(messages),name)
  self.assertTrue(ai_chat._chart_request([dict(role='user',content='Genera un histograma y explica los resultados')])[0])
  self.assertTrue(ai_chat._chart_request([dict(role='user',content='Cambia el histograma a 15 intervalos y explica')])[0])
  self.assertFalse(ai_chat._chart_request([dict(role='user',content='No generes otro histograma; interpreta este')])[0])

 def test_original_conversation_uses_saved_values(self):
  data=sales_histogram()
  chart=ai_chat._chart({'structuredContent':data},[dict(role='user',content='Genera histogramas de las ventas')])
  self.assertEqual(chart['statistics']['ventas'],330)
  self.assertEqual(chart['filters']['intervalos'],10)
  self.assertEqual(sum(chart['datasets'][0]['values']),330)
  snapshot=deepcopy(chart)
  messages=[dict(role='user',content='Genera histogramas de las ventas'),
            dict(role='assistant',content=ai_chat._histogram_text(data),chart=chart),
            dict(role='user',content='Dime tu interpretacion de lo que se ve en el histograma')]
  with patch.object(ai_chat,'mcp_request',side_effect=AssertionError('No debe consultar otra vez')),patch.object(ai_chat,'OpenAI',side_effect=AssertionError('No debe enviar el gráfico a OpenAI')):
   response=ai_chat.ask(messages)
  self.assertIsNone(response['chart'])
  self.assertEqual(response['tools'],[])
  self.assertIn('330 ventas',response['text'])
  modal=max(data['datos'],key=lambda row:row['frecuencia'])
  self.assertIn(modal['etiqueta'],response['text'])
  self.assertIn(str(modal['frecuencia'])+' ventas',response['text'])
  self.assertNotEqual(response['text'],messages[1]['content'])
  self.assertEqual(chart,snapshot)
  print(response['text'])

 def test_old_histograms_without_metadata(self):
  chart=dict(type='histogram',labels=['0–10','10–20','20–30','30–40'],
             datasets=[dict(values=[3,5,1,1])])
  answer=ai_chat.ask([dict(role='assistant',content='Histograma',chart=chart),
                     dict(role='user',content='Explícamelo')])
  self.assertIn('10–20',answer['text'])
  self.assertIn('80.0%',answer['text'])
  self.assertIsNone(answer['chart'])

 def test_ties_empty_invalid(self):
  chart=dict(labels=['0–10','10–20'],datasets=[dict(values=[5,5])])
  self.assertIn('empatan',ai_chat._histogram_interpretation(chart))
  chart['datasets'][0]['values']=[0,0]
  self.assertIn('no contiene ventas',ai_chat._histogram_interpretation(chart))
  chart['datasets'][0]['values']=[float('nan'),1]
  self.assertIsNone(ai_chat._histogram_interpretation(chart))

if __name__=='__main__':unittest.main()
