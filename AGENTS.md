# Repository Guidelines

## Project Structure & Module Organization
- `backend/` contains the FastAPI service. Core modules: `backend/app/api`, `app/core`, `app/strategies`, `app/live`, `app/backtest`, `app/agent`, and `app/assistant_runtime`.
- Backend tests live in `backend/tests/`; `backend/test_data.py` is a manual script and is not collected by pytest.
- `frontend/` contains the Electron + Vue 3 app: `src/main` (Electron main), `src/preload` (bridge), and `src/renderer` (views, components, stores, services, composables, assets).
- Runtime/config paths: `config/` for env templates, `data/` for local SQLite/runtime data, `logs/` for log output, and `tools/` for utility scripts.

## Build, Test, and Development Commands
- `install.bat` / `./install.sh`: install backend and frontend dependencies.
- `start.bat` / `./start.sh`: run FastAPI, Vite, and Electron together.
- `reset.bat` / `./reset.sh`: clear local runtime state.
- `cd backend && uv sync`: install backend Python packages.
- `cd backend && uv run python run.py`: start backend server.
- `cd backend && uv run pytest`: run backend tests.
- `cd frontend && npm install`: install frontend dependencies.
- `cd frontend && npm run dev`: run Electron + renderer locally.
- `cd frontend && npm run build`: build renderer and package Electron.
- `node --test frontend/tests/*.test.mjs tools/tests/*.test.mjs`: run JS tests using Node’s built-in test runner.

## Coding Style & Naming Conventions
- Follow the existing style in each folder; do not introduce a new formatting pattern.
- Python: 4-space indentation, `snake_case`, small focused modules.
- Frontend: existing single-quote and semicolon style.
- Use `PascalCase` for Vue views (`MarketView.vue`) and lowercase file names for stores/services (`stores/app.js`, `services/api.js`).
- No dedicated lint script exists; format code to match nearby files.

## Testing Guidelines
- Backend uses `pytest` and `pytest-asyncio`, with tests discovered from `backend/tests/test_*.py` via `backend/pytest.ini`.
- Add or update tests for each behavior change, especially API, assistant runtime, and data/storage paths.
- Keep tests deterministic: avoid live network calls, real credentials, and writes to production-like data.

## Commit & Pull Request Guidelines
- Recent history uses short Chinese summaries (for example, `优化交易系统`, `优化`). Keep commit messages brief, imperative, and scoped.
- PRs should state touched modules, key risks, and validation commands run.
- Include screenshots/recordings for UI changes and note any config, schema, or credential impact.

## Security & Configuration Tips
- Copy `config/.env.example` to `config/.env`; never commit OKX keys.
- Default to simulated trading for development.
- Avoid committing local runtime artifacts such as database files and logs (for example, `data/market.db`, `logs/*`) unless they are deliberate fixtures.
