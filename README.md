# Infomir Learning Platform

[![CI](https://github.com/Lisovtcoff-hub/infomir-learning-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Lisovtcoff-hub/infomir-learning-platform/actions/workflows/ci.yml)

A server-rendered learning platform for Russian school exams, including VPR and OGE preparation. It combines study materials, practice tasks, timed exam variants, student progress tracking, teacher groups, subscriptions, and a separate administration interface.

> This repository is a portfolio project and reference implementation. It is not presented as a hosted production service.

## What the project does

- supports student, teacher, and administrator workflows;
- manages timed attempts with ownership checks, scoring, and protected solutions;
- applies tariff-based access to learning content and exam variants;
- tracks student progress and teacher groups;
- supports manual payment confirmation, subscriptions, teacher commission, withdrawals, and refunds;
- uses revocable HttpOnly cookie sessions;
- separates public and administrative applications by host name;
- includes regression tests for security-sensitive and billing-sensitive behavior.

## Architecture

```text
Browser
  |-- public host --> public FastAPI app --> API / services --> database
  `-- admin host  --> admin FastAPI app  --> admin services -> database
```

The public and admin applications share the data model but use separate hosts and session cookies. See [docs/architecture.md](docs/architecture.md).

## Technology stack

- Python 3.12
- FastAPI and Uvicorn
- SQLAlchemy 2 and Alembic
- PostgreSQL; SQLite for local development and tests
- Pydantic Settings
- PyJWT, Passlib, and Argon2
- HTML, CSS, and vanilla JavaScript
- Pytest and GitHub Actions
- Docker Compose

## Quick start

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

## Development and tests

```bash
pytest -q
```

The regression suite covers answer disclosure, access control, attempt ownership, tariff bypasses, exam time limits, session revocation, scoring, payment activation, teacher commission, withdrawals, refunds, and administrator credentials.

For Docker deployment:

```bash
cp deploy/.env.example .env
docker compose up --build
```

## Project structure

```text
backend/app/       FastAPI applications, routes, models, schemas, and data access
backend/alembic/   database migrations
templates/         public, student, teacher, and admin pages
static/            browser-side JavaScript, styles, and assets
tests/             regression tests
deploy/            deployment examples
docs/              architecture, data model, security, and deployment notes
```

## Security and operational notes

- Sessions are stored in HttpOnly cookies and can be revoked through a session version.
- CI applies the complete migration chain to PostgreSQL before tests.
- Payments are confirmed manually; a provider webhook adapter is not included.
- The built-in rate limiter is process-local and should be replaced for multi-worker deployment.
- Email verification and password recovery require an external mail provider.
- The interface and seeded educational content are in Russian.

## Project status

The project is a portfolio-oriented implementation of a multi-role learning platform. Seed data is intended only for a new development database and must not be applied over real or edited data.

## Author

Sergey Inozemtsev — Python backend developer

GitHub: https://github.com/Lisovtcoff-hub
