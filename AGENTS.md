# Repository Guidelines

## Overview
This project is a Flask web application for generating natal charts. Automated tests live under `tests/` and depend on the packages listed in `requirements.txt` and `requirements-dev.txt`.

## Development
- Use Python 3.12 or later.
- Follow PEP8 formatting (4‑space indents, lines <= 100 chars).
- Commit messages must be short (\<=72 chars) and written in imperative mood.
- Do not add or modify files inside `saved_charts/` or `dist/`.
- Avoid committing binary icon files. Keep `icons/` empty unless otherwise instructed.

## Testing
Before committing changes:
1. Install dependencies: `pip install -r requirements.txt -r requirements-dev.txt`.
2. Run `pytest` from the repository root and ensure all tests pass.

## Pull Requests
Summaries should briefly describe the changes made and mention the test results.
