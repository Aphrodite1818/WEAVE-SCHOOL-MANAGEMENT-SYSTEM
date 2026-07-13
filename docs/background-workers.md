# Background Worker Deployment

Weave uses two dedicated ARQ workers that share the same PostgreSQL database and Redis instance but consume different queues.

## Bulk-import worker

Purpose:

- process confirmed student, teacher, and parent import jobs
- create database records
- write row-level progress and errors
- enqueue invite-email rows in the email outbox

Railway start command:

```bash
arq app.core.queue.bulk_import_worker.WorkerSettings
```

Recommended pilot configuration:

- replicas: `1`
- concurrency: `max_jobs = 2`
- queue: `weave:queue:bulk-import`
- required environment: the same backend database and Redis configuration

## Email-outbox worker

Purpose:

- poll the `email_outbox` table
- claim pending rows using the existing database locking rules
- send emails in bounded batches
- mark messages sent, failed, or pending for retry

Railway start command:

```bash
arq app.core.queue.email_worker.WorkerSettings
```

Recommended pilot configuration:

- replicas: `1`
- concurrency: `max_jobs = 3`
- batch size: `20`
- poll interval: `10 seconds`
- queue: `weave:queue:email`
- required environment: database, Redis, and email-provider variables

Neither worker needs a public domain or HTTP port.

## Deployment order

1. Do not deploy while an import is actively processing.
2. Deploy the code containing both queue-specific workers.
3. Change the existing Railway worker command to the bulk-import worker command.
4. Create a second Railway service using the email-worker command.
5. Give both services the same `DATABASE_URL` and `REDIS_URL` used by the API.
6. Give the email worker the email-provider variables used by the API.
7. Confirm both worker logs show their distinct queue names.
8. Run a small parent or teacher import and verify that account creation and email delivery progress independently.

## Expected behaviour

During an import, the bulk-import worker creates records and commits outbox rows. The email worker polls independently, claims up to 20 eligible rows per batch, and continues draining the email queue without consuming bulk-import worker slots.

New bulk-import outbox rows include `metadata_json.import_job_id`, allowing the frontend progress panel to report only emails belonging to the selected import job.
