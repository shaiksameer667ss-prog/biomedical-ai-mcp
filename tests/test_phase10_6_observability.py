"""Phase 10.6 observability tests for the MCP tool execution layer."""

import asyncio
import logging
import unittest
from pathlib import Path

import agent_executor


class FakeResult:
    """Minimal MCP-style result used by the tests."""

    def __init__(self, data, is_error=False):
        self.structured_content = data
        self.is_error = is_error
        self.content = []


class FakeSession:
    """Minimal async MCP session used by executor tests."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))

        response = self.responses[name]

        if isinstance(response, Exception):
            raise response

        return FakeResult(response)


class Phase106ObservabilityTests(unittest.TestCase):
    """Verify production logging and observability behavior."""

    def setUp(self):
        self.logger = logging.getLogger(
            "biomedical_research_agent"
        )

    def test_executor_does_not_configure_logging(self):
        """Logging configuration must remain centralized in config.py."""
        source = Path("agent_executor.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "logging.basicConfig(",
            source,
        )

        self.assertNotIn(
            "from config import (\n    LOG_LEVEL",
            source,
        )

    def test_plan_logs_start_and_completion_without_question_text(self):
        """Tool-plan lifecycle events should be logged without the question."""
        session = FakeSession(
            {
                "search_research_evidence": {
                    "results": [
                        {"page": 6}
                    ]
                }
            }
        )

        question = (
            "What mechanisms are involved in "
            "copper nanoparticle toxicity?"
        )

        with self.assertLogs(
            self.logger,
            level="INFO",
        ) as captured:

            result = asyncio.run(
                agent_executor.execute_tool_plan(
                    session,
                    question,
                    ["search_research_evidence"],
                )
            )

        output = "\n".join(captured.output)

        self.assertIn(
            "Starting MCP tool plan",
            output,
        )

        self.assertIn(
            "Starting MCP tool=search_research_evidence",
            output,
        )

        self.assertIn(
            "Completed MCP tool=search_research_evidence",
            output,
        )

        self.assertIn(
            "Completed MCP tool plan",
            output,
        )

        # The complete user research question must not appear
        # in executor logs.
        self.assertNotIn(
            question,
            output,
        )

        self.assertEqual(
            result[
                agent_executor.EXECUTION_STATUS_KEY
            ][
                "search_research_evidence"
            ]["status"],
            "SUCCESS",
        )

    def test_failed_tool_is_logged_and_execution_continues(self):
        """One failed MCP tool must not prevent later tools from running."""
        session = FakeSession(
            {
                "search_research_evidence": RuntimeError(
                    "simulated failure"
                ),
                "search_experiments": {
                    "experiments": []
                },
            }
        )

        with self.assertLogs(
            self.logger,
            level="ERROR",
        ) as captured:

            result = asyncio.run(
                agent_executor.execute_tool_plan(
                    session,
                    "find relevant research and experiments",
                    [
                        "search_research_evidence",
                        "search_experiments",
                    ],
                )
            )

        output = "\n".join(captured.output)

        self.assertIn(
            "search_research_evidence failed",
            output,
        )

        self.assertIsNone(
            result["search_research_evidence"]
        )

        self.assertEqual(
            result["search_experiments"],
            {
                "experiments": []
            },
        )

        self.assertEqual(
            result[
                agent_executor.EXECUTION_STATUS_KEY
            ][
                "search_research_evidence"
            ]["status"],
            "FAILED",
        )

        self.assertEqual(
            result[
                agent_executor.EXECUTION_STATUS_KEY
            ][
                "search_experiments"
            ]["status"],
            "SUCCESS",
        )

    def test_mcp_error_result_is_logged(self):
        """MCP CallToolResult.is_error must be logged and raised."""
        class ErrorResult:
            is_error = True
            content = [
                type(
                    "Item",
                    (),
                    {"text": "tool failure"},
                )()
            ]
            structured_content = None

        with self.assertLogs(
            self.logger,
            level="ERROR",
        ) as captured:

            with self.assertRaises(RuntimeError):
                agent_executor.parse_mcp_result(
                    ErrorResult()
                )

        output = "\n".join(captured.output)

        self.assertIn(
            "MCP tool result marked as error",
            output,
        )

    def test_unsupported_tool_is_warning(self):
        """Unsupported MCP tools should produce a warning."""
        with self.assertLogs(
            self.logger,
            level="WARNING",
        ) as captured:

            result = asyncio.run(
                agent_executor.execute_tool(
                    object(),
                    "unknown_tool",
                    "test question",
                )
            )

        self.assertEqual(
            result,
            {
                "error": "Unsupported tool: unknown_tool"
            },
        )

        output = "\n".join(captured.output)

        self.assertIn(
            "Unsupported MCP tool requested",
            output,
        )

    def test_research_question_is_not_logged_by_executor(self):
        """The executor must not expose the complete research question."""
        session = FakeSession(
            {
                "search_research_evidence": {
                    "results": []
                }
            }
        )

        sensitive_question = (
            "PRIVATE_RESEARCH_QUERY_12345"
        )

        with self.assertLogs(
            self.logger,
            level="INFO",
        ) as captured:

            asyncio.run(
                agent_executor.execute_tool_plan(
                    session,
                    sensitive_question,
                    ["search_research_evidence"],
                )
            )

        output = "\n".join(captured.output)

        self.assertNotIn(
            sensitive_question,
            output,
        )


if __name__ == "__main__":
    unittest.main()