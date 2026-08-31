import unittest
from unittest.mock import patch
from types import SimpleNamespace
import json
from weekly_analysis import weekly_summary, weekly_text


class WeeklyTests(unittest.TestCase):
    def test_calendar_includes_days_without_sales(self):
        rows = [{"etiqueta": "Monday", "serie": "Tienda", "valor": 10},
                {"etiqueta": "Saturday", "serie": "Tienda", "valor": 4}]
        result = weekly_summary(rows, ["dia_semana", "canal"], "2024-01-01", "2024-01-14")
        self.assertEqual((result["dias_laborables"], result["dias_fin_semana"]), (10, 4))
        self.assertEqual(result["grupos"][0]["promedio_laborable"], 1)
        self.assertEqual(result["grupos"][0]["promedio_fin_semana"], 1)

    def test_reverse_dimensions_and_zero_denominator(self):
        result = weekly_summary([{"etiqueta": "Tienda", "serie": "Monday", "valor": 2}],
                                ["canal", "dia_semana"], "2024-01-01", "2024-01-01")
        self.assertIsNone(result["grupos"][0]["promedio_fin_semana"])
        text = weekly_text({"estacionalidad_semanal": result})
        self.assertNotIn("canceladas", text)
        self.assertIn("no canceladas", weekly_text({"estacionalidad_semanal": result}, include_criterion=True))
        self.assertIn("No aplicable", text)
        self.assertIn("no ticket promedio", text)

    def test_empty_and_invalid_period(self):
        self.assertEqual(weekly_summary([], ["dia_semana"], "2024-01-01", "2024-01-07")["grupos"], [])
        with self.assertRaises(ValueError):
            weekly_summary([], ["dia_semana"], "2024-02-01", "2024-01-01")

    def test_report_period(self):
        result = weekly_summary([], ["dia_semana"], "2024-01-05", "2025-12-29")
        self.assertEqual(result["dias_laborables"] + result["dias_fin_semana"], 725)

    def test_chat_uses_verified_weekly_result(self):
        import ai_chat
        rows = [{"etiqueta": "Monday", "serie": "Tienda", "valor": 10}]
        evidence = {"estacionalidad_semanal": weekly_summary(rows, ["dia_semana", "canal"], "2024-01-01", "2024-01-14")}
        call = SimpleNamespace(type="function_call", name="consultar_semantica", call_id="test", arguments=json.dumps({"dimensiones": ["dia_semana", "canal"], "metrica": "transacciones"}))
        initial = SimpleNamespace(output=[call], id="test")
        final = SimpleNamespace(output=[], output_text="Mayor ticket por día: 15.6")
        with patch.dict(ai_chat.os.environ, {"OPENAI_API_KEY": "test-not-a-key"}), patch.object(ai_chat, "OpenAI") as client, patch.object(ai_chat, "openai_tools", return_value=[]), patch.object(ai_chat, "mcp_request", return_value={"structuredContent": evidence}):
            client.return_value.responses.create.side_effect = [initial, final]
            answer = ai_chat.ask([{"role": "user", "content": "Analiza estacionalidad semanal entre días laborables y fines de semana por canal"}])
        self.assertNotIn("Mayor ticket", answer["text"])
        self.assertIn("1.000 transacciones/día", answer["text"])

    def test_chat_does_not_repeat_sales_criterion(self):
        import ai_chat
        from weekly_analysis import SALE_CRITERION
        call = SimpleNamespace(type="function_call", name="consultar_semantica", call_id="test", arguments=json.dumps({"dimensiones": ["canal"], "metrica": "transacciones"}))
        with patch.dict(ai_chat.os.environ, {"OPENAI_API_KEY": "test-not-a-key"}), patch.object(ai_chat, "OpenAI") as client, patch.object(ai_chat, "openai_tools", return_value=[]), patch.object(ai_chat, "mcp_request", return_value={"structuredContent": {"criterio_ventas": SALE_CRITERION}}):
            client.return_value.responses.create.side_effect = [SimpleNamespace(output=[call], id="test"), SimpleNamespace(output=[], output_text="Hay 330 transacciones.")]
            answer = ai_chat.ask([{"role": "user", "content": "Cuántas transacciones hay por canal"}])
        self.assertNotIn(SALE_CRITERION, answer["text"])


if __name__ == "__main__":
    unittest.main()
