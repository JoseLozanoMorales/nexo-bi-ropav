import unittest
from unittest.mock import patch
import ai_chat
import dashboard_builder
from test_short_conversations import base_chart

class Prueba10(unittest.TestCase):
 def test_both_preserves_specs_without_queries(self):
  a=base_chart();a['type']='pie';b={**a,'type':'doughnut'}
  with patch.object(ai_chat,'mcp_request',side_effect=AssertionError('No query')):
   answer=ai_chat.ask([{'role':'assistant','content':'','chart':a},{'role':'assistant','content':'','chart':b},{'role':'user','content':'Descarga ambos'}])
  self.assertTrue(answer['dashboard']['export_collection'])
  self.assertEqual(answer['dashboard']['charts'],[a,b])
 def test_both_requires_two_distinct_charts(self):
  a=base_chart()
  with self.assertRaises(ai_chat.SafeRequestError):ai_chat.ask([{'role':'assistant','content':'','chart':a},{'role':'assistant','content':'','chart':a},{'role':'user','content':'Descarga ambos'}])
 def test_units_card_not_replaced(self):
  summary={'indicadores':{'ingresos':100,'utilidad':30,'transacciones':10,'unidades':25,'clientes':8,'margen':30}}
  with patch.object(dashboard_builder,'_query',return_value=summary),patch.object(dashboard_builder,'chart_contract',return_value=base_chart()):
   dashboard=dashboard_builder._planned_dashboard({}, {'kpis':['unidades','transacciones','unidades'],'charts':[{}]})
  values={k['label']:k['value'] for k in dashboard['kpis']}
  self.assertEqual(values['Unidades'],25)
  self.assertEqual(len(dashboard['kpis']),3)

if __name__=='__main__':unittest.main()
