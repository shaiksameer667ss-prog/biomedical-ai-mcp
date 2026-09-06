# Biomedical Research MCP Server

A biomedical research assistant built around the **Model Context Protocol (MCP)**.

The project combines structured biomedical experiment data, research-document ingestion, local evidence retrieval, validation, provenance tracking, and scientific utility tools into an MCP-based workflow.

## Overview

The server provides tools for:

- Searching biomedical experiments stored in SQLite
- Retrieving individual experiments
- Adding experiment records
- Registering research documents
- Extracting text from PDF research documents
- Searching extracted research content
- Retrieving mechanism-focused research evidence
- Performing dilution calculations
- Combining multiple tools to answer research questions
- Checking whether retrieved evidence is aligned with the requested experimental context
- Reporting evidence provenance and strength

The current retrieval system is fully local and does not require a paid external embedding API.

## Architecture

```text
                         User Question
                              |
                              v
                       +--------------+
                       | Python Agent |
                       +------+-------+
                              |
                         Tool Planning
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
      Experiment Search   Research RAG    Document Tools
             |                |                |
             v                v                v
         SQLite DB       PDF Content       documents/
                              |
                              v
                     Evidence Extraction
                              |
                              v
                    Cross-Tool Validation
                              |
                              v
                       Provenance Layer
                              |
                              v
                         Final Answer
```

## MCP Server

The MCP server exposes tools and resources for biomedical research workflows.

### Tools

| Tool | Purpose |
|---|---|
| `calculate_dilution` | Calculate stock and diluent volumes using the dilution equation |
| `get_experiment` | Retrieve an experiment by ID |
| `search_experiments` | Search experiments using text and structured filters |
| `add_experiment` | Add a validated experiment record |
| `get_research_document` | Retrieve document metadata |
| `add_research_document` | Register a research document |
| `extract_pdf_text` | Extract and store PDF text and page content |
| `get_research_content` | Retrieve extracted document content |
| `search_research_content` | Search extracted research content |
| `search_research_evidence` | Retrieve mechanism-focused evidence for a research question |

### Resources

The server exposes research data through MCP resources including:

```text
research://experiments
research://experiments/{experiment_id}

research://documents
research://documents/{document_id}
research://documents/{document_id}/content
research://documents/{document_id}/pages/{page_number}
```

## Research Retrieval Pipeline

The research workflow is designed to avoid treating every text match as scientific evidence.

```text
Research Question
       |
       v
Query expansion
       |
       v
Concept / mechanism detection
       |
       v
Page retrieval
       |
       v
Sentence-level evidence scoring
       |
       v
Topic relevance validation
       |
       v
Mechanism-specific filtering
       |
       v
Evidence strength classification
       |
       v
Provenance
```

Evidence can be classified as:

- **DIRECT** — the requested topic and mechanism are explicitly supported by the evidence sentence.
- **SUPPORTING** — the mechanism is explicit, while part of the topic linkage comes from page context.
- **WEAK/INDIRECT** — the mechanism is explicit but the requested topic linkage is limited.

The system also reports the document, page, evidence sentence, mechanism, and retrieval/topic scores.

## Cross-Tool Validation

When a question requires both experiment data and research evidence, the agent checks alignment across dimensions such as:

- Treatment
- Cell model
- Duration
- Mechanism

For example, an experiment involving doxorubicin should not silently be combined with evidence that only concerns copper nanoparticles.

The validation layer can distinguish:

```text
MATCH
PARTIALLY ALIGNED
NOT ALIGNED
NOT CONFIRMED
```

This is a transparent consistency check, not independent scientific validation.

## Security and Production Hardening

The server includes several defensive controls:

- Input validation
- Question length limits
- Tool argument length limits
- Search result limits
- Evidence `top_k` limits
- Experiment field limits
- Document title/description limits
- Document ID validation
- PDF filename validation
- PDF type validation
- Path traversal protection
- Absolute-path rejection
- Document-directory containment checks
- File-size limits
- Extracted-text limits
- Page-text limits
- SQLite identifier allowlisting
- Parameterized SQL values
- Generic public error messages
- Internal error logging
- Configuration through environment variables

## Project Structure

The current working layout intentionally keeps application modules at the project root so the existing test suite and MCP development workflow remain simple.

```text
biomedical-ai-mcp/
|
|-- server.py
|-- agent.py
|-- retrieval.py
|-- config.py
|-- run_all_tests.py
|
|-- biomedical.db
|
|-- documents/
|   `-- copper_nanoparticle_study.pdf
|
|-- test_agent_alignment.py
|-- test_production_hardening.py
|-- test_config.py
|-- test_config_integration.py
|-- test_security.py
|-- test_security_mcp.py
|-- test_sql_security.py
|-- test_error_safety.py
`-- test_tool_limits.py
```

A future refactor can move tests into a dedicated `tests/` package after import paths and CI configuration are updated.

## Requirements

Recommended environment:

- Windows
- Python 3.14
- `uv`
- MCP Python SDK 2.x
- SQLite
- Node.js only if using optional Claude Code tooling

The project does not require a paid LLM or paid embedding API for its current local retrieval workflow.

## Installation

From the project directory:

```cmd
uv sync
```

If the environment has not yet been created:

```cmd
uv venv
uv sync
```

## Running the MCP Server

The server can be developed and inspected with the MCP development tooling:

```cmd
uv run mcp dev server.py
```

The MCP Inspector should connect to the server and expose the available tools and resources.

For stdio execution, the server uses the MCP SDK's asynchronous stdio runner.

## Running the Agent

Run the Python research agent with:

```cmd
uv run python agent.py
```

The agent accepts research questions and plans the appropriate MCP tool calls.

Example questions:

```text
Which experiments used liver cells?

Which experiment tested doxorubicin on liver cells for two days?

What mechanisms are involved in copper nanoparticle toxicity?

Which experiment tested doxorubicin on liver cells for two days, and what does the research document say about the mechanisms of toxicity?
```

For combined questions, the agent can execute multiple tools and then perform cross-tool relevance checks before presenting the result.

## Running Tests

Run the complete automated test suite:

```cmd
uv run python run_all_tests.py
```

The current production-hardening baseline is:

```text
67 tests
OK
```

Before committing future changes, the full test suite should continue to pass.

A syntax check can also be run with:

```cmd
uv run python -m py_compile server.py
```

## Configuration

Configuration is controlled through environment variables.

| Variable | Purpose | Default |
|---|---|---|
| `BIOMED_MCP_SERVER_COMMAND` | MCP server command | `python` |
| `BIOMED_MCP_SERVER_SCRIPT` | MCP server script | `server.py` |
| `BIOMED_DEFAULT_DOCUMENT_ID` | Default research document | `DOC001` |
| `BIOMED_RESEARCH_TOP_K` | Number of evidence results | `5` |
| `BIOMED_MAX_QUESTION_LENGTH` | Maximum agent question length | `2000` |
| `BIOMED_LOG_LEVEL` | Logging level | `INFO` |

Example:

```cmd
set BIOMED_RESEARCH_TOP_K=8
uv run python agent.py
```

## Example Research Workflow

A multi-tool research question can follow this pattern:

```text
User question
     |
     v
Agent identifies required tools
     |
     +--> search_experiments
     |
     +--> search_research_evidence
     |
     v
Compare experiment and evidence context
     |
     v
Check treatment/cell model/duration/mechanism alignment
     |
     v
Return findings with evidence provenance
```

If the evidence is about a different treatment from the experiment, the agent reports the mismatch instead of presenting unrelated evidence as if it supported the experiment.

## Current Research Dataset

The example database includes experiments such as:

- Cytotoxicity study using copper nanoparticles on skin cells
- Antimicrobial susceptibility study using bacterial culture
- Drug cytotoxicity study using doxorubicin on liver cells

The example research document is a review concerning manufactured copper nanoparticles and their toxicological mechanisms.

## Limitations

This is a portfolio and research-assistance project, not a clinical decision-support system.

Important limitations include:

- Local retrieval is not equivalent to a production vector database.
- Evidence retrieval does not establish causality.
- Topic alignment is not independent scientific verification.
- The example dataset is small.
- The current system does not replace expert literature review.
- Scientific conclusions depend on the source documents available to the system.

## Future Improvements

Planned production-oriented improvements include:

1. Cleaner package/module structure
2. Additional automated tests for PDF size and extraction limits
3. Continuous integration
4. More comprehensive database initialization
5. Larger research-document datasets
6. Optional local embedding/vector retrieval
7. Improved document provenance
8. More robust observability
9. Authentication/authorization for network deployments
10. Containerized deployment
11. API/MCP deployment documentation
12. Evaluation datasets for retrieval quality

## Portfolio Value

This project demonstrates practical experience with:

- Python
- MCP
- AI agent tool planning
- Retrieval-augmented research workflows
- Biomedical informatics
- SQLite
- PDF processing
- Information retrieval
- Evidence extraction
- Data validation
- Cross-tool reasoning
- Security hardening
- Configuration management
- Automated testing
- Software engineering practices

## License

This project is intended as a portfolio/educational software project. See `LICENSE` for the current license terms.
