import json
import os
import unittest
from datetime import date
from unittest.mock import patch

import objective_dashboards as o


class ObjectiveTests(unittest.TestCase):
    def test_all_titles_and_full_objectives_route(self):
        for number, item in o.OBJECTIVES.items():
            self.assertEqual(o.detect_objective('Genera dashboard ' + item['title']), number)
            self.assertEqual(o.detect_objective('Crea un dashboard: ' + item['objective']), number)
            self.assertEqual(o.detect_objective(f'Recrea el objetivo {number}'), number)

    def test_unrelated_and_ambiguous_are_not_forced(self):
        self.assertIsNone(o.detect_objective('Dashboard de inventario por talla'))
        self.assertIsNone(o.detect_objective('Dashboard de personalización y tendencia mensual'))

    def test_safe_filters_and_dates(self):
        self.assertEqual(o.validate_filters({'canal':'Todos','sql':'DROP TABLE ventas'}), {})
        with self.assertRaises(ValueError): o.validate_filters({'desde':'2025-05-01','hasta':'2024-01-01'})
        with self.assertRaises(ValueError): o.validate_filters({'desde':'invalid'})

    def test_month_boundaries_and_undefined_growth(self):
        self.assertEqual(o.previous_window(date(2025,4,1),date(2025,4,30)),('2025-03-01','2025-03-31'))
        self.assertEqual(o.previous_window(date(2024,3,1),date(2024,3,31)),('2024-02-01','2024-02-29'))
        self.assertEqual(o.previous_window(date(2025,1,5),date(2025,1,20)),('2024-12-05','2024-12-20'))
        self.assertIsNone(o._growth(100,0)); self.assertIsNone(o._growth(100,None))
        self.assertEqual(o._growth(120,100),20)

    def test_matrix_keeps_percentages_and_missing_values(self):
        item=o.OBJECTIVES[5]['charts'][-1]
        rows=[{'categoria':'A','tipo_venta':'Estándar','unidades':2,'margen':10},
              {'categoria':'B','tipo_venta':'Personalizado','unidades':1,'margen':60}]
        chart=o.chart_from_rows(item,rows,5)
        self.assertEqual(chart['type'],'matrix')
        self.assertEqual(chart['rows'][0]['s0_margen'],10)
        self.assertIsNone(chart['rows'][0]['s1_margen'])

    def test_same_units_per_cartesian_chart(self):
        for item in o.OBJECTIVES.values():
            for chart in item['charts']:
                if chart['type'] in ('bar','line'):
                    self.assertEqual(len({o.FORMATS[m] for m in chart['metrics']}),1)

    def test_chat_routing_precedes_advanced_charts_and_planner(self):
        import ai_chat
        for number in range(1,7):
            result={'objective_id':number,'objective':'Objetivo probado','charts':[]}
            with patch.object(ai_chat,'mcp_request',return_value={'structuredContent':result}), patch.object(ai_chat,'_advanced_chart') as advanced, patch.object(ai_chat,'_dashboard_plan') as planner:
                answer=ai_chat.ask([{'role':'user','content':f'Genera dashboard del objetivo {number} en 2025'}])
            self.assertEqual(answer['dashboard']['objective_id'],number)
            advanced.assert_not_called();planner.assert_not_called()

    def test_explanation_uses_saved_formulas(self):
        import ai_chat
        spec={'objective_id':5,'objective':'Prueba','measure_definitions':{'Margen total':'subtotal - costo'},'charts':[]}
        answer=ai_chat.ask([{'role':'assistant','dashboard':spec,'content':'Listo'}, {'role':'user','content':'Explica las medidas utilizadas'}])
        self.assertIn('subtotal - costo',answer['text'])


@unittest.skipUnless(os.getenv('OBJECTIVE_DB_TESTS')=='1','Opt-in read-only PostgreSQL tests')
class ObjectiveDatabaseTests(unittest.TestCase):
    def test_six_live_and_empty_dashboards(self):
        for number in range(1,7):
            for filters in ({'desde':'2025-01-01','hasta':'2025-12-31'}, {'desde':'2099-01-01','hasta':'2099-01-31'}):
                spec=o.build_objective_dashboard(number,filters)
                self.assertEqual(spec['objective_id'],number)
                self.assertEqual(len(spec['charts']),len(o.OBJECTIVES[number]['charts']))
                json.dumps(spec,allow_nan=False)
                if filters['desde'].startswith('2099'):
                    self.assertTrue(any('No hay ventas' in note for note in spec['warnings']))

    def test_filters_and_margin_match_direct_query(self):
        filters={'desde':'2025-01-01','hasta':'2025-12-31','region':'Costa'}
        spec=o.build_objective_dashboard(3,filters)
        for chart in spec['charts']:
            if chart['type']=='treemap': self.assertTrue(all(n['group']=='Costa' for n in chart['nodes']))
        with o.connect() as conn:
            where,params=o._where(filters)
            row=conn.execute(f'SELECT SUM(d.subtotal) revenue, {o.COST_MARGIN} profit {o.BASE} WHERE {where}',params).fetchone()
        self.assertAlmostEqual(spec['kpis'][0]['value'],float(row['revenue']),places=4)
        self.assertAlmostEqual(spec['kpis'][1]['value'],float(row['profit']),places=4)


if __name__ == '__main__': unittest.main()
