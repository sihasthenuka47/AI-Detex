# AEGIS AI

**Intelligent Writing Analysis. Evidence Over Assumptions.**

A working private, single-user writing analysis workspace. All measurements come from submitted text. No AI-authorship probability is produced: no validated detector has been supplied. No documents are transmitted to AI or search providers.

## Run

Requires Python 3.12+ and Node.js 22+ (tested with Node 24).

```sh
./scripts/install.sh
./scripts/start.sh
```

The backend serves the built frontend on port 8000. It binds to loopback by default. Check `/api/health`; API documentation is at `/docs`. In development, run `.venv/bin/uvicorn backend.main:app --reload` and, in another terminal, `npm --prefix frontend run dev`. Vite proxies `/api` to the backend.

## Verify

```sh
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend run build
# Browser suite: install once, then run against an isolated test database:
cd frontend
npx playwright install chromium
npm run test:e2e
```

Use the existing checkout in cloud tasks; no worktree is necessary. If a sandbox blocks the supplied proxy or threaded test client, run the same commands through the platform's approved execution path. Never disable TLS checks.

## Working features

- Responsive dark/light dashboard, editor, drag/drop and file selection, selection-only analysis.
- Backend TXT, PDF and DOCX extraction; paragraph/table order for DOCX; PDF layout extraction; size, page and expanded ZIP limits. No OCR.
- Sentence/paragraph measurements, lexical diversity, repetition, function words, punctuation, rule-based sentence outliers, interactive passage findings, charts and accessible measurement table.
- Background jobs with real queued/analyzing/completed/failed states; cancellation discards results. Jobs are ephemeral, capped at 100, and cleaned on subsequent submissions after an hour. Cancellation suppresses results; it cannot interrupt an already running Python calculation.
- Explicit save/discard, persistent history, deletion, real PDF/JSON/TXT report exports.
- Opt-in private reference profiles; actual draft comparisons, revision notes, group identifiers and downloadable diff reports.
- Deterministic report guide grounded in saved results. **Not a conversational LLM.**
- Model adapter protocol, explicit abstention, offline evaluation utility and documented evaluation requirements.
- Privacy controls, lazy retention cleanup, request limits, origin checks, security response headers; no training pipeline or telemetry.

## Deliberately unavailable

Validated authorship classification, calibrated probabilities, POS tagging, grammar parsing, perplexity/entropy, OCR, external originality search and conversational AI require additional validated models or providers. The interface discloses these limitations. A language selector is not offered because only English analysis is supported; English is user-declared with script checks, not reliable language identification. Mixed and non-English Latin-script text cannot be reliably rejected.

## Architecture and boundaries

React 19 + TypeScript + Vite, Lucide icons and Recharts; FastAPI + Pydantic, pypdf, python-docx and ReportLab. SQLite schema is initialized in `backend/storage.py`. Vite replaces Next.js because this application does not require server rendering; SQLite replaces PostgreSQL for an entirely local single-user deployment. Model libraries are not installed without a model that needs them.

This is a functional foundation, **not a multi-tenant production service**. No accounts are enabled, and all local callers share one workspace. Do not expose it publicly without an authenticated HTTPS gateway. Production account isolation, robust distributed queues, PostgreSQL migrations, encryption/key management, malware scanning, resource-isolated file parsers and operational monitoring remain future work. See [security](docs/SECURITY.md) and [model evaluation](docs/MODEL_EVALUATION.md).

Configuration: `AEGIS_DATA_DIR` sets storage (default `.data/`), `PORT` sets the start script port, and `AEGIS_ALLOWED_ORIGINS` is a comma-separated exact origin allowlist for dev clients. No credentials are needed. Retention is configured through Settings; zero means manual deletion. No uploaded files are retained separately from extracted text. Deletion removes active database records and temporary results, but does not securely erase SQLite free pages or infrastructure backups.

## Container deployment

```sh
docker build -t aegis-ai .
docker run --rm -p 127.0.0.1:8000:8000 -v aegis-data:/data aegis-ai
```

Docker configuration is supplied but must be validated in your deployment environment. In managed environments preserve the session's proxy and CA trust during builds; never pass credentials as build arguments. Bind to loopback or place behind an authenticated reverse proxy with HTTPS, request-size limits and restricted hosts. The container runs as a non-root user. Persist `/data`; live processes and ephemeral jobs do not survive restart.
