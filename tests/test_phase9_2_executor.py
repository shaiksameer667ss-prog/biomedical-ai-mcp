import asyncio
import unittest

from agent_executor import EXECUTION_STATUS_KEY, execute_tool_plan, parse_mcp_result


class Item:
    def __init__(self, text): self.text = text


class Result:
    def __init__(self, text): self.content = [Item(text)]


class Session:
    def __init__(self, responses=None, failures=None):
        self.responses = responses or {}
        self.failures = failures or set()
        self.calls = []

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        if name in self.failures:
            raise RuntimeError(f"simulated failure: {name}")
        return self.responses.get(name, Result("{}"))


class Phase92Tests(unittest.TestCase):
    QUESTION = "What mechanisms are involved in copper nanoparticle toxicity, and what related experiments are in the database?"

    def test_parse_json(self):
        self.assertEqual(parse_mcp_result(Result('{"ok": true}')), {"ok": True})

    def test_none_result_is_error(self):
        with self.assertRaises(ValueError):
            parse_mcp_result(None)

    def test_partial_success_is_retained(self):
        session = Session(
            responses={"search_research_evidence": Result('{"evidence": ["valid"]}')},
            failures={"search_experiments"},
        )
        results = asyncio.run(execute_tool_plan(session, self.QUESTION, ["search_research_evidence", "search_experiments"]))
        self.assertIsNotNone(results["search_research_evidence"])
        self.assertIsNone(results["search_experiments"])
        self.assertEqual(results[EXECUTION_STATUS_KEY]["search_research_evidence"]["status"], "SUCCESS")
        self.assertEqual(results[EXECUTION_STATUS_KEY]["search_experiments"]["status"], "FAILED")
        self.assertEqual(len(session.calls), 2)

    def test_both_fail_without_aborting(self):
        session = Session(failures={"search_research_evidence", "search_experiments"})
        results = asyncio.run(execute_tool_plan(session, self.QUESTION, ["search_research_evidence", "search_experiments"]))
        for name in ["search_research_evidence", "search_experiments"]:
            self.assertIsNone(results[name])
            self.assertEqual(results[EXECUTION_STATUS_KEY][name]["status"], "FAILED")

    def test_tool_level_error_is_failed(self):
        session = Session(responses={"search_experiments": Result('{"error": "database unavailable"}')})
        results = asyncio.run(execute_tool_plan(session, "Find experiments involving copper nanoparticles", ["search_experiments"]))
        self.assertIsNone(results["search_experiments"])
        self.assertEqual(results[EXECUTION_STATUS_KEY]["search_experiments"]["status"], "FAILED")

    def test_unsupported_tool_is_failed(self):
        session = Session()
        results = asyncio.run(execute_tool_plan(session, "Find experiments involving copper nanoparticles", ["unknown_tool"]))
        self.assertIsNone(results["unknown_tool"])
        self.assertEqual(results[EXECUTION_STATUS_KEY]["unknown_tool"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
