# Background Worker Deployment

Weave deploys two ARQ workers that share PostgreSQL and Redis while consuming separate queues.

## General worker

Purpose:

- poll and deliver email-outbox rows
- run attendance location-evidence retention
- reconcile expired subscriptions and scheduled plan changes

Railway start command:

```bash
arq app.core.queue.general_worker.WorkerSettings
```

Recommended initial configuration:

- replicas: `1`
- concurrency: `max_jobs = 3`
- queue: `weave:queue:general`
- email poll interval: `10 seconds`
- database pool: `DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=1`
- required environment: database, Redis, email-provider, and subscription variables

## Heavy worker

Purpose:

- process confirmed student bulk-import jobs
- run academic-session student progression
- preserve the existing row-level progress, retry, and failure workflows

Railway start command:

```bash
arq app.core.queue.heavy_worker.WorkerSettings
```

Recommended initial configuration:

- replicas: `1`
- concurrency: `max_jobs = 1`
- queue: `weave:queue:heavy`
- timeout: `3600 seconds`
- database pool: `DB_POOL_SIZE=1`, `DB_MAX_OVERFLOW=1`
- required environment: the same database, Redis, storage, and application configuration used by the API

Neither worker needs a public domain or HTTP port.

## API pool configuration

Recommended initial API values:

```env
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=3
DB_POOL_TIMEOUT_SECONDS=10
```

The combined theoretical maximum is approximately 13 application-owned PostgreSQL connections:

- API: 8
- general worker: 3
- heavy worker: 2

## Deployment order

1. Do not deploy while a bulk import or progression run is actively processing.
2. Deploy the code containing the two worker entrypoints.
3. Create or update the Railway general-worker service with the general-worker command.
4. Create or update the Railway heavy-worker service with the heavy-worker command.
5. Apply the service-specific database-pool variables.
6. Confirm Redis contains both health keys:
   - `weave:queue:general:health`
   - `weave:queue:heavy:health`
7. Trigger a test email-outbox delivery.
8. Run a small student bulk import.
9. Verify subscription reconciliation executes from the general worker.
10. Remove the obsolete worker services only after both new services are healthy.

## Expected behaviour

General work remains concurrent but bounded. Heavy imports and progression runs are serialized so they cannot compete with each other for database capacity. Email delivery remains independent of heavy jobs because it uses a separate queue and worker process.
