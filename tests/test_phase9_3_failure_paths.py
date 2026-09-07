import asyncio
import unittest

from agent_executor import EXECUTION_STATUS_KEY, execute_tool_plan, parse_mcp_result


class Item:
    def __init__(self, text):
        self.text = text


class Result:
    def __init__(self, text="{}", is_error=False):
        self.content = [Item(text)]
        self.is_error = is_error


class MalformedResult:
    pass


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


class Phase93FailurePathTests(unittest.TestCase):
    QUESTION = (
        "What mechanisms are involved in copper nanoparticle toxicity, "
        "and what related experiments are in the database?"
    )

    def test_empty_result_is_valid_success(self):
        session = Session(
            responses={"search_experiments": Result("[]")}
        )
        results = asyncio.run(
            execute_tool_plan(
                session,
                "Find experiments involving copper nanoparticles",
                ["search_experiments"],
            )
        )
        self.assertEqual(results["search_experiments"], [])
        self.assertEqual(
            results[EXECUTION_STATUS_KEY]["search_experiments"]["status"],
            "SUCCESS",
        )

    def test_mcp_is_error_is_failed(self):
        result = Result("database unavailable", is_error=True)
        with self.assertRaises(RuntimeError):
            parse_mcp_result(result)

    def test_mcp_is_error_does_not_abort_other_tool(self):
        session = Session(
            responses={
                "search_research_evidence": Result('{"evidence": ["valid"]}'),
                "search_experiments": Result("database unavailable", is_error=True),
            }
        )
        results = asyncio.run(
            execute_tool_plan(
                session,
                self.QUESTION,
                ["search_research_evidence", "search_experiments"],
            )
        )
        self.assertIsNotNone(results["search_research_evidence"])
        self.assertIsNone(results["search_experiments"])
        self.assertEqual(
            results[EXECUTION_STATUS_KEY]["search_research_evidence"]["status"],
            "SUCCESS",
        )
        self.assertEqual(
            results[EXECUTION_STATUS_KEY]["search_experiments"]["status"],
            "FAILED",
        )

    def test_malformed_result_is_failed_without_aborting(self):
        session = Session(
            responses={
                "search_research_evidence": Result('{"evidence": ["valid"]}'),
                "search_experiments": MalformedResult(),
            }
        )
        results = asyncio.run(
            execute_tool_plan(
                session,
                self.QUESTION,
                ["search_research_evidence", "search_experiments"],
            )
        )
        self.assertIsNotNone(results["search_research_evidence"])
        self.assertIsNone(results["search_experiments"])
        self.assertEqual(
            results[EXECUTION_STATUS_KEY]["search_experiments"]["status"],
            "FAILED",
        )

    def test_both_fail_and_status_records_errors(self):
        session = Session(
            failures={"search_research_evidence", "search_experiments"}
        )
        results = asyncio.run(
            execute_tool_plan(
                session,
                self.QUESTION,
                ["search_research_evidence", "search_experiments"],
            )
        )
        for name in ["search_research_evidence", "search_experiments"]:
            self.assertIsNone(results[name])
            info = results[EXECUTION_STATUS_KEY][name]
            self.assertEqual(info["status"], "FAILED")
            self.assertIn("simulated failure", info["error"])


if __name__ == "__main__":
    unittest.main()
