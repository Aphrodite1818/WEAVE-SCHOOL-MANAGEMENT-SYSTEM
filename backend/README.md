# Backend — Academic Model Notes

## Phase 1: Assignment consolidation

**Subjects belong to classes.** Each class offers subjects via `class_subjects` (managed on the Classes screen and `/classes/:id/subjects`).

**Teachers are assigned to class-subject pairs in one place (Academic Hub).** Operational assignments live in `teacher_assignments`, linked to `class_subjects`. Use `/tenant-admin/academic/teacher-assignments`.

**Class teacher stays on the class record.** Homeroom/form tutor is `classes.teacher_id` only — do not duplicate this on the teacher model.

**Report cards are admin-generated snapshots, never live-computed.** Scores use `draft | submitted` only; `published` applies to `report_cards` exclusively. Generate via `/tenant-admin/academic/report-cards/generate`.

### Legacy tables (compatibility only)

- `teacher_subjects` — catalog qualification only; no new UI writes
- `class_subject_teachers` — deprecated; kept only for backward-compatible reads and result backfill during migration

### Migration

1. Run Alembic: `alembic upgrade head`
2. Backfill: `python -m scripts.backfill_academic_assignments [--dry-run]`
3. Review `migration_report.json` and `unmatched_teacher_subjects.csv` before production
