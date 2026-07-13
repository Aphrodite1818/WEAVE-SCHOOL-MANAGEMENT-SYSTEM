# Contributing

This repository should stay predictable, reviewable, and production-oriented. Prefer small changes with clear test evidence over broad speculative cleanup.

## Branches

Use short-lived branches:

```text
feat/<short-description>
fix/<short-description>
refactor/<short-description>
test/<short-description>
docs/<short-description>
chore/<short-description>
ci/<short-description>
```

Do not push directly to `master`.

## Commits

Use Conventional Commit-style messages:

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

Examples:

```text
chore(repo): standardize project tooling
docs(readme): document local development workflow
ci(backend): add lint and test validation
```

## Pull Requests

Every PR should include:

- Summary of the change.
- Type of change.
- Test evidence.
- Migration impact.
- Environment-variable impact.
- Deployment impact.
- Screenshots for UI changes.
- Rollback considerations.

For repository hygiene work, explicitly state:

```text
Environment-variable impact: none
Database migration impact: none
Production behavior impact: none intended
```

## Testing Expectations

Backend changes should run the smallest meaningful test set first, then broader tests when shared behavior is touched:

```bash
cd backend
uv run pytest tests/unit
uv run pytest tests/integration
```

Frontend changes should run:

```bash
cd frontend
npm run lint
npm run test
npm run build
```

## Migration Rules

- Do not delete, rename, rewrite, squash, or rebase Alembic migrations.
- Do not change `down_revision` on existing migrations.
- Do not stamp or reset a real database as part of application work.
- Create forward migrations for schema changes.
- Run read-only Alembic checks before merging migration-related work.

## Secrets and Generated Files

- Never commit `.env` files or real environment values.
- Never document secrets in README files, PRs, tests, or screenshots.
- Do not commit local databases, logs, coverage output, build output, caches, or generated reports.
- Keep deployment secrets in Railway, Vercel, or the approved secret manager.
