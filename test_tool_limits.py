import unittest

import server


class ToolLimitTests(unittest.TestCase):

    def test_search_experiments_rejects_long_query(self):
        result = __import__("asyncio").run(
            server.search_experiments("x" * (server.MAX_SEARCH_QUERY_LENGTH + 1))
        )
        self.assertIn("too long", result["error"])

    def test_search_experiments_rejects_excessive_limit(self):
        result = __import__("asyncio").run(server.search_experiments(limit=server.MAX_SEARCH_LIMIT + 1))
        self.assertIn("maximum allowed value", result["error"])

    def test_search_experiments_rejects_excessive_duration(self):
        result = __import__("asyncio").run(server.search_experiments(duration_hours=server.MAX_DURATION_HOURS + 1))
        self.assertIn("maximum allowed value", result["error"])

    def test_research_content_rejects_long_query(self):
        result = __import__("asyncio").run(server.search_research_content("x" * (server.MAX_SEARCH_QUERY_LENGTH + 1)))
        self.assertIn("too long", result["error"])

    def test_research_content_rejects_excessive_limit(self):
        result = __import__("asyncio").run(server.search_research_content("copper", limit=server.MAX_SEARCH_LIMIT + 1))
        self.assertIn("maximum allowed value", result["error"])

    def test_evidence_rejects_long_question(self):
        result = __import__("asyncio").run(server.search_research_evidence("x" * (server.MAX_SEARCH_QUERY_LENGTH + 1)))
        self.assertIn("too long", result["error"])

    def test_evidence_rejects_excessive_top_k(self):
        result = __import__("asyncio").run(server.search_research_evidence("toxicity", top_k=server.MAX_EVIDENCE_TOP_K + 1))
        self.assertIn("maximum allowed value", result["error"])

    def test_add_experiment_rejects_long_name(self):
        result = __import__("asyncio").run(server.add_experiment("EXP999", "x" * (server.MAX_EXPERIMENT_FIELD_LENGTH + 1)))
        self.assertIn("too long", result["error"])

    def test_add_document_rejects_long_title(self):
        result = __import__("asyncio").run(server.add_research_document("DOC999", "x" * (server.MAX_DOCUMENT_TITLE_LENGTH + 1), "x.pdf"))
        self.assertIn("too long", result["error"])

    def test_add_document_rejects_long_description(self):
        result = __import__("asyncio").run(server.add_research_document("DOC999", "Test", "x.pdf", description="x" * (server.MAX_DOCUMENT_DESCRIPTION_LENGTH + 1)))
        self.assertIn("too long", result["error"])


if __name__ == "__main__":
    unittest.main()
