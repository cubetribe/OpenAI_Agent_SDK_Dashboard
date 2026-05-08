# Contributing

Thanks for improving the OpenAI Agent SDK Dashboard.

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run the focused checks before opening a pull request:

```bash
ruff check .
mypy dashboard_service scripts tests
pytest
```

## Pull Request Expectations

- Keep changes small and reviewable.
- Include tests for changed behavior.
- Update documentation when configuration, setup, security, or user-visible behavior changes.
- Do not commit secrets, local context, generated workflow state, trace dumps, prompts, or tenant data.
- Note release impact in the pull request body: major, minor, patch, or none.

## Branching

Use GitHub Flow:

- branch from `main`
- open a pull request
- require CI before merge
- squash merge when approved
