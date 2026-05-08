# Agent Overseas Report

FastAPI backend for enterprise overseas-plan generation. The service layer keeps
an injectable repository boundary: tests can continue to use the in-memory
repository, while the default API app persists generation projects, plan
versions, audit logs, and report export records to SQLite via SQLAlchemy 2.0.

## Local SQLite startup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. Initialize the local SQLite database and demo enterprise/product data:

   ```bash
   python scripts/init_sqlite_db.py
   ```

   By default the database file is created at `.data/overseas_report.sqlite3`.
   To use another SQLite file, set `OVERSEAS_REPORT_DATABASE_URL`, for example:

   ```bash
   export OVERSEAS_REPORT_DATABASE_URL=sqlite:///./local_overseas_report.sqlite3
   python scripts/init_sqlite_db.py
   ```

3. Start the FastAPI application:

   ```bash
   uvicorn agent_overseas_report.main:app --reload
   ```

The API startup path also creates missing tables and seeds the demo records, so
`python scripts/init_sqlite_db.py` is optional for quick local smoke tests. For
unit tests, instantiate `InMemoryGenerationStore` or use the existing service
test helpers to avoid touching SQLite.

## Persistence tables

The SQLAlchemy metadata defines these tables with shared `id`, `created_at`,
`updated_at`, `status`, and JSON `metadata` columns:

- `enterprises`
- `products`
- `overseas_generation_projects`
- `overseas_plan_versions`
- `overseas_audit_logs`
- `report_exports`
