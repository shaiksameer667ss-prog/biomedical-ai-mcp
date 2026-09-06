import os


# MCP server configuration
MCP_SERVER_COMMAND = os.getenv("BIOMED_MCP_SERVER_COMMAND", "python")
MCP_SERVER_SCRIPT = os.getenv("BIOMED_MCP_SERVER_SCRIPT", "server.py")


# Research configuration
DEFAULT_DOCUMENT_ID = os.getenv("BIOMED_DEFAULT_DOCUMENT_ID", "DOC001")

try:
    RESEARCH_TOP_K = int(os.getenv("BIOMED_RESEARCH_TOP_K", "5"))
except ValueError:
    RESEARCH_TOP_K = 5


# Input configuration
try:
    MAX_QUESTION_LENGTH = int(
        os.getenv("BIOMED_MAX_QUESTION_LENGTH", "2000")
    )
except ValueError:
    MAX_QUESTION_LENGTH = 2000


# Logging configuration
LOG_LEVEL = os.getenv("BIOMED_LOG_LEVEL", "INFO").upper()