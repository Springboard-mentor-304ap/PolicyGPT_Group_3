# PolicyGPT

PolicyGPT is a government policy and public-scheme intelligence platform. It
brings government policies and welfare schemes into one searchable place and
helps citizens find out which schemes they may qualify for, instead of
navigating dozens of department websites.

The problem it solves: welfare schemes and policies are published across many
ministry and department portals in inconsistent formats. Citizens rarely find
the schemes they are eligible for. PolicyGPT centralises the content, adds
search and comparison tools, and gives each visitor a rule-based eligibility
check.

A note on eligibility: eligibility checks in PolicyGPT are advisory only —
applications are never blocked on the eligibility verdict, and final
eligibility decisions are made by the reviewing official.

## Features

- **Search & discovery** — global search over policies and schemes, with
  category / state / department filters.
- **Eligibility checker & Scheme Finder** — answer a few questions (or describe
  your need in plain language) and get matched to relevant schemes using
  per-scheme eligibility rules (age, income, gender, state, etc.).
- **Comparison** — compare schemes side by side before applying.
- **Applications** — citizens apply to schemes; government officials review the
  applications.
- **AI helpdesk** — LLM-backed (Groq) question answering over the scheme and
  policy knowledge base, with a per-user daily quota.
- **Content management** — officials upload policies and schemes (saved as
  pending approval); administrators approve, edit, or reject them.
- **Reports** — downloadable PDF/Excel/CSV reports with file retention and
  expiry.
- **Notifications** — in-app and e-mail notifications (deadlines, approvals,
  role requests, and more).
- **Feedback & FAQ** — citizen feedback queue for admins; a public FAQ section
  managed by administrators.
- **Audit logs** — administrative activity trail.

## User roles

| Role | Access |
| --- | --- |
| Guest | Browse and search public policies and schemes. |
| Citizen | Eligibility checks, comparisons, applications, feedback, profile. |
| Researcher | Read-only access to policies, schemes, analytics and reports. |
| Organization | Applies to schemes on behalf of an organization. |
| Government Official | Uploads policies/schemes, reviews applications, departmental analytics. |
| Administrator | Manages users, approvals, content, FAQs, feedback, audit logs. |
| Super Admin | Everything an administrator does, plus administrator access management. |

Roles are requested through the app (role upgrade requests) and granted by an
administrator or super admin.

## Tech stack

**Backend** — Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (with
pgvector for AI knowledge chunks), Alembic migrations, psycopg2, JWT auth
(python-jose + bcrypt), Groq LLM API, Brevo SMTP e-mail.

**Frontend** — Angular 22 (standalone components, signals), TypeScript 6,
RxJS. In development the Angular dev server proxies `/api` to the backend.

**Tooling** — pytest for the backend test suite, npm for the frontend,
uvicorn as the ASGI server.

## Prerequisites

- Python 3.12
- Node.js 20+ and npm 11+
- PostgreSQL 14+ with the [pgvector](https://github.com/pgvector/pgvector)
  extension available (used by the AI knowledge base)
- A Groq API key (AI helpdesk and knowledge ingestion)
- Brevo SMTP credentials (e-mail delivery; optional for local UI testing)

## Setup

### 1. Clone and configure the environment

```bash
git clone <repository-url>
cd PolicyGPT_Group_3
cp .env.example .env
```

`.env.example` is the authoritative list of every variable the code reads —
fill in real values there. The important ones:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string; also used by Alembic and the seed scripts. |
| `JWT_SECRET_KEY` | **Required** — the backend refuses to start without it. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes. |
| `FRONTEND_BASE_URL` | Base URL of the Angular app, used in password-reset e-mail links. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated explicit origins (never `*`). |
| `BREVO_*` | SMTP settings for e-mail (verification codes, password resets, notifications). |
| `GROQ_API_KEY` / `GROQ_MODEL` | AI helpdesk and knowledge ingestion. |
| `SEED_SUPER_ADMIN_*` / `SEED_ADMIN_*` | Credentials the seed scripts create admin accounts from (no password is hardcoded). |

### 2. Backend

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Database: create, migrate, seed

Create a PostgreSQL database and role, then install pgvector once (it is not a
trusted extension, so a superuser must run this):

```bash
psql -d <database> -c 'CREATE EXTENSION vector'
```

Run migrations first, then seeds (the seeds insert rows that only exist once
the schema does):

```bash
alembic upgrade head
python -m backend.app.seed_super_admin
python -m backend.app.seed_admins
python -m backend.seed_realistic_data   # optional demo data
```

The seed scripts read their credentials from `.env` and refuse to run when
`ENVIRONMENT=production`.

### 4. Run the backend

```bash
uvicorn backend.app.main:app --reload
```

The API listens on `http://localhost:8000`. Interactive API documentation is
served at `http://localhost:8000/docs`, and a database-aware health check at
`http://localhost:8000/health`.

### 5. Run the frontend

```bash
cd frontend
npm install
npm start
```

The dev server runs on `http://localhost:4200` and proxies `/api` requests to
`http://localhost:8000` (see `frontend/proxy.conf.json`), so no API URL
configuration is needed in development.

## Production notes

- **Environment variables** — copy `.env.example` to `.env` and fill in every
  value. `JWT_SECRET_KEY` is mandatory; `DATABASE_URL` is used by the app,
  Alembic, and the seed scripts.
- **Frontend build** — production bundles have no dev-server proxy, so set
  `apiUrl` in `frontend/src/environments/environment.prod.ts` to the backend
  origin before running `npm run build`.
- **One worker only** — the `Procfile` starts a single uvicorn worker:

  ```
  web: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
  ```

  The app hosts an in-process maintenance loop (deadline reminders, expired
  report cleanup, expired refresh-token cleanup). Every additional worker would
  run its own copy and duplicate that work — do not scale the worker count.

## Project structure

```
.
├── alembic/                  # Database migrations (alembic upgrade head)
│   └── versions/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, routers, CORS, maintenance loop
│   │   ├── db/               # Engine, session factory, Base
│   │   ├── models/           # SQLAlchemy models
│   │   ├── auth/             # JWT auth, password reset, e-mail verification
│   │   ├── admin/            # /admin/users management
│   │   ├── policies/         # Policy CRUD + approval workflow
│   │   ├── schemes/          # Scheme CRUD, approvals, eligibility rules
│   │   ├── eligibility/      # Rule-based eligibility checks
│   │   ├── applications/     # Citizen applications + official review
│   │   ├── search/           # Global search
│   │   ├── comparison/       # Scheme comparison
│   │   ├── finder/           # Natural-language scheme matching
│   │   ├── helpdesk/         # AI helpdesk (Groq)
│   │   ├── ai/               # Knowledge ingestion + sync worker
│   │   ├── analytics/        # Role-scoped analytics
│   │   ├── reports/          # PDF/Excel/CSV report generation
│   │   ├── notifications/    # In-app + e-mail notifications, reminders
│   │   ├── feedback/         # Feedback queue
│   │   ├── faq/              # FAQ management
│   │   ├── audit/            # Audit logs
│   │   ├── role_requests/    # Role upgrade requests
│   │   ├── profile/          # Citizen / official profiles
│   │   └── departments/      # Department directory
│   ├── seed_super_admin.py   # Seeds the first super admin
│   ├── seed_admins.py        # Seeds administrator accounts
│   └── seed_realistic_data.py# Optional demo data
├── frontend/
│   └── src/app/
│       ├── core/             # Guards, interceptors, services, models
│       ├── pages/            # Feature pages (dashboard, policies, schemes,
│       │                     #   search, eligibility, finder, helpdesk, admin, …)
│       ├── layouts/          # Auth / dashboard layouts
│       └── shared/           # Reusable UI components
├── tests/                    # pytest suite (api/, ai/, eligibility/, finder/)
├── .env.example              # Full list of backend environment variables
└── Procfile                  # Single-worker uvicorn start command
```

## API overview

All endpoints live under the `/api` prefix and are documented interactively at
`/docs` (Swagger UI). The main route groups:

| Prefix | Purpose |
| --- | --- |
| `/api/auth` | Register, login, JWT refresh, e-mail verification, password reset |
| `/api/admin/users` | Administrative user management |
| `/api/role-requests` | Role upgrade request workflow |
| `/api/profile` | Citizen and government-official profiles |
| `/api/policies`, `/api/schemes` | Content CRUD, approvals, eligibility rules |
| `/api/eligibility` | Eligibility checks |
| `/api/applications` | Apply to schemes; official review |
| `/api/search`, `/api/comparison`, `/api/finder` | Discovery tools |
| `/api/helpdesk` | AI helpdesk (quota-metered) |
| `/api/analytics`, `/api/reports` | Analytics and downloadable reports |
| `/api/notifications`, `/api/feedback`, `/api/faqs`, `/api/audit-logs` | Platform features |
| `/health` | Liveness probe that also verifies database connectivity |

Authentication uses Bearer JWT access tokens with a rotating refresh token
(`POST /api/auth/refresh`); the Angular client stores them and attaches them
through an HTTP interceptor.

## Testing

The backend test suite runs with pytest (configured by `pytest.ini`):

```bash
source .venv/bin/activate
pytest                        # entire suite
pytest tests/api              # API tests only
pytest tests/api/test_ops_bugs.py   # a single file
```

The suite covers auth and verification security, refresh-token rotation,
admin user management, policies/schemes and approval workflows, eligibility
rules, applications, reports retention, search, notifications, and AI quota
enforcement. Tests use SQLite in-memory databases, so no PostgreSQL
connection is required to run them.
