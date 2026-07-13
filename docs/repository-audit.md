# Repository Audit

Date: 2026-07-13

## Summary

The repository is a FastAPI and React/Vite monorepo. The main product code is organized under `backend/` and `frontend/`, but several professional-development standards were missing or stale: the root README described an old WhatsApp review branch, `.github/` was absent, frontend documentation was still Vite template text, and tracked generated/runtime files were present.

## Root

- `README.md` was outdated and did not describe the current school management SaaS.
- `.gitignore` already protected environment files, logs, caches, frontend build output, and virtual environments.
- `.github/` was missing.
- `CONTRIBUTING.md`, `SECURITY.md`, and `.editorconfig` were missing.
- `design-qa.md` appears to be durable design QA documentation and was left in place.

## Backend

- Backend structure follows a layered FastAPI pattern: routers, services, repositories, models, schemas, core utilities, and config.
- Alembic has a single tracked migration revision and was treated as protected.
- `requirements.txt`, `pyproject.toml`, and `uv.lock` all exist. Docker currently installs from `requirements.txt`, so compatibility was preserved.
- `backend/scripts/backfill_academic_assignments.py` generates `migration_report.json` and `unmatched_teacher_subjects.csv`; those generated outputs were tracked and are safe to remove.
- `backend/logs/uvicorn_repro.pid` was tracked runtime state and is safe to remove.
- `backend/uv` was an empty tracked file with no repository references and is safe to remove.
- Duplicate-looking packages exist under `backend/app/core/rate_limit` and `backend/app/core/rate_limits`; these were not removed because import usage and behavior need a focused compatibility review.
- `backend/app/modules/bulk_imports/templatest.py` looks suspicious by name, but it was not removed without import and behavior proof.

## Frontend

- Frontend is a React/Vite application with role-based pages, feature folders, shared components, services, and routes.
- `frontend/README.md` contained default Vite template documentation and needed replacement.
- `frontend/package.json` had only basic scripts and no standard `check` command.
- Duplicate-looking `src/features/*` and `src/modules/*` folders exist for academics, AI, announcements, and finance. These were not removed because usage needs a careful import graph check and visual regression risk is not zero.
- PWA and mobile files were left untouched.

## Tests

- Backend tests are split across unit, integration, regression, and e2e directories.
- Frontend has no dedicated test framework configured yet; the standardized test script currently records that gap instead of pretending coverage exists.

## Docker and Deployment

- `docker-compose.yml` runs Redis and the backend.
- Backend Dockerfile installs from `requirements.txt`; this is why `requirements.txt` was preserved.
- Railway/Vercel environment configuration was not changed.

## Protected Files

- No `.env` or `.env.example` file should be modified by this cleanup.
- No Alembic migration file should be modified by this cleanup.
- No database reset, migration rewrite, or deployment secret change should be performed.

## Postponed Cleanup

- Dependency pruning: several backend dependencies look development-only, but safe removal requires lockfile regeneration and full validation.
- Duplicate frontend module/feature cleanup: needs import graph proof and UI regression testing.
- Backend router refactor: current order includes deliberate overlapping student access-code behavior, so no broad router rewrite was attempted.
- Full backend formatting: Ruff reports more than 170 files would be reformatted, so this should be handled as a separate mechanical PR to keep review noise controlled.
- Backend type checking: Pyright now runs in the project environment, but reports 136 existing type errors. CI records this as non-blocking until the codebase has a dedicated typing hardening pass.
- Alembic autogenerate check: `alembic check` reports model/migration drift, mainly schema-qualified foreign keys/enums and generated constraint differences. This was reported rather than repaired because migration history is protected.
- Backend integration tests: local integration tests currently fail with authentication/session validation errors and asyncpg event-loop teardown noise. Unit tests pass, so the failures should be investigated separately from repository hygiene.
