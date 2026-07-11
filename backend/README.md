# Backend — Academic Model Notes

## Assignment model

**Subjects belong to classes.** Each class offers subjects via `class_subjects`, managed through the Academic Hub and class-subject APIs.

**Teachers are assigned to class-subject pairs in one place.** Operational assignments live in `teacher_assignments`, linked to `class_subjects`.

**Class teacher stays on the class record.** Homeroom/form tutor remains `classes.teacher_id`; do not duplicate it on the teacher model.

**Report cards are admin-generated snapshots.** Scores use `draft | submitted`; `published` applies to generated report cards.

## Fresh database migration baseline

The development migration history was reset after the database was dropped. The repository now uses one initial Alembic revision:

```text
20260711_initial_schema
```

For a new, empty PostgreSQL database:

```bash
cd backend
alembic upgrade head
```

Then verify Alembic reports one head:

```bash
alembic heads
alembic current
```

Do not run the old academic backfill scripts against a fresh database. They were intended for upgrading legacy data, not for initializing an empty schema.

Before deploying this migration to any environment that still contains data, take a backup and create a forward migration instead of applying this reset baseline.
