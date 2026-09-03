import unittest
from unittest.mock import patch
import ai_chat
from objective_dashboards import detect_objective

DASH='Genera un dashboard de ventas de 2025 con ingresos por mes, productos más vendidos por región y margen por categoría'
PRED='Genera un dashboard con el pronóstico de ingresos para los primeros tres meses de 2026 usando los datos de 2024 y 2025'

class Prueba11(unittest.TestCase):
 def test_themes_never_activate_official(self):
  for text in [DASH,'Genera un dashboard de tendencia mensual','Compara personalizados vs estándar','Dashboard de clientes por margen','Dashboard de retorno de promociones','Dashboard de fines de semana']:
   self.assertIsNone(detect_objective(text),text)
 def test_explicit_official(self):
  for n in range(1,7):self.assertEqual(detect_objective(f'Recrea el objetivo {n} de Jhinson'),n)
 def test_new_objectives_and_negation_are_not_official(self):
  for text in ['Inventa objetivos diferentes a los de Jhinson','No uses los objetivos predefinidos; genera un dashboard mensual','Propón cinco objetivos como los de Power BI pero nuevos']:
   self.assertFalse(ai_chat._official_request([{'role':'user','content':text}]))
 def test_three_months_and_training(self):
  with patch.object(ai_chat,'mcp_request',side_effect=AssertionError('No date query needed')):
   args=ai_chat._prediction_args([{'role':'user','content':PRED}])
  self.assertEqual(args['horizonte_meses'],3)
  self.assertEqual(args['desde'],'2024-01-01');self.assertEqual(args['hasta'],'2025-12-31')
 def test_numeric_and_word_horizons(self):
  for count in ('3','tres'):
   args=ai_chat._prediction_args([{'role':'user','content':f'Pronostica los primeros {count} meses de 2026 usando los datos de 2024 y 2025'}])
   self.assertEqual(args['horizonte_meses'],3)
 def test_explicit_panels(self):
  result=ai_chat._constrain_dashboard_plan(DASH,{'title':'Ventas','kpis':['ingresos'],'charts':[]})
  self.assertEqual([(c['dimensions'],c['metric']) for c in result['charts']],[(['mes'],'ingresos'),(['region','producto'],'unidades'),(['categoria'],'margen')])
  self.assertEqual(result['charts'][1]['top_per_group'],5)
 def test_ranking_per_group_not_global(self):
  from semantic_analytics import chart_contract
  data={'datos':[{'etiqueta':'Costa','serie':'A','valor':100},{'etiqueta':'Costa','serie':'B','valor':90},{'etiqueta':'Sierra','serie':'C','valor':5},{'etiqueta':'Sierra','serie':'D','valor':1}], 'formato':'numero','etiqueta_metrica':'Unidades'}
  chart=chart_contract({'dimensions':['region','producto'],'metric':'unidades','top_per_group':1},{},data)
  self.assertEqual(chart['labels'],['Costa · A','Sierra · C'])
  self.assertEqual(chart['datasets'][0]['values'],[100,5])
 def test_official_tools_hidden(self):
  fake={'tools':[{'name':n,'description':'','inputSchema':{}} for n in ('consultar_semantica','generar_dashboard_objetivo','consultar_objetivos_dashboards')]}
  with patch.object(ai_chat,'mcp_request',return_value=fake):
   self.assertEqual([t['name'] for t in ai_chat.openai_tools([{'role':'user','content':'Propón cinco objetivos'}])],['consultar_semantica'])
   self.assertEqual(len(ai_chat.openai_tools([{'role':'user','content':'Muéstrame los objetivos de Jhinson'}])),3)
 def test_proposed_selection_not_official_id(self):
  messages=[{'role':'user','content':'Propón cinco objetivos de análisis'},{'role':'assistant','content':'1. Analizar colores\nUnidades por color.\n2. Analizar métodos de pago\nIngresos por método de pago.\n3. Analizar tallas\nUnidades por talla.'},{'role':'user','content':'Genera un dashboard del segundo objetivo para 2025'}]
  result=ai_chat._resolve_proposed_objective(messages)
  self.assertIn('Ingresos por método de pago',result[-1]['content'])
  self.assertNotIn('Unidades por talla',result[-1]['content'])
  self.assertIsNone(detect_objective(result[-1]['content']))
  self.assertEqual(messages[-1]['content'],'Genera un dashboard del segundo objetivo para 2025')
 def test_proposal_plan_preserves_dimensions(self):
  messages=[{'role':'user','content':'Propón cinco objetivos'},{'role':'assistant','content':'1. Otro\n2. Margen y utilidad\n - Analizar: Margen (%), Utilidad por categoría y proveedor.\n3. Otro'},{'role':'user','content':'Genera un dashboard del objetivo 2 para 2025'}]
  resolved=ai_chat._resolve_proposed_objective(messages)
  self.assertEqual([(c['dimensions'],c['metric']) for c in resolved[-1]['_proposed_plan']['charts']],[(['categoria','proveedor'],'margen'),(['categoria','proveedor'],'utilidad')])

if __name__=='__main__':unittest.main()
