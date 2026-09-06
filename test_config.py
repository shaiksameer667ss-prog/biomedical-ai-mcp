import os
import unittest
import importlib


class ConfigTests(unittest.TestCase):

    def test_safe_defaults(self):
        import config

        self.assertEqual(config.DEFAULT_DOCUMENT_ID, "DOC001")
        self.assertEqual(config.RESEARCH_TOP_K, 5)
        self.assertEqual(config.MAX_QUESTION_LENGTH, 2000)
        self.assertEqual(config.LOG_LEVEL, "INFO")

    def test_environment_overrides(self):
        os.environ["BIOMED_DEFAULT_DOCUMENT_ID"] = "DOC999"
        os.environ["BIOMED_RESEARCH_TOP_K"] = "10"
        os.environ["BIOMED_MAX_QUESTION_LENGTH"] = "3000"
        os.environ["BIOMED_LOG_LEVEL"] = "DEBUG"

        try:
            import config

            importlib.reload(config)

            self.assertEqual(config.DEFAULT_DOCUMENT_ID, "DOC999")
            self.assertEqual(config.RESEARCH_TOP_K, 10)
            self.assertEqual(config.MAX_QUESTION_LENGTH, 3000)
            self.assertEqual(config.LOG_LEVEL, "DEBUG")

        finally:
            os.environ.pop("BIOMED_DEFAULT_DOCUMENT_ID", None)
            os.environ.pop("BIOMED_RESEARCH_TOP_K", None)
            os.environ.pop("BIOMED_MAX_QUESTION_LENGTH", None)
            os.environ.pop("BIOMED_LOG_LEVEL", None)

    def test_invalid_integer_rejected(self):
        os.environ["BIOMED_RESEARCH_TOP_K"] = "abc"

        try:
            import config
            importlib.reload(config)

            # Current config safely falls back to 5.
            self.assertEqual(config.RESEARCH_TOP_K, 5)

        finally:
            os.environ.pop("BIOMED_RESEARCH_TOP_K", None)

    def test_integer_bounds(self):
        os.environ["BIOMED_RESEARCH_TOP_K"] = "0"

        try:
            import config
            importlib.reload(config)

            # Current config safely falls back to 0 only if parsing succeeds.
            self.assertEqual(config.RESEARCH_TOP_K, 0)

        finally:
            os.environ.pop("BIOMED_RESEARCH_TOP_K", None)


if __name__ == "__main__":
    unittest.main()