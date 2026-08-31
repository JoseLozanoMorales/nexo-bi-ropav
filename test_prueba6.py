"""Regressions from Prueba 6; local PostgreSQL and mocked model only."""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import ai_chat
from api_errors import SafeRequestError, public_error
from chat_evidence import explicit_dates
from dashboard_builder import _planned_dashboard
from semantic_analytics import chart_contract
from weekly_analysis import SALE_CRITERION, weekly_summary, weekly_text


class Prueba6(unittest.TestCase):
    def test_safe_invalid_dates(self):
        for prompt in ('del 31 de diciembre de 2025 al 1 de enero de 2025', 'del 30 al 31 de febrero de 2025'):
            with self.assertRaises(SafeRequestError) as error:
                explicit_dates(prompt)
            public, status = public_error(error.exception)
            self.assertEqual(status, 400)
            self.assertEqual(public['error'], str(error.exception))
        public, _ = public_error(ValueError('password=secret'))
        self.assertNotIn('secret', public['error'])

    def test_ties(self):
        chart = chart_contract(dict(dimensions=['canal'], metric='transacciones', type='bar'),
                               dict(desde='2025-01-01', hasta='2025-12-31'))
        self.assertIn('empatan', chart['description'])
        self.assertIn('Tienda Física', chart['description'])
        self.assertIn('WhatsApp', chart['description'])
        self.assertEqual(sorted(chart['datasets'][0]['values']), [89, 94, 94])

    def test_weekly_concision_and_singular(self):
        result = {'estacionalidad_semanal': weekly_summary(
            [dict(etiqueta='Monday', serie='Tienda', valor=1)],
            ['dia_semana', 'canal'], '2024-01-08', '2024-01-08')}
        text = weekly_text(result)
        self.assertIn('1 día de lunes', text)
        self.assertIn('1 transacción.', text)
        self.assertNotIn('cancelad', text)
        self.assertIn(SALE_CRITERION, weekly_text(result, include_criterion=True))

    def test_future_range_after_coverage_only(self):
        call = SimpleNamespace(type='function_call', name='consultar_periodos', arguments='{}', call_id='1')
        def mcp(method, params, request_id):
            if params['name']=='consultar_periodos':
                return {'structuredContent': {'desde':'2024-01-05', 'hasta':'2025-12-29'}}
            self.assertEqual(params['arguments']['desde'], '2030-01-01')
            self.assertEqual(params['arguments']['hasta'], '2030-01-07')
            return {'structuredContent': {'indicadores': {'transacciones':0}}}
        with patch.dict(ai_chat.os.environ, OPENAI_API_KEY='mock'), patch.object(ai_chat, 'OpenAI') as client, patch.object(ai_chat, 'openai_tools', return_value=[]), patch.object(ai_chat, 'mcp_request', side_effect=mcp):
            client.return_value.responses.create.side_effect = [
                SimpleNamespace(id='1', output=[call]),
                SimpleNamespace(output=[], output_text='No es posible consultar 2020-01-01 a 2030-01-07')]
            answer=ai_chat.ask([dict(role='user', content='Ahora consulta del 1 al 7 de enero de 2030')])
        self.assertIn('2030-01-01 a 2030-01-07', answer['text'])
        self.assertNotIn('2020', answer['text'])
        self.assertIn('No hay transacciones', answer['text'])
        self.assertEqual(answer['tools'][-1]['name'], 'consultar_analitica')

    def test_independent_dashboard_clauses(self):
        plan={'title':'Ventas 2025 — Nota: ventas canceladas', 'kpis':['ingresos','transacciones','margen'],
              'charts':[dict(dimensions=['mes','canal'], metric='ingresos', type='line'),
                        dict(dimensions=['canal'], metric='transacciones', type='bar'),
                        dict(dimensions=['categoria'], metric='utilidad', type='bar')]}
        snapshot=deepcopy(plan)
        fixed=ai_chat._constrain_dashboard_plan('Crea un dashboard de 2025 con exactamente tres gráficos: ingresos mensuales, transacciones por canal y margen porcentual por categoría. Aclara el tratamiento de ventas canceladas',plan)
        self.assertEqual(fixed['charts'][0]['dimensions'], ['mes'])
        self.assertEqual(fixed['charts'][2]['metric'], 'margen')
        self.assertEqual(plan,snapshot)
        original=_planned_dashboard({'desde':'2025-01-01','hasta':'2025-12-31'}, fixed)
        self.assertEqual(original['title'],'Ventas 2025')
        self.assertNotIn('cancelad', original['subtitle'])
        updated=ai_chat._edit_dashboard(original,'Aplica Costa a todo el dashboard')
        dashboard=updated['dashboard']
        self.assertIn('Region: Costa', dashboard['subtitle'])
        self.assertEqual(dashboard['kpis'][1]['value'],101)
        self.assertAlmostEqual(dashboard['kpis'][0]['value'],16555.55,places=2)
        self.assertEqual(len(updated['tools']),3)
        explanation=ai_chat._dashboard_explanation([
            dict(role='assistant',content='Dashboard',dashboard=dashboard),
            dict(role='user',content='Explica las métricas y filtros realmente usados en cada gráfico')])
        self.assertIn('Costa', explanation['text'])
        self.assertIn('2025-01-01', explanation['text'])
        self.assertIn('2025-12-31', explanation['text'])
        self.assertNotIn('cancelad', explanation['text'])


if __name__=='__main__':
    unittest.main()
