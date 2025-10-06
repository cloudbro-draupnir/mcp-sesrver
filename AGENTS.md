# Repository Guidelines

## Project Structure & Module Organization
- `src/draupnir_mcp_server/server.py` — MCP server, resources, and tools. CLI: `draupnir-mcp-server`.
- `src/draupnir_mcp_server/ingest.py` — Draupnir ZIP importer. CLI: `cnp-ingest`.
- `tests/` — Pytest suite for tools, validators, and k8s helpers.
- `data/` — Local assets (Cilium policies, rules). Set via `STATIC_MCP_DATA_DIR`.
- `pyproject.toml`, `Makefile`, `uv.lock` — Build and automation config.

## Build, Test, and Development Commands
- `make setup` — Install Python 3.12 and deps via `uv`.
- `make run` — Run MCP over stdio.
- `make run-http` — Run HTTP/SSE server on `0.0.0.0:8765`.
- `make ui` — Launch Streamlit UI (`ui/app.py`).
- `make import ZIP=/path.zip` — Unpack Draupnir ZIP into `data/`.
- `make lint` — Run Ruff; keep warnings at zero.
- `make test` — Run pytest.
- `make package` — Build `dist/draupnir-mcp-server.zip`.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4‑space indents; add type hints for new/changed code.
- Naming: modules/files `snake_case`; functions `snake_case`; classes `PascalCase`; constants `UPPER_SNAKE_CASE`.
- Prefer `pathlib`, small functions, and concise docstrings for MCP tools.
- Lint with `ruff` before pushing.

## MCP Tools
- Add tools in `src/draupnir_mcp_server/server.py` using `@mcp.tool` with a clear docstring and minimal params.
- Keep tools deterministic and scoped to `data/`.
- Key tools: `list_files`, `read_text`, `search_text`, `list_cilium_policies`, `validate_cilium_policy`, `generate_policy_template`, `hubble_filters`, `zero_trust_checklist`, `k8s_context`.
- Add targeted tests when introducing new tools or validators.

## Testing Guidelines
- Framework: `pytest` (configured with `pythonpath=src`).
- Place tests in `tests/test_*.py`; name tests `test_*`.
- Use `tmp_path` and set `STATIC_MCP_DATA_DIR` in tests to isolate data.
- Mock external commands for k8s helpers (use `_run_cmd` monkeypatch pattern).
- Run `make test` locally before opening a PR.

## Commit & Pull Request Guidelines
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`).
- PRs: include purpose/motivation, linked issues, summary of changes, test notes, and local output (e.g., `make test`). Update docs (README/AGENTS.md) when adding tools or commands.

## Security & Configuration Tips
- Access is restricted to `data/`; do not read/write outside it. Always honor `STATIC_MCP_DATA_DIR`.
- Avoid committing secrets; validate YAML defensively.
- Package for distribution with `make package`.
