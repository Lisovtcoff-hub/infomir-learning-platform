# Security policy

## Reporting a vulnerability

Do not open a public issue containing credentials, personal data, or a working exploit. Send a minimal reproduction and the affected route to the repository owner through a private channel.

## Security model

The project includes the following controls:

- Argon2 password hashes, with transparent upgrade support for legacy PBKDF2 hashes;
- HttpOnly authentication cookies and separate public/admin sessions;
- session revocation after logout, password changes, role changes, and account deactivation;
- ownership checks for attempts, results, teacher groups, and financial records;
- host allowlists and a dedicated admin host;
- Content Security Policy, anti-framing, MIME-sniffing protection, referrer policy, and HSTS in production mode;
- server-side tariff checks, attempt time limits, and post-completion solution disclosure;
- idempotent payment confirmation and database constraints around withdrawals and commission refunds;
- audit records for sensitive administrative actions.

These controls do not replace infrastructure security. A deployment still needs HTTPS, secret management, database backups, monitoring, restricted admin access, and an external rate limiter for multiple workers.
