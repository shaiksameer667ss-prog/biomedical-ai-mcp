"""Interactive application entry point for the Biomedical Research MCP Agent."""

import asyncio
import logging
import sys

from config import (
    MCP_SERVER_COMMAND,
    MCP_SERVER_SCRIPT,
    configure_logging,
)

configure_logging()

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_answer import build_combined_research_answer, print_result
from agent_executor import EXECUTION_STATUS_KEY, execute_tool_plan
from agent_planner import plan_tools, validate_question, AgentInputError

logger = logging.getLogger("biomedical_research_agent")


async def show_tools(session):
    tools_result = await session.list_tools()
    print()
    print(f"Connected to MCP server. Discovered {len(tools_result.tools)} tools.")
    print()
    for tool in tools_result.tools:
        print(f"- {tool.name}")
    print()


def _print_execution_status(tool_names, tool_results):
    statuses = tool_results.get(EXECUTION_STATUS_KEY, {})
    if not statuses:
        return
    print()
    print("Tool Execution Status")
    print("---------------------")
    for tool_name in tool_names:
        info = statuses.get(tool_name, {})
        status = info.get("status", "UNKNOWN")
        print(f"- {tool_name}: {status}")
        if status == "FAILED":
            print(f"  Error: {info.get('error', 'Unknown error')}")


def print_planned_result(question, tool_names, tool_results):
    """Display results while preserving successful partial results."""
    _print_execution_status(tool_names, tool_results)
    statuses = tool_results.get(EXECUTION_STATUS_KEY, {})
    failed = [
        name for name in tool_names
        if statuses.get(name, {}).get("status") == "FAILED"
    ]
    successful = [name for name in tool_names if name not in failed]

    if len(tool_names) == 1:
        name = tool_names[0]
        print()
        print(f"Selected MCP tool: {name}")
        if name in failed:
            print("\nThe selected tool failed, so no result is available.")
            return
        print_result(name, question, tool_results.get(name))
        return

    print()
    print("Selected MCP tools:")
    for name in tool_names:
        print(f"- {name}")
    print()
    print("=" * 60)
    print("Combined Research Answer")
    print("------------------------")

    if not successful:
        print("All planned MCP tools failed. No research answer can be generated.")
    else:
        try:
            answer = build_combined_research_answer(question, tool_results)
            print(answer or "The available tool results were insufficient to generate a combined answer.")
        except Exception:
            logger.exception("Failed to build combined answer")
            print("The combined answer formatter failed. Successful tool results remain available.")
            for name in successful:
                print()
                print(f"Successful tool: {name}")
                print_result(name, question, tool_results.get(name))

        if failed and successful:
            print()
            print("Note: the answer is partial because one or more planned tools failed.")

    print("=" * 60)
    print()


def _build_server_parameters():
    """
    Build MCP stdio parameters while preserving the production-safe
    virtual-environment interpreter behavior.

    The default config value "python" is replaced with sys.executable
    so the MCP server runs under the same environment as the agent.
    A custom BIOMED_MCP_SERVER_COMMAND remains respected.
    """

    configured_command = MCP_SERVER_COMMAND.strip()

    if configured_command.lower() in {"python", "python.exe"}:
        command = sys.executable
    else:
        command = configured_command

    logger.info(
        "MCP server configuration: command=%s script=%s",
        command,
        MCP_SERVER_SCRIPT,
    )

    return StdioServerParameters(
        command=command,
        args=[MCP_SERVER_SCRIPT],
    )


async def main():
    print("=" * 60)
    print("Biomedical Research MCP Agent")
    print("=" * 60)

    server_params = _build_server_parameters()

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            await show_tools(session)

            print("Type a research question.")
            print("The agent can use one or multiple MCP tools for a single question.")
            print("Type 'tools' to show MCP tools.")
            print("Type 'quit' to exit.")
            print()

            while True:
                try:
                    question = input("You: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nGoodbye.")
                    break

                if not question:
                    continue
                if question.lower() in {"quit", "exit"}:
                    print("Goodbye.")
                    break
                if question.lower() == "tools":
                    await show_tools(session)
                    continue

                try:
                    question = validate_question(question)
                    tool_names = plan_tools(question)
                    logger.info("Processing question with tools=%s", tool_names)
                    tool_results = await execute_tool_plan(session, question, tool_names)
                    print_planned_result(question, tool_names, tool_results)
                except AgentInputError as exc:
                    logger.warning("Invalid user input: %s", exc)
                    print(f"\nInput error: {exc}\n")
                except Exception:
                    logger.exception("Unexpected error while executing MCP tool plan")
                    print("\nAn unexpected error occurred while processing the request.")
                    print("Check the console log for technical details.\n")


if __name__ == "__main__":
    asyncio.run(main())
