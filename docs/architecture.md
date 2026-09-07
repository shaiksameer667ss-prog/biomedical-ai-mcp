# System Architecture

## Purpose

The Biomedical AI MCP project connects structured biomedical experiment data and unstructured research documents through an MCP interface and a deterministic research-agent layer.

## High-Level Flow

```text
User Question
     |
     v
agent_app.py
     |
     v
agent_planner.py
     |
     |  deterministic tool plan
     v
agent_executor.py
     |
     +--------------------+
     |                    |
     v                    v
MCP Server           Execution Status
server.py
     |
     +------------------+-------------------+
     |                  |                   |
     v                  v                   v
Experiment Tools   Research Tools     Document Tools
     |                  |                   |
     v                  v                   v
SQLite             retrieval.py       PDF/content
     |                  |                   |
     +------------------+-------------------+
                        |
                        v
                 agent_validator.py
                        |
                        v
                  agent_answer.py
                        |
                        v
                 Structured Answer
```

## Agent Layer

### Planner

`agent_planner.py` determines which MCP tools are needed.

Planning is deterministic and supports multiple domains. For example, a question requesting both research mechanisms and related experiments can select:

```text
search_research_evidence
search_experiments
```

The planner avoids duplicate tools and uses a deterministic ordering.

### Executor

`agent_executor.py` executes the selected tools.

Important behavior:

- validates the question
- dispatches supported tools
- normalizes MCP results
- detects MCP `is_error` results
- detects tool-level error dictionaries
- isolates individual failures
- records per-tool execution status
- logs execution lifecycle events
- measures tool duration

A failure in one tool does not automatically discard successful results from other tools.

### Validator

`agent_validator.py` checks relationships between retrieved evidence and structured experiment information.

The validation layer is designed to prevent an important research mistake: treating a literature statement as proof that a particular database experiment produced the same result.

### Answer Generator

`agent_answer.py` formats evidence, experiments, document metadata, validation, and provenance into a structured research response.

## MCP Server Layer

`server.py` exposes the biomedical capabilities through MCP.

### Tool categories

**Experiment**

- `get_experiment`
- `search_experiments`
- `add_experiment`

**Research document**

- `get_research_document`
- `add_research_document`
- `extract_pdf_text`
- `get_research_content`
- `search_research_content`
- `search_research_evidence`

**Utility**

- `calculate_dilution`

### Resource categories

**Experiments**

```text
research://experiments
research://experiments/{experiment_id}
```

**Documents**

```text
research://documents
research://documents/{document_id}
research://documents/{document_id}/content
research://documents/{document_id}/pages/{page_number}
```

## Data Layer

### SQLite

`database.py` provides the structured experiment/document data layer.

The main database is:

```text
biomedical.db
```

Experiment records contain identifiers and research attributes such as cell type, treatment, organism, test, and duration.

### Research Documents

PDFs are stored under:

```text
documents/
```

The extraction pipeline uses `pypdf` to convert PDF pages into searchable text.

## Retrieval Layer

`retrieval.py` implements local evidence retrieval.

The pipeline can be summarized as:

```text
Question
   |
   v
Cleaning + tokenization
   |
   v
Biomedical concept detection
   |
   v
Mechanistic query expansion
   |
   v
Page scoring
   |
   v
Relevant pages
   |
   v
Evidence snippets + provenance
```

The current implementation uses deterministic lexical/concept-based scoring. It is intentionally local and does not require paid embedding APIs.

## Observability

Logging is configured centrally in:

```text
config.py
```

Modules obtain named loggers but do not independently configure the root logging system.

The executor logs:

```text
tool-plan start
tool start
tool completion
tool duration
tool failure
tool-plan completion
```

The complete user research question is deliberately excluded from executor lifecycle logs.

## Failure Isolation

The execution result contains a dedicated status structure:

```text
_execution_status
    search_research_evidence
        status: SUCCESS

    search_experiments
        status: FAILED
        error: ...
```

This allows the application to continue with successful results while clearly exposing partial failures.

## Security Boundaries

The project applies validation at several layers:

```text
User Input
   |
   v
Question validation
   |
   v
Planner
   |
   v
Tool argument validation
   |
   v
MCP server
   |
   v
Database / document layer
```

SQL operations use parameterized queries and controlled column/filter handling.

Document operations validate document identifiers and file paths before processing.

## Deployment Direction

The current architecture is local and single-user oriented.

A future production deployment could separate:

```text
Client / UI
     |
     v
Agent service
     |
     v
MCP service
     |
     +--> production database
     |
     +--> document/object storage
     |
     +--> retrieval service
     |
     +--> authentication / authorization
     |
     +--> centralized observability
```

Those capabilities are not claimed as implemented in the current version.
