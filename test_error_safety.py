import unittest

import server


class ErrorMessageSafetyTests(unittest.TestCase):

    def test_safe_internal_error_hides_exception_details(self):
        secret = r"C:\Users\lenovo\biomedical-ai-mcp\secret\private.db"
        exc = RuntimeError(f"database failure at {secret}")

        result = server.safe_internal_error(
            "Operation failed safely.",
            exc,
        )

        self.assertEqual(
            result,
            {"error": "Operation failed safely."},
        )
        self.assertNotIn(secret, result["error"])

    def test_safe_internal_error_does_not_return_exception_type(self):
        exc = RuntimeError("sqlite3.OperationalError: SELECT secret FROM users")

        result = server.safe_internal_error(
            "Database operation failed.",
            exc,
        )

        self.assertEqual(
            result["error"],
            "Database operation failed.",
        )
        self.assertNotIn("sqlite3", result["error"])
        self.assertNotIn("SELECT", result["error"])

    def test_pdf_extraction_error_message_is_generic(self):
        with open(server.__file__, "r", encoding="utf-8") as file:
            source = file.read()

        self.assertIn(
            '"PDF extraction failed. Please verify the PDF file and try again."',
            source,
        )
        self.assertNotIn(
            '"PDF extraction failed.",\n                str(exc)',
            source,
        )

    def test_retrieval_error_message_is_generic(self):
        with open(server.__file__, "r", encoding="utf-8") as file:
            source = file.read()

        self.assertIn(
            '"Research evidence retrieval failed. Please try again."',
            source,
        )
        self.assertNotIn(
            '"Research evidence retrieval failed.",\n                str(exc)',
            source,
        )

    def test_import_error_message_does_not_expose_exception_details(self):
        with open(server.__file__, "r", encoding="utf-8") as file:
            source = file.read()

        self.assertIn(
            '"The research retrieval component is unavailable."',
            source,
        )
        self.assertNotIn(
            '"Could not import retrieval.py.",\n                str(exc)',
            source,
        )


if __name__ == "__main__":
    unittest.main()
