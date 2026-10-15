# PolicyGPT_Group_3

Eligibility checks in PolicyGPT are advisory only: applications are never
blocked on the eligibility verdict, and final eligibility decisions are made
by the reviewing official.

## Deploying

### 1. Environment variables

Copy `.env.example` to `.env` and fill in every value it lists — it is the
authoritative list of variables the code reads. The app refuses to start
without `JWT_SECRET_KEY`; `DATABASE_URL` is needed by the app, Alembic and the
seed scripts, and the Brevo SMTP / Groq blocks power e-mail and the AI helpdesk.

The frontend bakes its API origin in at build time: set `apiUrl` in
`frontend/src/environments/environment.prod.ts` before running
`ng build` (a production bundle has no dev-server proxy).

### 2. Database: migrate, then seed

Run migrations first and seeds second — the seeds insert rows that only exist
once the schema does:

```bash
alembic upgrade head
python -m backend.app.seed_super_admin
python -m backend.app.seed_admins
python -m backend.seed_realistic_data   # optional demo data
```

On a brand-new database the role in `DATABASE_URL` also needs the pgvector
extension (used by `knowledge_chunks`). Alembic runs
`CREATE EXTENSION IF NOT EXISTS vector` before migrating, but pgvector is not
a trusted extension on most builds, so a superuser has to install it once:

```bash
psql -d <database> -c 'CREATE EXTENSION vector'
```

### 3. Start command — one worker only

The `Procfile` starts a single worker:

```
web: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

**Run exactly one worker.** The app hosts an in-process maintenance loop
(deadline reminders, expired report files, expired refresh-token cleanup) that
starts with the process; every additional worker would run its own copy and
duplicate that work.
