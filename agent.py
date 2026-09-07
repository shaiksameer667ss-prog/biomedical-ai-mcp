"""Compatibility entry point for the Biomedical Research MCP Agent."""

import asyncio

# Keep the main configuration contract visible from the compatibility entry point.
# These imports also make the configured values discoverable to regression tests
# and to tools that inspect the agent entry point.
from config import (
    DEFAULT_DOCUMENT_ID,
    LOG_LEVEL,
    MAX_QUESTION_LENGTH,
    MCP_SERVER_COMMAND,
    MCP_SERVER_SCRIPT,
    RESEARCH_TOP_K,
)

from agent_planner import *  # noqa: F401,F403
from agent_executor import *  # noqa: F401,F403
from agent_answer import *  # noqa: F401,F403
from agent_validator import *  # noqa: F401,F403
from agent_app import main, show_tools, print_planned_result  # noqa: F401

if __name__ == "__main__":
    asyncio.run(main())
