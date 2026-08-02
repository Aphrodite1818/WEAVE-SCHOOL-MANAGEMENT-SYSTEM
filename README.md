# Weave School Management SaaS

Weave is a multi-tenant school management SaaS for running core school operations across administrators, teachers, parents, students, and platform superadmins. The repository is a monorepo with a FastAPI backend and a React/Vite frontend.

## Supported Roles

- **Superadmin**: manages platform-wide controls, tenant oversight, analytics, and operational monitoring.
- **Tenant admin**: manages one school tenant, including users, students, classes, subjects, announcements, billing, onboarding, and academic workflows.
- **Teacher**: manages assigned classes, subjects, attendance, assignments, results, and student academic views.
- **Parent**: views linked children, reports, results, announcements, and student progress.
- **Student**: accesses assigned subjects, reports, profile flows, and student-specific academic information.

## Architecture

- `backend/` contains the FastAPI application, SQLAlchemy models/repositories, Pydantic schemas, services, routers, Alembic migrations, Redis cache utilities, and ARQ workers.
- `frontend/` contains the React application built with Vite, React Router, feature modules, shared UI, and service clients.
- PostgreSQL is the system of record.
- Redis supports caching, rate limiting, background queues, and worker health keys.
- Alembic owns schema migrations.
- Railway hosts the backend API, PostgreSQL, Redis, and worker services.
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

### Start ARQ Workers

The general worker handles lightweight and recurring work. The heavy worker serializes imports and progression so they cannot compete for database capacity.

```bash
cd backend

# Email delivery, attendance retention, and subscription reconciliation
uv run arq app.core.queue.general_worker.WorkerSettings

# Confirmed student bulk imports and academic-session progression
uv run arq app.core.queue.heavy_worker.WorkerSettings
```

Recommended initial database pool values:

```text
API:            DB_POOL_SIZE=5  DB_MAX_OVERFLOW=3
General worker: DB_POOL_SIZE=2  DB_MAX_OVERFLOW=1
Heavy worker:   DB_POOL_SIZE=1  DB_MAX_OVERFLOW=1
```

See `docs/background-workers.md` for the deployment sequence and health keys.

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
uv run --with pyright pyright app
uv run alembic heads
uv run alembic history
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/unit
uv run pytest tests/integration
uv run python -c "from app.main import app; print(app.title)"
uv run python -c "from app.core.queue.general_worker import WorkerSettings; print(WorkerSettings.queue_name)"
uv run python -c "from app.core.queue.heavy_worker import WorkerSettings; print(WorkerSettings.queue_name)"
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
- `weave:queue:general:health` proves the general worker is alive.
- `weave:queue:heavy:health` proves the heavy worker is alive.

Use `/health/ready` for deployment readiness and `/health/live` for process liveness.

## PostgreSQL and Alembic

Alembic migrations live in `backend/alembic/versions/` and must be treated as protected history after the first production database is created. Create forward migrations for later schema changes.

For a new database:

```bash
cd backend
uv run alembic upgrade head
```

`20260731_clean_baseline` is a frozen, explicit description of the initial production schema. After it has been used by staging or production, never edit or regenerate it. Every later model or schema change must be represented by a new forward Alembic revision whose `down_revision` points to the current head.

Before production rollout, run migrations against a current production-like database, verify critical workflows, and confirm backup and restore procedures.

## Production Configuration

Production-like environments fail startup when required infrastructure or security settings are missing. At minimum, configure:

- strong independent `SECRET_KEY` and `BULK_IMPORT_RESULT_ENCRYPTION_KEY` values;
- PostgreSQL and Redis URLs;
- explicit HTTPS CORS origins and frontend URL;
- trusted proxy headers and the correct trusted proxy hop count;
- an HTTPS email provider endpoint or complete SMTP credentials;
- durable R2 media storage in production;
- conservative database pool sizes for each deployed process.

Production logs are emitted as single-line JSON to standard output for Railway collection. Development keeps readable console output and rotating `backend/logs/app.log` files.

Refresh and logout requests use the HttpOnly refresh cookie and require both an approved browser origin and the `X-Weave-CSRF: 1` request header.

Student setup codes created by bulk import are encrypted at rest and available for access-slip generation only for the configured retention window.

## Deployment

- Backend API: Railway
- PostgreSQL: Railway
- Redis: Railway
- General worker: Railway
- Heavy worker: Railway
- Frontend: Vercel

### Release Checklist

1. Remove or rotate any credentials that have appeared in repository history.
2. Configure all production environment variables and verify startup validation.
3. Run backend and frontend CI, including fresh migration upgrades and integration tests.
4. Deploy migrations before application processes that require the schema.
5. Deploy the API, general worker, and heavy worker.
6. Verify `/health/ready` and both ARQ worker health keys.
7. Confirm the subscription reconciliation cron executes successfully.
8. Run authentication, invitation, student creation, bulk-import, academic-session, report-card, and notification smoke tests in staging.
9. Verify Railway receives structured API and worker logs with service and release context.
10. Promote staging only after test evidence and rollback steps are recorded.

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
