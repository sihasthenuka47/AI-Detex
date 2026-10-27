# Security and privacy

Threat model: one trusted person using a private local workspace. There is no account identity, tenant separation or authentication. Access to the API is access to all stored documents. Do not expose this deployment to other users.

Application controls include Pydantic text limits, 10 MB file limits, 30 MB expanded DOCX limits, 200 PDF pages, format checks, parameterized SQL, React escaping, escaped PDF content, restricted origin checks, no permissive CORS, per-process request throttling (120 requests/minute/client), job capacity limits and response security headers. No API keys or remote providers are required. No document telemetry or training occurs.

Documents are parsed in memory. Local extracted text and result records are stored in SQLite. Set storage permissions and disk encryption at the host level. Retention cleanup occurs on database access, not on a scheduled timer. Unsaved jobs are deleted on server restart and lazily expire on new submissions; they have no durable recovery. Keep backups subject to the same retention/deletion policy.

Untrusted file parsing remains a resource-exhaustion risk: production should isolate PDF/DOCX workers with CPU/memory/time limits. Deploy a reverse proxy that enforces request limits including chunked bodies before the ASGI server. In-process rate limits do not work across replicas. Profiles and saved documents are not encrypted by the application. Deletion is logical, not secure media erasure. A public deployment needs proper account authentication and authorization, audited migrations, a distributed job queue, host restrictions, monitoring and tested backups.
