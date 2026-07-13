# Weave School Management SaaS

Weave is a multi-tenant school management SaaS for running core school operations across administrators, teachers, parents, students, and platform superadmins. The repository is a monorepo with a FastAPI backend and a React/Vite frontend.

## Supported Roles

- **Superadmin**: manages platform-wide controls, tenant oversight, analytics, and operational monitoring.
- **Tenant admin**: manages one school tenant, including users, students, classes, subjects, announcements, billing, onboarding, and academic workflows.
- **Teacher**: manages assigned classes, subjects, attendance, assignments, results, and student academic views.
- **Parent**: views linked children, reports, results, announcements, and student progress.
- **Student**: accesses assigned subjects, reports, profile flows, and student-specific academic information.

## Architecture

- `backend/` contains the FastAPI application, SQLAlchemy models/repositories, Pydantic schemas, services, routers, Alembic migrations, Redis cache utilities, and ARQ worker setup.
- `frontend/` contains the React application built with Vite, React Router, feature modules, shared UI, and service clients.
- PostgreSQL is the system of record.
- Redis is used for caching, rate limiting, and ARQ-backed background work.
- Alembic owns schema migrations.
- Railway hosts the backend API, PostgreSQL, Redis, and the ARQ worker.
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
- Ruff and Pyright for local/CI validation

## Frontend Stack

- React
- Vite
- React Router
- Tailwind CSS
- Lucide React
- Recharts
- ESLint

## Local Development

Environment values are managed separately and must not be committed. Do not put secrets in documentation, source files, tests, or CI configuration.

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

### Start the ARQ Worker

```bash
cd backend
uv run arq app.core.queue.worker_settings.WorkerSettings
```

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
uv run pytest tests/unit
uv run pytest tests/integration
uv run alembic heads
uv run alembic history
uv run alembic check
```

### Frontend

```bash
cd frontend
npm run lint
npm run test
npm run build
npm run check
```

## PostgreSQL and Alembic

Alembic migrations live in `backend/alembic/versions/` and must be treated as protected history. Do not delete, rename, rewrite, squash, or rebase existing migration files. Create forward migrations for schema changes.

For a new local database:

```bash
cd backend
uv run alembic upgrade head
```

## Redis and ARQ

Redis supports cache, rate-limit, and queue behavior. The ARQ worker uses the backend import path and should be deployed as a separate Railway worker process from the API.

## Deployment

- Backend API: Railway
- PostgreSQL: Railway
- Redis: Railway
- ARQ worker: Railway
- Frontend: Vercel

No Railway or Vercel secrets are stored in this repository. Environment-variable impact for repository hygiene changes should normally be `none`.

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
