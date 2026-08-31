import unittest
from unittest.mock import patch
from api_errors import validate_chat, public_error


class ErrorTests(unittest.TestCase):
    def test_invalid_messages(self):
        for payload in (None, [], {}, {"messages": [None]}, {"messages": [{"role": "system", "content": "x"}]}, {"messages": [{"role": "user", "content": " "}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_chat(payload)

    def test_valid_chat(self):
        messages = [{"role": "user", "content": "Ventas de 2025"}]
        self.assertEqual(validate_chat({"messages": messages}), messages)

    def test_errors_do_not_disclose_internals(self):
        with patch("api_errors.logging.getLogger"):
            for error, status in ((RuntimeError("secret-connection-string"), 500), (TimeoutError("secret"), 504), (ValueError("secret"), 400)):
                result, actual = public_error(error)
                self.assertEqual(actual, status)
                self.assertNotIn("secret", result["error"])
                self.assertEqual(len(result["reference"]), 12)

    def test_provider_errors(self):
        with patch("api_errors.logging.getLogger"):
            for name, status in (("RateLimitError", 429), ("APIConnectionError", 503), ("AuthenticationError", 503)):
                result, actual = public_error(type(name, (Exception,), {})("private detail"))
                self.assertEqual(actual, status)


if __name__ == "__main__":
    unittest.main()
