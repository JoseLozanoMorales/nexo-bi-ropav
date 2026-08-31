"""Tool-loop regression tests without API calls or database writes."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import ai_chat


class ToolLoopTests(unittest.TestCase):
    def run_chat(self, calls):
        responses = [SimpleNamespace(output=[call], id=str(i)) for i, call in enumerate(calls)]
        responses.append(SimpleNamespace(output=[], output_text="Consulta terminada."))
        with patch.dict(ai_chat.os.environ, {"OPENAI_API_KEY": "test-not-a-key"}), patch.object(ai_chat, "OpenAI") as client, patch.object(ai_chat, "openai_tools", return_value=[]), patch.object(ai_chat, "mcp_request", return_value={"structuredContent": {"ok": True}}) as mcp:
            client.return_value.responses.create.side_effect = responses
            answer = ai_chat.ask([{"role": "user", "content": "Consulta las tablas disponibles"}])
            return answer, client.return_value.responses.create.call_count, mcp.call_count

    def test_more_than_twenty_distinct_rounds_complete(self):
        calls = [SimpleNamespace(type="function_call", name="consultar_esquema", call_id=str(i), arguments=json.dumps({"tabla": "tabla_" + str(i)})) for i in range(25)]
        answer, api_calls, mcp_calls = self.run_chat(calls)
        self.assertEqual(answer["text"], "Consulta terminada.")
        self.assertEqual(len(answer["tools"]), 25)
        self.assertEqual(api_calls, 26)
        self.assertEqual(mcp_calls, 25)
        self.assertNotIn("recovered", answer)

    def test_identical_calls_still_stop_without_reexecution(self):
        calls = [SimpleNamespace(type="function_call", name="consultar_esquema", call_id=str(i), arguments="{}") for i in range(3)]
        answer, api_calls, mcp_calls = self.run_chat(calls)
        self.assertTrue(answer["recovered"])
        self.assertIn("llamada repetida", answer["text"])
        self.assertEqual(api_calls, 3)
        self.assertEqual(mcp_calls, 1)


if __name__ == "__main__":
    unittest.main()
