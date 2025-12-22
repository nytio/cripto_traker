# Repository Guidelines

## Project Structure & Module Organization
- `web/app/`: Flask app. `routes/` blueprints, `services/` API logic, `templates/` Jinja pages, `static/` CSS/JS, `scripts/` scheduler jobs, `models.py` data model, `db.py` DB init, `config.py` env config.
- `tests/`: pytest suite for routes, services, and analytics.
- `nginx/`: optional reverse proxy config and TLS certs.
- Root: `docker-compose.yml`, `.env.example`, `web/Dockerfile`.

## Build, Test, and Development Commands
- `cp .env.example .env` set local configuration.
- `docker compose up --build` start web + Postgres; app at `http://localhost:8000`.
- `docker compose --profile scheduler up --build` run the daily update scheduler.
- `docker compose --profile nginx up --build` run HTTPS proxy (requires `nginx/certs/*`).
- `pip install -r web/requirements.txt -r requirements-dev.txt` install deps for local tests.
- `PYTHONPATH=web pytest` run the test suite.

## Coding Style & Naming Conventions
- Python uses 4-space indentation and PEP 8 conventions.
- Use `snake_case` for functions/variables, `CapWords` for classes, and keep blueprints named `bp` in `web/app/routes/*.py`.
- Templates live in `web/app/templates/` and static assets in `web/app/static/` (e.g., `static/css/app.css`).

## Testing Guidelines
- Framework: pytest 7.x; files named `tests/test_*.py`.
- Prefer fixtures from `tests/conftest.py` (`app`, `client`) and keep tests isolated from external APIs.
- Add tests for new routes and service logic.

## Commit & Pull Request Guidelines
- Commit messages are short Spanish descriptions in sentence case (no prefixes), e.g., "Pausa entre actualizacion de criptos".
- PRs should include: summary, test command(s) run, and screenshots for UI changes; link issues if available.

## Security & Configuration Tips
- Never commit secrets; keep values in `.env`.
- Update `.env.example` when adding new required variables.
- The database is internal to Compose; avoid exposing new ports without a clear reason.
