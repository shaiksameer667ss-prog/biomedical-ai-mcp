# Biomedical AI MCP

A local Biomedical Research Assistant and Model Context Protocol (MCP) server for structured experiment data and evidence-based research-document retrieval.

## Overview

This project combines a Python MCP server, a deterministic research agent, a SQLite database, PDF extraction, and local evidence retrieval.

The system is designed as a portfolio project demonstrating practical skills in:

- Python application design
- MCP server/tool development
- Biomedical research data handling
- SQLite database integration
- PDF text extraction
- Local evidence retrieval
- Deterministic tool planning
- Multi-tool execution and failure isolation
- Evidence provenance and validation
- Production-oriented logging
- Automated testing

The current implementation is intentionally local and does not require a paid external LLM or paid embedding API.

## Architecture

```text
User
  |
  v
Biomedical Research Agent
  |
  +--> Planner
  |      |
  |      +--> selects MCP tools
  |
  +--> Executor
  |      |
  |      +--> executes tools
  |      +--> isolates failures
  |      +--> records execution status
  |      +--> logs execution events
  |
  +--> Validator
  |      |
  |      +--> checks cross-tool alignment
  |
  +--> Answer Generator
         |
         +--> evidence
         +--> experiments
         +--> document metadata
         +--> provenance
                  |
                  v
             MCP Server
                  |
       +----------+-----------+
       |          |           |
       v          v           v
   Research   Experiment   Document
     Tools       Tools       Tools
       |          |           |
       +----------+-----------+
                  |
          +-------+-------+
          |               |
          v               v
      SQLite DB       Research PDFs
                          |
                          v
                 PDF text extraction
                          |
                          v
                Local evidence retrieval
```

See [`docs/architecture.md`](docs/architecture.md) for the detailed architecture description.

## Main Components

### MCP Server

`server.py` exposes the biomedical capabilities through MCP.

Current MCP tools:

1. `calculate_dilution`
2. `get_experiment`
3. `search_experiments`
4. `add_experiment`
5. `get_research_document`
6. `add_research_document`
7. `extract_pdf_text`
8. `get_research_content`
9. `search_research_content`
10. `search_research_evidence`

Current MCP resources:

- `research://experiments`
- `research://experiments/{experiment_id}`
- `research://documents`
- `research://documents/{document_id}`
- `research://documents/{document_id}/content`
- `research://documents/{document_id}/pages/{page_number}`

### Agent

The agent is split into focused modules:

- `agent.py` — compatibility entry point
- `agent_app.py` — application flow and MCP connection
- `agent_planner.py` — deterministic intent detection and tool planning
- `agent_executor.py` — MCP tool execution and failure isolation
- `agent_validator.py` — cross-tool validation
- `agent_answer.py` — research-answer formatting

### Data Layer

- `database.py` — SQLite database operations
- `biomedical.db` — project database
- `documents/` — research PDFs
- `retrieval.py` — local evidence retrieval

## Research Workflow

A research question follows this general path:

1. The user submits a biomedical research question.
2. The planner identifies the required tool domain.
3. The planner selects one or more MCP tools.
4. The executor calls the selected tools.
5. Individual tool failures are isolated so successful results can still be used.
6. Research evidence is retrieved from extracted document pages.
7. Experiment data can be retrieved from SQLite.
8. The validator checks relationships between retrieved evidence and database experiments.
9. The answer generator produces a structured response with evidence and provenance.

For combined questions, the planner can execute multiple domains in a deterministic order.

Example:

> What mechanisms are involved in copper nanoparticle toxicity, and what related experiments are in the database?

This can result in:

```text
search_research_evidence
search_experiments
```

The answer can then distinguish literature evidence from database experiment metadata instead of treating them as the same source.

## Local Evidence Retrieval

The project uses a local retrieval implementation in `retrieval.py`.

It:

- loads extracted document pages
- tokenizes and expands research questions
- detects biomedical concepts and mechanisms
- scores relevant pages
- creates evidence snippets
- returns page-level provenance

The current implementation is deliberately lightweight and deterministic. It does not depend on a paid external embedding service.

This makes the project reproducible in a local development environment, while also making its limitations explicit: the retrieval system is not equivalent to a large-scale neural semantic-search stack.

## Example Evidence Domains

The current research workflow includes concepts such as:

- oxidative stress
- reactive oxygen species (ROS)
- mitochondrial damage
- lipid peroxidation
- DNA damage
- apoptosis
- cell membrane damage
- cell death and reduced viability

The answer layer preserves the distinction between direct and supporting evidence where available.

## Database

The SQLite database contains structured experiment metadata.

The current experiment schema includes:

- `experiment_id`
- `name`
- `cell_type`
- `treatment`
- `organism`
- `test`
- `duration_hours`

The database layer uses parameterized SQL and validation rather than interpolating user-controlled values directly into SQL statements.

## PDF Research Pipeline

Research documents are registered in the database and can be processed through the MCP server.

The extraction workflow is:

```text
PDF
 |
 v
PDF metadata
 |
 v
pypdf text extraction
 |
 +--> full document content
 |
 +--> page-level content
 |
 v
SQLite storage
 |
 v
local evidence retrieval
```

The project includes a research PDF related to copper nanoparticle toxicity.

## Error Handling

The agent is designed so that one failed tool does not necessarily invalidate the complete request.

Execution status is tracked separately:

```text
_execution_status
    |
    +--> tool A: SUCCESS
    |
    +--> tool B: FAILED
```

This allows the answer layer to distinguish complete and partial results.

MCP-level error results are also detected explicitly.

## Observability

Logging is centralized through `config.py`.

The application records operational events such as:

- tool-plan start and completion
- individual tool start and completion
- execution duration
- successful tool execution
- failed tool execution
- MCP errors
- unsupported tool requests

The executor intentionally avoids logging the complete research question.

Logging configuration is not duplicated across individual modules.

## Configuration

Configuration is centralized in `config.py` and can be controlled through environment variables.

Important settings include:

- `BIOMED_DATABASE_PATH`
- `BIOMED_DOCUMENTS_DIR`
- `BIOMED_DEFAULT_DOCUMENT_ID`
- `BIOMED_RESEARCH_TOP_K`
- `BIOMED_MAX_QUESTION_LENGTH`
- `BIOMED_LOG_LEVEL`
- `BIOMED_MCP_SERVER_COMMAND`
- `BIOMED_MCP_SERVER_SCRIPT`

See `.env.example` for the supported configuration pattern.

## Requirements

The current project targets:

- Python 3.14
- MCP Python SDK 2.1.1
- pypdf 6.17.0
- SQLite
- uv (recommended for environment management)

The MCP server can be inspected with the MCP development tooling.

## Setup

From the project directory:

```cmd
uv sync
```

Or, if the existing virtual environment is already configured:

```cmd
.venv\Scripts\activate
```

The project currently uses a local SQLite database and local PDF files.

## Run the MCP Server

The standard development command is:

```cmd
uv run mcp dev server.py
```

This opens the MCP development/inspection workflow and allows the exposed tools and resources to be inspected.

## Run the Agent

From the project directory:

```cmd
.venv\Scripts\python.exe agent.py
```

The agent connects to the MCP server using the current Python interpreter.

## Run Tests

Run the complete suite:

```cmd
.venv\Scripts\python.exe run_all_tests.py
```

The current verified baseline is:

```text
Tests run: 126
Failures:  0
Errors:    0
```

The test suite covers configuration, security, SQL safety, PDF limits, MCP behavior, planning, execution failure handling, answer quality, logging, and observability.

## Example Questions

### Research evidence

```text
What mechanisms are involved in copper nanoparticle toxicity?
```

### Research + experiments

```text
What mechanisms are involved in copper nanoparticle toxicity, and what related experiments are in the database?
```

### Experiment search

```text
Which experiments use doxorubicin?
```

### Document information

```text
Show me the research document.
```

### Combined document + evidence

```text
Show me the paper and tell me what it says about apoptosis.
```

## Security and Safety Considerations

The project includes defensive controls around:

- SQL query construction
- input validation
- numeric validation
- document identifiers
- PDF processing
- tool limits
- MCP errors
- unsupported tools
- execution failures

The system should still be treated as a research-support prototype rather than a clinical decision-support system.

It does not establish clinical efficacy, safety, diagnosis, or treatment recommendations.

## Current Limitations

This is a portfolio/research prototype.

Known limitations include:

- local deterministic retrieval rather than a production-scale vector database
- limited document corpus
- SQLite rather than a production database service
- deterministic planning rather than a general-purpose LLM planner
- no authentication layer for a deployed multi-user service
- no production web UI
- no clinical validation
- evidence retrieval quality depends on the indexed document content

These limitations are intentional and documented rather than hidden.

## Project Structure

```text
biomedical-ai-mcp/
|
+-- agent.py
+-- agent_app.py
+-- agent_answer.py
+-- agent_executor.py
+-- agent_planner.py
+-- agent_validator.py
|
+-- server.py
+-- database.py
+-- retrieval.py
+-- config.py
|
+-- biomedical.db
+-- documents/
|
+-- tests/
+-- docs/
|
+-- .env.example
+-- .gitignore
+-- CONTRIBUTING.md
+-- LICENSE
+-- pyproject.toml
+-- README.md
+-- run_all_tests.py
```

Legacy and experimental files are kept separately under `archive/legacy/` rather than mixed into the production-facing project structure.

## Roadmap

The project roadmap includes:

- production documentation
- architecture documentation
- Git/GitHub preparation
- final end-to-end demonstration
- stronger retrieval strategies
- broader document collections
- additional biomedical tools
- optional LLM-based agent orchestration
- deployment hardening

## Portfolio Positioning

This project demonstrates an end-to-end biomedical AI engineering workflow rather than a single isolated model.

The strongest portfolio themes are:

- MCP protocol implementation
- biomedical research workflows
- tool-using agent architecture
- local retrieval/RAG concepts
- structured data + unstructured documents
- multi-tool orchestration
- evidence provenance
- defensive engineering
- automated testing
- production-oriented observability

## License

See [`LICENSE`](LICENSE).
