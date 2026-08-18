# Deployment notes

The included Compose file is a deployment example, not a complete hosting platform.

## Required components

- PostgreSQL;
- an HTTPS reverse proxy;
- separate public and admin host names;
- external backups and restore testing;
- centralized logs and alerts;
- an external or Redis-backed rate limiter when running multiple application workers.

## Configuration

Copy `deploy/.env.example` to `.env` and replace every placeholder. Production mode rejects debug configuration, short or placeholder secrets, wildcard CORS, SQLite, and example payment instructions.

```bash
cp deploy/.env.example .env
docker compose up --build
```

The application container binds to `127.0.0.1:8000`. The example Nginx configuration in `deploy/nginx.conf.example` forwards the public and admin hosts to that address.

After the first start:

```bash
docker compose exec infomir python -m backend.app.db.seed
docker compose exec infomir python -m backend.app.db.create_admin admin@example.com
```

Do not run the seed command over a database containing edited or real content.

## Before exposing the service

- use a unique database password and a random `SECRET_KEY` of at least 32 characters;
- restrict direct access to the application port and database;
- enable TLS and verify proxy header handling;
- restrict the admin host with an identity-aware proxy, VPN, or equivalent control;
- schedule encrypted backups and test a restore;
- replace manual billing with a provider adapter when automatic payment confirmation is required.
