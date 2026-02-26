# GeoStorm Development

## Architecture

- **Backend**: FastAPI (Python) on port 8080, serves both the API (`/api/*`) and static frontend files from `web/dist/`
- **Frontend**: Astro + React islands in `web/`, built to `web/dist/`
- **Dev server**: Astro dev server on port 4321 with hot reload (proxies `/api` to port 8080)

## Dev Workflow

### Frontend changes visible at localhost:8080

The backend at `http://localhost:8080` serves a **static build** of the frontend from `web/dist/`. It does NOT hot-reload on file changes. After modifying frontend files, you must rebuild and restart:

```bash
cd web && npx astro build          # rebuild static files into web/dist/
kill $(lsof -ti :8080)             # stop backend
cd .. && uv run uvicorn src.main:app --host 0.0.0.0 --port 8080  # restart
```

Alternatively, use `http://localhost:4321` during development — the Astro dev server hot-reloads frontend changes automatically and proxies API calls to the backend.

### Running checks

```bash
uv run pytest tests/ -v                    # backend tests
uv run ruff check src/                     # python linter
cd web && npx tsc --noEmit                 # typescript type check
```
