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


## AI credit checkout configuration

`PAYSTACK_CALLBACK_URL` remains the subscription payment callback.
Set `PAYSTACK_AI_CREDIT_CALLBACK_URL` separately to the frontend public completion
page, for example `https://weavecloudspace.com/payments/ai-credits/complete` in
production. Use the corresponding frontend origin in staging or development.
AI checkout fails before creating a purchase when this setting is blank in staging
or production; it never falls back to the subscription callback.

Deploy the frontend completion route before enabling the backend callback setting.
The page requires no CBT credentials and does not verify or settle payments.
Paystack webhooks remain authoritative for settlement; the authenticated CBT
`POST /cbt/ai/admin/quota/purchases/{reference}/verify` endpoint remains available
for explicit fallback verification from CBT.

AI credits default to 2,000 kobo (20 naira) each. Existing environment overrides
still take precedence: set `CBT_AI_CREDIT_UNIT_PRICE_KOBO=2000` to apply this price
where an override already exists; `0` disables purchases. Existing purchases retain
their recorded amounts. No database migration is required. To roll back callback
changes, coordinate the backend release and environment configuration; retain the
public page for users returning from already-created checkouts.
