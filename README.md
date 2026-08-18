# Infomir Learning Platform

[![CI](https://github.com/Lisovtcoff-hub/infomir-learning-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Lisovtcoff-hub/infomir-learning-platform/actions/workflows/ci.yml)

Infomir is a server-rendered learning platform for Russian school exams (VPR and OGE). It combines study materials, practice tasks, timed exam variants, student progress tracking, teacher groups, subscriptions, and a separate administration interface.

The repository is a portfolio project and a reference implementation. It is not presented as a hosted production service.

## What it demonstrates

- role-based workflows for students, teachers, and administrators;
- FastAPI APIs backed by SQLAlchemy 2 and Alembic migrations;
- an attempt lifecycle with ownership checks, time limits, scoring, and protected solutions;
- tariff-based access to content and exam variants;
- manual payment confirmation, subscription activation, teacher commission accounting, withdrawals, and refunds;
- HttpOnly cookie sessions with revocation through a session version;
- a public application and an isolated admin application selected by host name;
- regression tests for security-sensitive and billing-sensitive behavior.

## Technology

- Python 3.12
- FastAPI and Uvicorn
- SQLAlchemy 2 and Alembic
- PostgreSQL for deployment, SQLite for local development and tests
- Pydantic Settings
- PyJWT, Passlib, and Argon2
- HTML, CSS, and vanilla JavaScript
- Pytest and GitHub Actions
- Docker Compose

## Architecture

```text
Browser
  ├── public host ──> public FastAPI app ──> API routers ──> CRUD/services ──> database
  └── admin host  ──> admin FastAPI app  ──> admin operations ─────────────> database
```

The public and admin applications share the data model but use different hosts and session cookies. More detail is available in [docs/architecture.md](docs/architecture.md).

## Local development

Create a virtual environment and install the development dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
```

Copy the example configuration:

```bash
cp .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Replace `SECRET_KEY` in `.env` with a random value, then initialize the database:

```bash
alembic -c backend/alembic.ini upgrade head
python -m backend.app.db.seed
python -m backend.app.db.create_admin admin@example.com --name "Administrator"
```

Run the application:

```bash
uvicorn backend.app.main:app --reload
```

Useful addresses:

- public site: `http://localhost:8000/`
- admin interface: `http://admin.localhost:8000/`
- OpenAPI documentation: `http://localhost:8000/docs`
- health check: `http://localhost:8000/api/health`

The seed command is intended for a new development database. Do not run it over edited or real data.

## Tests

```bash
pytest -q
```

The regression suite currently covers 13 scenarios, including answer disclosure, access control, attempt ownership, tariff bypasses, exam time limits, session revocation, scoring, payment activation, teacher commission, withdrawals, refunds, and administrator credentials.

CI also applies all migrations to PostgreSQL before running the test suite.

## Docker

Create an environment file from the deployment example:

```bash
cp deploy/.env.example .env
```

Then start the application and PostgreSQL:

```bash
docker compose up --build
```

The container is bound to `127.0.0.1:8000` and is intended to run behind an HTTPS reverse proxy. See [docs/deployment.md](docs/deployment.md).

## Project layout

```text
backend/app/              FastAPI applications, API routes, models, schemas, and data access
backend/alembic/          database migrations
templates/                public, student, teacher, and admin pages
static/                   browser-side JavaScript, styles, and assets
tests/                    regression tests
deploy/                   deployment examples
docs/                     architecture, data model, security, and deployment notes
```

## Known limitations

- payments are confirmed manually; no payment-provider webhook adapter is included;
- the built-in rate limiter is process-local and should be replaced by Redis or an edge limiter for multi-worker deployments;
- email verification and password recovery require an external mail provider and are not implemented;
- the user interface and seeded learning content are in Russian.
