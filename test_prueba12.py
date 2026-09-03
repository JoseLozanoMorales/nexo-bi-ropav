import unittest
from semantic_analytics import chart_contract

class MissingValues(unittest.TestCase):
 def test_missing_is_null_but_real_zero_survives(self):
  data={'datos':[{'etiqueta':'2025-01','serie':'A','valor':0},{'etiqueta':'2025-02','serie':'B','valor':40}],'formato':'moneda','etiqueta_metrica':'Ticket promedio'}
  chart=chart_contract({'dimensions':['mes','promocion'],'metric':'ticket_promedio','type':'line'},{},data)
  self.assertEqual(chart['datasets'][0]['values'],[0,None])
  self.assertEqual(chart['datasets'][1]['values'],[None,40])
  self.assertIn('no demuestra efectividad',chart['description'])
 def test_series_colors_unique_and_stable(self):
  rows=[{'etiqueta':'2025-01','serie':str(i),'valor':i} for i in range(15)]
  def chart(rows):return chart_contract({'dimensions':['mes','promocion'],'metric':'ingresos','type':'line'},{},{'datos':rows,'formato':'moneda','etiqueta_metrica':'Ingresos'})
  a,b=chart(rows),chart(list(reversed(rows)))
  self.assertEqual(len({d['color'] for d in a['datasets']}),15)
  self.assertEqual([(d['label'],d['color']) for d in a['datasets']],[(d['label'],d['color']) for d in b['datasets']])

if __name__=='__main__':unittest.main()
