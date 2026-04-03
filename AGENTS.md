# Repository Guidelines

## Project Structure & Module Organization
`backend/` holds the FastAPI service. Main areas are `backend/app/api`, `app/core`, `app/strategies`, `app/live`, `app/backtest`, `app/agent`, and `app/assistant_runtime`. Tests live in `backend/tests/`; `backend/test_data.py` is a manual script, not part of pytest. `frontend/` contains the Electron + Vue 3 client: `src/main` for Electron, `src/preload` for the bridge, and `src/renderer` for views, components, stores, services, composables, and assets. Use `config/` for env files, `data/` for local SQLite/runtime data, `logs/` for logs, and `tools/` for utilities.

## Build, Test, and Development Commands
- `install.bat`: install backend and frontend dependencies on Windows.
- `start.bat`: run FastAPI, Vite, and Electron together.
- `reset.bat`: clear local runtime state.
- `cd backend && uv sync`: install Python packages.
- `cd backend && uv run python run.py`: start the backend.
- `cd backend && uv run pytest`: run backend unit tests.
- `cd frontend && npm install`: install frontend packages.
- `cd frontend && npm run dev`: launch Vite and Electron.
- `cd frontend && npm run build`: build the renderer and package Electron.

## Coding Style & Naming Conventions
Follow the existing style instead of introducing a new one. Python uses 4-space indentation, `snake_case`, and small focused modules. Frontend code follows the current single-quote and semicolon style. Use `PascalCase` for Vue views such as `MarketView.vue`, and lowercase names for stores and services such as `stores/app.js` and `services/api.js`. No dedicated lint script exists, so keep formatting aligned with nearby code.

## Testing Guidelines
Backend tests use `pytest` and `pytest-asyncio`, collected from `backend/tests/test_*.py` by `backend/pytest.ini`. Add or update tests for each behavior change, especially API, assistant runtime, and data/storage paths. Keep tests deterministic and avoid live network calls, real credentials, or writes to production-like data.

## Commit & Pull Request Guidelines
Recent history uses short Chinese summaries such as `优化交易系统`. Keep commit messages brief, imperative, and scoped to one change. Pull requests should describe the touched module, risk, and validation commands. Include screenshots or recordings for UI changes and note any config, schema, or credential impact.

## Security & Configuration Tips
Copy `config/.env.example` to `config/.env`; never commit OKX keys. Default to simulated trading for development. Avoid committing `data/market.db`, generated logs, or other local runtime artifacts unless they are deliberate fixtures.
