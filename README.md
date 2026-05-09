# Agent Overseas Report

FastAPI backend for enterprise overseas-plan generation. The default local app
uses SQLite, a deterministic demo LLM when `DEEPSEEK_API_KEY` is empty, and a
local hashing embedder for knowledge-base retrieval. Real API keys are read only
from environment variables or a local `.env` file that must not be committed.

## Configuration and security

1. Copy the sample configuration and edit local values:

   ```bash
   cp .env.example .env
   ```

2. Keep secrets out of Git:
   - `.env` and `.env.*` are ignored by `.gitignore`.
   - Leave `DEEPSEEK_API_KEY=` empty for offline local smoke tests.
   - Set `DEEPSEEK_API_KEY` only in your local shell, `.env`, or server secret
     manager when you want to call DeepSeek.

3. Main environment variables:

   | Variable | Purpose | Default |
   | --- | --- | --- |
   | `OVERSEAS_REPORT_DATABASE_URL` | SQLAlchemy database URL | `sqlite:///.data/overseas_report.sqlite3` |
   | `DEEPSEEK_API_KEY` | DeepSeek API key; empty means demo LLM | empty |
   | `DEEPSEEK_BASE_URL` | DeepSeek OpenAI-compatible endpoint | `https://api.deepseek.com` |
   | `DEEPSEEK_MODEL` | Chat model name | `deepseek-chat` |
   | `EMBEDDING_PROVIDER` | Embedding implementation selector | `local_hashing` |
   | `EMBEDDING_DIMENSIONS` | Local hashing embedding vector size | `384` |
   | `ENABLE_CREWAI` | Opt-in multi-agent orchestration | `false` |
   | `ENABLE_WEB_RESEARCH` | Opt-in web research hook | `false` |
   | `MAX_UPLOAD_BYTES` | Knowledge-file upload size limit | `20971520` |
   | `ALLOWED_UPLOAD_EXTENSIONS` | Upload extension whitelist | `.pdf,.docx,.xlsx,.pptx,.md,.txt` |
   | `ALLOWED_UPLOAD_MIME_TYPES` | Upload MIME whitelist | common PDF/Office/text types |
   | `LOG_LEVEL` | Python logging level | `INFO` |

The configuration module (`agent_overseas_report.config`) centralizes parsing,
validation, `.env` loading, and log redaction for known secrets.

## From-zero local startup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install runtime and development dependencies:

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Create local configuration:

   ```bash
   cp .env.example .env
   ```

   For a fully offline local run, keep `DEEPSEEK_API_KEY=` empty. To use the
   real provider, set `DEEPSEEK_API_KEY` in `.env` or the shell; never commit it.

4. Initialize the database and seed demo data:

   ```bash
   python scripts/init_sqlite_db.py
   ```

5. Start the API:

   ```bash
   uvicorn agent_overseas_report.main:app --reload
   ```

6. Open the API docs:

   ```text
   http://127.0.0.1:8000/docs
   ```

7. Optional smoke tests:

   ```bash
   pytest
   ```

## Database initialization

The default database is SQLite at `.data/overseas_report.sqlite3`. Initialize it
with:

```bash
python scripts/init_sqlite_db.py
```

To use a different SQLite file:

```bash
export OVERSEAS_REPORT_DATABASE_URL=sqlite:///./local_overseas_report.sqlite3
python scripts/init_sqlite_db.py
```

For a server deployment, set `OVERSEAS_REPORT_DATABASE_URL` to the managed
database URL supported by SQLAlchemy, then run the initialization script during
the release/setup phase. The FastAPI startup path also creates missing tables and
seeds demo rows for local convenience, but explicit initialization is recommended
before server deployment.

## Persistence tables

The SQLAlchemy metadata defines these tables with shared `id`, `created_at`,
`updated_at`, `status`, and JSON `metadata` columns:

- `enterprises`
- `products`
- `overseas_generation_projects`
- `overseas_plan_versions`
- `overseas_audit_logs`
- `report_exports`
- `knowledge_base_files`
- `knowledge_base_chunks`
- `web_research_sources`

## File upload rules

Knowledge-base uploads are rejected unless both checks pass:

- Extension is in `ALLOWED_UPLOAD_EXTENSIONS`.
- MIME type, when provided by the client, is in `ALLOWED_UPLOAD_MIME_TYPES`.

The upload stream is copied in chunks and rejected with HTTP 413 when it exceeds
`MAX_UPLOAD_BYTES`. Supported defaults are PDF, DOCX, XLSX, PPTX, Markdown, and
plain text.

## Logging

`LOG_LEVEL` and `LOG_FORMAT` configure standard Python logging. Known secret
values such as `DEEPSEEK_API_KEY` are redacted before log handlers emit records.
Application logs should include operational metadata such as provider, model,
prompt length, and status, but not prompts, uploaded file contents, API keys, or
full provider error payloads.
