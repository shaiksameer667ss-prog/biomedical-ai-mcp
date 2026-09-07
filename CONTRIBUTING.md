# Contributing

Thank you for contributing to the Biomedical Research MCP Server.

This repository is primarily a portfolio and educational project, but changes should still follow normal software-engineering practices.

## Development environment

Requirements:

- Python 3.14
- `uv`
- Git

Install the locked dependencies:

```bash
uv sync --locked
```

## Before making changes

Create a feature branch:

```bash
git checkout -b feature/short-description
```

Keep changes focused. Avoid mixing unrelated refactors with feature or bug-fix work.

## Testing

Run the complete test suite before committing:

```bash
uv run python run_all_tests.py
```

The expected baseline is:

```text
Ran 70 tests
OK
```

You can also run a syntax check:

```bash
uv run python -m py_compile server.py
```

GitHub Actions runs the test suite automatically on pushes to `main` and pull requests targeting `main`.

## MCP development

For MCP inspection:

```bash
uv run mcp dev server.py
```

For the interactive research agent:

```bash
uv run python agent.py
```

## Security expectations

Do not weaken existing validation without a clear reason.

Pay particular attention to:

- SQL parameterization
- SQLite identifier allowlisting
- document ID validation
- PDF filename/path validation
- path traversal protection
- file-size and extracted-text limits
- question/tool argument limits
- safe public error messages

If a security-sensitive behavior changes, add or update a regression test.

## Configuration

Do not commit:

- `.env` files
- SQLite databases
- private research PDFs
- credentials or API keys
- local virtual environments

Use `.env.example` as the reference for supported environment variables.

## Commit messages

Use short, descriptive commit messages.

Examples:

```text
Add PDF extraction limits
Fix experiment filter parsing
Improve evidence provenance output
Update CI test workflow
```

## Pull requests

A useful pull request should explain:

1. What changed
2. Why it changed
3. How it was tested
4. Any security or compatibility impact

Before opening a pull request, confirm that the local test suite passes and that no generated/local runtime files are accidentally tracked.
