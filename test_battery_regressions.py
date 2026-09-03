import unittest
from unittest.mock import patch
import ai_chat

class BatteryRegressions(unittest.TestCase):
    def test_prediction_singular_plural(self):
        for expression, expected in [('región','region'),('regiones','region'),('canal','canal'),('canales','canal')]:
            args=ai_chat._prediction_args([{'role':'user','content':'Proyecta ingresos por '+expression+' seis meses'}])
            self.assertEqual(args['segmento'],expected)
            self.assertEqual(args['horizonte_meses'],6)

    def test_unrequested_filter_is_removed(self):
        messages=[{'role':'user','content':'Ventas de 2025'}, {'role':'user','content':'Ahora en unidades'}, {'role':'user','content':'Desglósalo por canal'}]
        self.assertNotIn('personalizado',ai_chat._ground_personalization(messages,{'personalizado':'No'}))
        self.assertIn('2025',ai_chat._request_text(messages))

    def test_explicit_filter_is_preserved(self):
        self.assertEqual(ai_chat._ground_personalization([{'role':'user','content':'Solo personalizados'}],{'personalizado':'Sí'}),{'personalizado':'Sí'})

    def test_semantic_table_does_not_invent_categories(self):
        text=ai_chat._semantic_result_text({'dimensiones':['canal'],'metrica':'unidades','datos':[{'etiqueta':'Tienda','valor':12}]})
        self.assertIn('12.00',text)
        self.assertNotIn('Otros',text)
        self.assertTrue(text.index('Parámetros')>text.index('Tienda'))

    def test_region_followup_filters_zero_sales(self):
        messages=[{'role':'user','content':'Cuántas regiones están registradas en la base'}, {'role':'user','content':'Ahora dime únicamente cuáles tuvieron ventas'}]
        data={'regiones':[{'region':'Costa','provincias':4,'todas':3,'no_canceladas':2},{'region':'Insular','provincias':0,'todas':0,'no_canceladas':0}]}
        with patch.object(ai_chat,'mcp_request',return_value={'structuredContent':data}):
            result=ai_chat._region_catalog_request(messages)
        self.assertIn('**1**',result['text'])
        self.assertNotIn('Insular',result['text'])

if __name__=='__main__':unittest.main()
