# Architecture

## Application split

`backend.app.main:app` is an ASGI dispatcher. It sends requests to one of two FastAPI applications based on the request host:

- the public application serves the student and teacher APIs, OpenAPI documentation, templates, and static assets;
- the admin application serves a separate dashboard and administrative API on a host listed in `ADMIN_HOSTS`.

Unknown hosts are rejected before they reach either application.

## Backend layers

```text
api/routes  -> request validation and authorization dependencies
crud        -> data access and domain operations
models      -> SQLAlchemy entities and database constraints
schemas     -> Pydantic request and response models
db          -> engine, sessions, seed data, and CLI utilities
core        -> configuration, security, access rules, and rate limiting
```

The code uses synchronous SQLAlchemy sessions. Schema changes are applied only through Alembic migrations.

## Main flows

### Student learning flow

1. A student registers or signs in.
2. The API exposes theory and tasks allowed by the current tariff.
3. A practice or exam attempt is created.
4. Answers are stored against the authenticated owner.
5. The server enforces variant membership and exam time limits.
6. Correct answers are returned only after completion.

### Teacher flow

Teachers receive an invite/profile code, organize connected students into groups, inspect student progress, and request withdrawals from accrued commission.

### Billing flow

1. A student creates a payment request with an idempotency key.
2. An administrator confirms the external payment.
3. The subscription is activated in the same domain flow.
4. When a teacher is connected, a commission record is created.
5. Withdrawals and refunds are checked against existing financial records.

The repository includes a manual payment flow. A real payment provider should be implemented as a separate adapter with signed webhooks and server-side amount verification.
