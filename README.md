# Infomir Learning Platform

[![CI](https://github.com/lisovcoff/infomir-learning-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/lisovcoff/infomir-learning-platform/actions/workflows/ci.yml)

Server-rendered learning platform for exam-preparation workflows. The project separates public and administrative applications, supports timed attempts and subscriptions, tracks student progress, manages teacher groups, and includes billing-related back-office flows.

## Highlights

- student, teacher, and administrator workflows;
- timed attempts with ownership checks, scoring, and protected solutions;
- tariff-based access to learning content and exam variants;
- progress tracking, teacher groups, and subscription management;
- manual payment confirmation, commission, withdrawals, and refunds;
- separate public and admin applications by host name;
- regression tests for security-sensitive and billing-sensitive behavior.

## Stack

`Python 3.12` · `FastAPI` · `SQLAlchemy 2` · `Alembic` · `PostgreSQL` · `SQLite` · `PyJWT` · `Argon2` · `Pytest` · `Docker Compose`

## Architecture

```text
Browser
  |-- public host --> public FastAPI app --> API / services --> database
  `-- admin host  --> admin FastAPI app  --> admin services -> database
```

The public and admin applications share the same data model while keeping separate host-based entry points and session cookies.

Additional notes: [architecture](docs/architecture.md), [data model](docs/data-model.md), [deployment](docs/deployment.md), [security](SECURITY.md).

## Run locally

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
cp .env.example .env
alembic -c backend/alembic.ini upgrade head
python -m backend.app.db.seed
python -m backend.app.db.create_admin admin@example.com --name "Administrator"
uvicorn backend.app.main:app --reload
```

PowerShell can create configuration with `Copy-Item .env.example .env`.

Useful addresses:

- public site: `http://localhost:8000/`
- admin interface: `http://admin.localhost:8000/`
- OpenAPI: `http://localhost:8000/docs`
- health check: `http://localhost:8000/api/health`

## Tests

```bash
pytest -q
```

The regression suite covers access control, answer disclosure, attempt ownership, tariff bypasses, exam time limits, session revocation, payment activation, teacher commission, withdrawals, refunds, and administrator credentials.

For container-based development:

```bash
cp deploy/.env.example .env
docker compose up --build
```

## Repository layout

```text
backend/app/       FastAPI applications, routes, models, schemas, and data access
backend/alembic/   database migrations
templates/         public, student, teacher, and admin pages
static/            browser-side JavaScript, styles, and assets
tests/             regression tests
deploy/            deployment examples
docs/              architecture, data model, security, and deployment notes
```

## Notes

- This public repository excludes hosted infrastructure and third-party provider credentials.
- Payments are confirmed manually; provider webhook integration is out of scope.
- The built-in rate limiter is process-local and should be replaced for multi-worker deployment.
- The interface and seeded educational content are in Russian.
