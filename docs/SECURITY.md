# Security

## Implemented and tested (Milestone 1)
| Control | Detail | Test |
| --- | --- | --- |
| Password storage | Argon2id; constant-cost verification for unknown accounts | `test_passwords_are_hashed_with_argon2`, `test_duplicate_email_and_bad_credentials` |
| Sessions | HS256 JWT, 12 h expiry, httpOnly SameSite=Lax cookie (`Secure` required in prod); `none`/forged/expired tokens rejected | `test_forged_expired_and_orphaned_tokens_are_rejected` |
| Membership check | User ↔ organization membership re-read on every request | same |
| Tenant isolation | All tenant queries filter by `org_id`; foreign ids return 404 | `test_tenants_cannot_see_or_touch_each_others_data` |
| Roles | `viewer` is read-only | `test_viewer_role_is_read_only` |
| Login throttling | Per IP+email and per IP, Redis-backed when configured, in-memory otherwise | `test_login_is_rate_limited` |
| Input validation | Pydantic models with `extra="forbid"` on scan definitions; indicator params range-checked; scans are data, never evaluated as code | `test_schema_rejects_malformed_definitions`, `test_parameter_validation` |
| Entitlements | Plan limits enforced server-side from configuration | `test_plan_limits_come_from_entitlements` |
| Audit log | Registration, login, failed login, watchlist and saved-scan changes | `test_audit_log_records_security_events` |
| Production guards | API refuses to start in `prod` with the default JWT secret or insecure cookies; OpenAPI UI disabled in prod | `test_production_settings_refuse_insecure_defaults` |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `no-store` on API responses | `test_health` |
| CSV export | Formula-injection neutralised | — (manual) |
| Containers | Non-root users, health checks | — (images not built in this environment) |
| Dependencies | `npm audit --omit=dev`: 0 known vulnerabilities at time of writing; runs in CI | CI |

## Known gaps — do not expose publicly until closed
1. **No email verification, password reset, MFA or account lockout notification.**
2. **Sessions cannot be revoked** before expiry (no server-side session store / token denylist). Logout clears the cookie only.
3. **CSRF** relies on SameSite=Lax plus JSON-only bodies; add an explicit CSRF token or Origin check before launch.
4. **No general API rate limiting or per-tenant quotas** (only login/registration are throttled). Scans are CPU-heavy.
5. **Client IP** is taken from the socket; behind a proxy configure trusted `X-Forwarded-For` handling or throttling keys collapse.
6. **No Content-Security-Policy** on the web app yet (Vela's worker/blob needs must be mapped first).
7. **Secrets** come from environment variables; no secret manager integration, no rotation procedure, no encryption of data at rest beyond the database's own.
8. **No Python dependency audit** in CI (`pip-audit`), no container image scanning, no SAST.
9. **No backups, restore drill, error monitoring or alerting.**
10. Database-level row security (PostgreSQL RLS) would add defence in depth to the application-level tenant filter.
11. No invitation flow: every account is the sole owner of its own workspace.

## Reporting
Until a security contact is published, report issues privately to the repository owner.
