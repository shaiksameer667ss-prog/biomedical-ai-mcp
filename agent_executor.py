"""MCP tool execution layer for the Biomedical Research MCP Agent."""

import json
import logging
import time

from config import (
    DEFAULT_DOCUMENT_ID,
    MAX_QUESTION_LENGTH,
    MCP_SERVER_COMMAND,
    MCP_SERVER_SCRIPT,
    RESEARCH_TOP_K,
)

from agent_planner import (
    AgentInputError,
    extract_experiment_search_query,
    parse_experiment_filters,
    validate_numeric_dilution_values,
    validate_question,
)

logger = logging.getLogger("biomedical_research_agent")

EXECUTION_STATUS_KEY = "_execution_status"


def parse_mcp_result(result):
    """Normalize an MCP CallToolResult into Python data and reject MCP errors."""
    if result is None:
        logger.error("MCP returned no result.")
        raise ValueError("MCP returned no result.")

    if getattr(result, "is_error", False):
        error_texts = []
        content = getattr(result, "content", None)
        if isinstance(content, list):
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    error_texts.append(str(text))
                elif isinstance(item, str) and item:
                    error_texts.append(item)
        elif isinstance(content, str) and content:
            error_texts.append(content)
        message = "\n".join(error_texts).strip() or "MCP tool reported an error."
        logger.error("MCP tool result marked as error: %s", message)
        raise RuntimeError(message)

    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)

    if structured is not None:
        if isinstance(structured, (dict, list)):
            return structured
        if isinstance(structured, str):
            try:
                return json.loads(structured)
            except json.JSONDecodeError:
                return structured

    if hasattr(result, "content"):
        content = result.content
        if isinstance(content, list):
            texts = []
            for item in content:
                if hasattr(item, "text") and item.text:
                    texts.append(item.text)
                elif isinstance(item, str) and item:
                    texts.append(item)
            if texts:
                text = "\n".join(texts)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        elif isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content

    if isinstance(result, (dict, list, str)):
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return result

    logger.error("Unsupported MCP result type: %s", type(result).__name__)
    raise ValueError(
        f"Unsupported MCP result type: {type(result).__name__}"
    )


def _record_status(results, tool_name, status, error=None):
    """Record execution status separately from the tool result."""
    entry = {"status": status}
    if error:
        entry["error"] = str(error)
    results.setdefault(EXECUTION_STATUS_KEY, {})[tool_name] = entry

    if error:
        logger.error(
            "MCP tool=%s status=%s error=%s",
            tool_name,
            status,
            error,
        )
    else:
        logger.info("MCP tool=%s status=%s", tool_name, status)


def _result_contains_error(result):
    """Return an MCP/tool-level error message when one is present."""
    if isinstance(result, dict):
        value = result.get("error")
        if value:
            return str(value)
    return None


async def execute_tool_plan(session, question, tool_names):
    """Execute every planned tool while isolating individual failures.

    Successful results are retained even when another tool fails. This lets
    the answer layer produce a partial answer instead of losing the entire
    request.
    """
    question = validate_question(question)
    if not tool_names:
        raise AgentInputError("No MCP tool was selected for this question.")

    logger.info(
        "Starting MCP tool plan: tool_count=%d tools=%s",
        len(tool_names),
        ", ".join(tool_names),
    )

    results = {EXECUTION_STATUS_KEY: {}}

    for tool_name in tool_names:
        started = time.perf_counter()
        logger.info("Starting MCP tool=%s", tool_name)

        try:
            result = await execute_tool(session, tool_name, question)
            error_message = _result_contains_error(result)
            if error_message:
                raise RuntimeError(error_message)
            if result is None:
                raise ValueError("Tool returned no usable result.")

            results[tool_name] = result
            _record_status(results, tool_name, "SUCCESS")

            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "Completed MCP tool=%s duration_ms=%.2f",
                tool_name,
                elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "MCP tool=%s failed duration_ms=%.2f",
                tool_name,
                elapsed_ms,
            )
            results[tool_name] = None
            _record_status(results, tool_name, "FAILED", exc)

    logger.info(
        "Completed MCP tool plan: success=%d failed=%d",
        sum(
            1
            for entry in results[EXECUTION_STATUS_KEY].values()
            if entry["status"] == "SUCCESS"
        ),
        sum(
            1
            for entry in results[EXECUTION_STATUS_KEY].values()
            if entry["status"] == "FAILED"
        ),
    )

    return results


async def execute_tool(session, tool_name, question):
    """Execute one supported MCP tool."""
    logger.debug("Dispatching MCP tool=%s", tool_name)

    if tool_name == "search_experiments":
        filters = parse_experiment_filters(question)
        query = "" if filters else extract_experiment_search_query(question)
        arguments = {"query": query, "limit": 10}
        arguments.update(filters)

        print(f"Database text query: {query}")
        print(f"Structured filters: {filters}")

        logger.info(
            "Calling MCP tool=%s with experiment-search filters=%s",
            tool_name,
            filters,
        )
        result = await session.call_tool(tool_name, arguments=arguments)
        return parse_mcp_result(result)

    if tool_name == "search_research_evidence":
        logger.info(
            "Calling MCP tool=%s document_id=%s top_k=%s",
            tool_name,
            DEFAULT_DOCUMENT_ID,
            RESEARCH_TOP_K,
        )
        result = await session.call_tool(
            tool_name,
            arguments={
                "question": question,
                "document_id": DEFAULT_DOCUMENT_ID,
                "top_k": RESEARCH_TOP_K,
            },
        )
        return parse_mcp_result(result)

    if tool_name == "get_research_document":
        logger.info(
            "Calling MCP tool=%s document_id=%s",
            tool_name,
            DEFAULT_DOCUMENT_ID,
        )
        result = await session.call_tool(
            tool_name,
            arguments={"document_id": DEFAULT_DOCUMENT_ID},
        )
        return parse_mcp_result(result)

    if tool_name == "calculate_dilution":
        print("Dilution calculation selected.")
        print("Please provide values in this format:")
        print("stock concentration, desired concentration, final volume")
        user_input = input("Values: ").strip()
        parts = [part.strip() for part in user_input.split(",")]

        if len(parts) != 3:
            logger.warning("Invalid dilution input: expected three values.")
            return {"error": "Please provide exactly three comma-separated values."}

        try:
            stock, desired, final_volume = validate_numeric_dilution_values(
                parts[0], parts[1], parts[2]
            )
        except AgentInputError as exc:
            logger.warning("Invalid dilution input: %s", exc)
            return {"error": str(exc)}

        logger.info("Calling MCP tool=%s for dilution calculation", tool_name)
        result = await session.call_tool(
            tool_name,
            arguments={
                "stock": stock,
                "desired": desired,
                "final_volume": final_volume,
            },
        )
        return parse_mcp_result(result)

    logger.warning("Unsupported MCP tool requested: %s", tool_name)
    return {"error": f"Unsupported tool: {tool_name}"}
