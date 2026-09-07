import inspect
import unittest

import agent


class ConfigIntegrationTests(unittest.TestCase):

    def test_agent_imports_configuration(self):
        self.assertTrue(hasattr(agent, "DEFAULT_DOCUMENT_ID"))
        self.assertTrue(hasattr(agent, "RESEARCH_TOP_K"))
        self.assertTrue(hasattr(agent, "MAX_QUESTION_LENGTH"))
        self.assertTrue(hasattr(agent, "MCP_SERVER_COMMAND"))
        self.assertTrue(hasattr(agent, "MCP_SERVER_SCRIPT"))
        self.assertTrue(hasattr(agent, "LOG_LEVEL"))

    def test_default_document_id_is_configured(self):
        source = inspect.getsource(agent)

        self.assertIn("DEFAULT_DOCUMENT_ID", source)
        self.assertNotIn(
            '"document_id": "DOC001"',
            source
        )

    def test_research_top_k_is_configured(self):
        source = inspect.getsource(agent)

        self.assertIn("RESEARCH_TOP_K", source)

    def test_server_configuration_is_configured(self):
        source = inspect.getsource(agent)

        self.assertIn("MCP_SERVER_COMMAND", source)
        self.assertIn("MCP_SERVER_SCRIPT", source)

    def test_question_limit_is_configured(self):
        source = inspect.getsource(agent)

        self.assertIn("MAX_QUESTION_LENGTH", source)


if __name__ == "__main__":
    unittest.main()