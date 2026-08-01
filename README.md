# Weave School Management SaaS

Weave is a multi-tenant school management SaaS for running core school operations across administrators, teachers, parents, students, and platform superadmins. The repository is a monorepo with a FastAPI backend and a React/Vite frontend.

## Supported Roles

- **Superadmin**: manages platform-wide controls, tenant oversight, analytics, and operational monitoring.
- **Tenant admin**: manages one school tenant, including users, students, classes, subjects, announcements, billing, onboarding, and academic workflows.
- **Teacher**: manages assigned classes, subjects, attendance, assignments, results, and student academic views.
- **Parent**: views linked children, reports, results, announcements, and student progress.
- **Student**: accesses assigned subjects, reports, profile flows, and student-specific academic information.

## Architecture

- `backend/` contains the FastAPI application, SQLAlchemy models/repositories, Pydantic schemas, services, routers, Alembic migrations, Redis cache utilities, and dedicated ARQ workers.
- `frontend/` contains the React application built with Vite, React Router, feature modules, shared UI, and service clients.
- PostgreSQL is the system of record.
- Redis supports caching, rate limiting, background queues, and worker health keys.
- Alembic owns schema migrations.
- Railway hosts the backend API, PostgreSQL, Redis, and dedicated worker services.
- Vercel hosts the frontend.

## Repository Structure

```text
/
├── backend/              FastAPI API, Alembic, tests, backend scripts
├── frontend/             React/Vite frontend
├── docs/                 Durable engineering documentation
├── .github/              Pull request template and CI workflows
├── .editorconfig         Shared editor defaults
├── .gitignore            Repository-wide ignore rules
├── CONTRIBUTING.md       Development and review workflow
├── SECURITY.md           Private vulnerability reporting process
└── docker-compose.yml    Local Redis/API orchestration
```

## Backend Stack

- FastAPI
- SQLAlchemy async ORM
- Pydantic and Pydantic Settings
- Alembic
- PostgreSQL via `asyncpg`
- Redis
- ARQ
- Pytest
- Ruff and Pyright

## Frontend Stack

- React
- Vite
- React Router
- Tailwind CSS
- Lucide React
- Recharts
- ESLint
- Node test runner

## Local Development

Environment values are managed separately and must not be committed. Do not put secrets, credentials, generated login files, or real user data in documentation, source files, tests, or CI configuration.

### Backend Setup

```bash
cd backend
uv sync
```

If a deployment target still uses `requirements.txt`, treat it as compatibility output rather than an independent source of truth.

### Frontend Setup

```bash
cd frontend
npm ci
```

### Start Redis and API with Docker Compose

```bash
docker compose up redis backend
```

### Start the API Locally

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Start Dedicated ARQ Workers

Each worker consumes a different queue. Running only the legacy worker alias starts email processing and does not process the other queues.

```bash
cd backend

# Email outbox
uv run arq app.core.queue.email_worker.WorkerSettings

# Confirmed student bulk imports
uv run arq app.core.queue.bulk_import_worker.WorkerSettings

# Academic-session progression
uv run arq app.core.queue.progression_worker.WorkerSettings

# Attendance retention and scheduled attendance work
uv run arq app.core.queue.attendance_worker.WorkerSettings
```

In production, deploy these as four separate Railway worker services with restart policies and health monitoring. Configure conservative database pool values independently for the API and every worker.

### Start the Frontend

```bash
cd frontend
npm run dev
```

## Validation Commands

### Backend

```bash
cd backend
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
uv run --with pyright pyright
uv run alembic heads
uv run alembic history
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/unit
uv run pytest tests/integration
uv run python -c "from app.main import app; print(app.title)"
```

### Frontend

```bash
cd frontend
npm run lint
npm run test
npm run build
npm run check
```

## Health Checks

- `/health/live` proves that the API process is running.
- `/health` and `/health/ready` verify PostgreSQL and Redis and return HTTP 503 when either dependency is unavailable.

Use `/health/ready` for deployment readiness and `/health/live` for process liveness.

## PostgreSQL and Alembic

Alembic migrations live in `backend/alembic/versions/` and must be treated as protected history. Do not delete, rename, rewrite, squash, or rebase existing migration files. Create forward migrations for schema changes.

For a new database:

```bash
cd backend
uv run alembic upgrade head
```

Before production rollout, run migrations against a current production-like database clone, verify critical workflows, and confirm rollback procedures.

## Production Configuration

Production-like environments fail startup when required infrastructure or security settings are missing. At minimum, configure:

- strong independent `SECRET_KEY` and `BULK_IMPORT_RESULT_ENCRYPTION_KEY` values;
- PostgreSQL and Redis URLs;
- explicit HTTPS CORS origins and frontend URL;
- trusted proxy headers and the correct trusted proxy hop count;
- an HTTPS email provider endpoint or complete SMTP credentials;
- durable R2 media storage in production;
- conservative database pool sizes for each deployed process.

Student setup codes created by bulk import are encrypted at rest and available for access-slip generation only for the configured retention window.

## Deployment

- Backend API: Railway
- PostgreSQL: Railway
- Redis: Railway
- Email worker: Railway
- Bulk-import worker: Railway
- Session-progression worker: Railway
- Attendance worker: Railway
- Frontend: Vercel

### Release Checklist

1. Remove or rotate any credentials that have appeared in repository history.
2. Configure all production environment variables and verify startup validation.
3. Run backend and frontend CI, including migration upgrades and integration tests.
4. Deploy migrations before application processes that require the new schema.
5. Deploy the API and all four workers.
6. Verify `/health/ready` and each ARQ worker health key.
7. Run authentication, invitation, student creation, bulk-import, attendance, academic-session, report-card, and notification smoke tests in staging.
8. Promote staging only after test evidence and rollback steps are recorded.

## Branching and Pull Requests

Use short-lived branches and Conventional Commit-style messages:

```text
feat:
fix:
refactor:
test:
docs:
chore:
ci:
perf:
```

Open pull requests with test evidence, migration impact, environment-variable impact, deployment impact, and rollback considerations. Do not push directly to `master`.
