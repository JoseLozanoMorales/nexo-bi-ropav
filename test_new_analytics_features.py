import unittest
from unittest.mock import patch

from response_ordering import parameters_last
from forecasting import forecast_chart
import objective_dashboards


class ResponseOrderingTests(unittest.TestCase):
    def test_parameters_move_after_findings(self):
        text="Respuesta.\n\nFiltros usados:\n- desde: 2025-01-01\n\nHallazgo importante."
        ordered=parameters_last(text)
        self.assertLess(ordered.index("Hallazgo"),ordered.index("Filtros usados"))


class ObjectiveRoutingTests(unittest.TestCase):
    def test_personalized_by_region_is_dynamic(self):
        self.assertIsNone(objective_dashboards.detect_objective(
            "Genera un dashboard sobre los productos personalizados más vendidos en cada región"))
        self.assertIsNone(objective_dashboards.detect_objective(
            "Compara productos personalizados frente a estándar"))
        self.assertEqual(objective_dashboards.detect_objective("Recrea el objetivo 5"),5)

    def test_genera_does_not_mean_gender(self):
        from dashboard_builder import _fallback_plan
        plan=_fallback_plan("Genera un dashboard de productos personalizados por región")
        self.assertFalse(any("genero" in item["dimensions"] for item in plan["charts"]))
        self.assertEqual(plan["charts"][0]["dimensions"],["region","producto"])

    def test_planner_is_constrained_to_product_by_region(self):
        import ai_chat
        plan={"title":"X","kpis":["unidades"],"charts":[{"dimensions":["sku","personalizado"],"metric":"unidades","type":"bar","orientation":"horizontal","title":"X","limit":20}]}
        result=ai_chat._constrain_dashboard_plan("Productos personalizados más vendidos en cada región",plan)
        self.assertEqual(result["charts"][0]["dimensions"],["region","producto"])
        self.assertEqual(result["charts"][0]["metric"],"unidades")


class ForecastChartTests(unittest.TestCase):
    def setUp(self):
        self.result={"metrica":"ingresos","dimension_segmento":"region","horizonte_meses":2,"filtros":{},
          "metodo":"Tendencia lineal.","limitacion":"No es garantía.","datos":[
            {"periodo":"2026-01","serie":"Costa","estimado":100,"inferior":80,"superior":120},
            {"periodo":"2026-01","serie":"Sierra","estimado":200,"inferior":170,"superior":230},
            {"periodo":"2026-02","serie":"Costa","estimado":110,"inferior":85,"superior":135},
            {"periodo":"2026-02","serie":"Sierra","estimado":210,"inferior":175,"superior":245}]}

    def test_supported_prediction_visual_contracts(self):
        for kind in ("line","bar","area","pie","doughnut","scatter","heatmap","stacked_bar","pareto","boxplot","histogram"):
            chart=forecast_chart(self.result,kind)
            self.assertTrue(chart.get("type"),kind)
            self.assertIn("forecast",chart,kind)


class RegionRoutingTests(unittest.TestCase):
    def test_registered_regions_use_master_catalog_without_clarification(self):
        import ai_chat
        data={"regiones":[{"region":"Costa","provincias":7},{"region":"Sierra","provincias":10},{"region":"Amazonía","provincias":6},{"region":"Insular","provincias":1}]}
        with patch.object(ai_chat,"mcp_request",return_value={"structuredContent":data}):
            answer=ai_chat.ask([{"role":"user","content":"¿Cuántas regiones tenemos registradas en la base de datos?"}])
        self.assertIn("**4**",answer["text"])
        self.assertIn("Amazonía",answer["text"])
        self.assertNotIn("¿Te refieres",answer["text"])


if __name__ == "__main__": unittest.main()
