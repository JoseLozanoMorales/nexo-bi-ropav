import unittest
from unittest.mock import patch

import ai_chat


def base_chart():
    return {"type":"bar","orientation":"horizontal","title":"Ingresos por canal","labels":["A"],
            "datasets":[{"label":"Ingresos","values":[10]}],"filters":{"desde":"2025-01-01","hasta":"2025-12-31"},
            "semantic":{"modelo":"ventas","dimensiones":["canal"],"metrica":"ingresos"}}


class ShortConversationTests(unittest.TestCase):
    def messages(self,current,chart=None):
        return [{"role":"user","content":"Haz un gráfico de barras de ingresos por canal en 2025"},
                {"role":"assistant","content":"Listo","chart":chart or base_chart()},
                {"role":"user","content":current}]

    def semantic_result(self,dimensions,measure,filters,limit):
        return {"fuente":"PostgreSQL RopaV","modelo":"ventas","dimensiones":dimensions,"metrica":measure,
                "etiqueta_metrica":measure.title(),"formato":"number","filtros":filters,
                "datos":[{"etiqueta":"X","valor":4}],"criterio_ventas":""}

    def test_type_only_keeps_metric_dimension_and_period(self):
        with patch.object(ai_chat,"query_semantic",side_effect=self.semantic_result):
            answer=ai_chat.ask(self.messages("De dona"))
        self.assertEqual(answer["chart"]["type"],"doughnut")
        self.assertEqual(answer["chart"]["semantic"]["dimensiones"],["canal"])
        self.assertEqual(answer["chart"]["filters"]["desde"],"2025-01-01")

    def test_dimension_and_metric_modifiers(self):
        with patch.object(ai_chat,"query_semantic",side_effect=self.semantic_result):
            province=ai_chat.ask(self.messages("Ahora por provincia"))
            units=ai_chat.ask(self.messages("Cambia ingresos por unidades"))
        self.assertEqual(province["chart"]["semantic"]["dimensiones"],["provincia"])
        self.assertEqual(units["chart"]["semantic"]["metrica"],"unidades")

    def test_short_filter_is_applied(self):
        with patch.object(ai_chat,"query_semantic",side_effect=self.semantic_result):
            answer=ai_chat.ask(self.messages("Solo personalizados"))
        self.assertEqual(answer["chart"]["filters"]["personalizado"],"Sí")

    def test_put_it_in_dashboard_and_download_it(self):
        with patch.object(ai_chat,"_planned_dashboard",return_value={"title":"Dashboard","charts":[],"kpis":[]}):
            dashboard=ai_chat.ask(self.messages("Ponlo en un dashboard"))
        downloaded=ai_chat.ask(self.messages("Descárgalo"))
        self.assertIsNotNone(dashboard["dashboard"])
        self.assertEqual(downloaded["chart"]["title"],"Ingresos por canal")

    def test_elliptical_text_keeps_prior_request(self):
        text=ai_chat._request_text(self.messages("Proyecta tres meses"))
        self.assertIn("ingresos por canal",text)
        self.assertTrue(text.endswith("Proyecta tres meses"))

    def test_procede_keeps_the_original_instruction(self):
        messages=[{"role":"user","content":"Haz un gráfico de dona con ingresos por canal"},
                  {"role":"assistant","content":"¿Confirmas que proceda?"},
                  {"role":"user","content":"Procede"}]
        text=ai_chat._request_text(messages)
        self.assertIn("gráfico de dona",text)
        self.assertTrue(text.endswith("Procede"))

    def test_legacy_chart_saves_semantic_definition(self):
        data={"structuredContent":{"dimension":"canal","filtros":{"desde":"2025-01-01"},"datos":[{"etiqueta":"WhatsApp","ingresos":10,"unidades":2,"utilidad":5}]}}
        chart=ai_chat._chart(data,[{"role":"user","content":"Gráfico de ingresos por canal"}])
        self.assertEqual(chart["semantic"],{"modelo":"ventas","dimensiones":["canal"],"metrica":"ingresos"})


if __name__=="__main__":unittest.main()
