# Data model

Alembic is the source of truth for the schema. Apply all migrations with:

```bash
alembic -c backend/alembic.ini upgrade head
```

The current migration chain ends at `0016_production_hardening`.

## Main entities

| Area | Entities |
|---|---|
| Accounts | users, user profiles, session versions |
| Learning content | theory topics, task categories, tasks, task options |
| Exam workflow | variants, variant tasks, attempts, attempt answers |
| Access and billing | tariffs, subscriptions, payments |
| Teacher tools | teacher profiles, groups, group members, withdrawals |
| Finance and auditing | teacher commissions, administrator audit records |

Important consistency rules are enforced in both application code and database constraints. Examples include one answer per task in an attempt, one active teacher relationship per student, and restrictions around active withdrawals and refunded commission.

SQLite is convenient for local development and tests. Deployment configuration requires PostgreSQL because several financial and concurrency-sensitive operations rely on its transaction behavior.
