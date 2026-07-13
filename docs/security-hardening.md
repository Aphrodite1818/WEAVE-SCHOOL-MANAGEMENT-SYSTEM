# Security Hardening Notes

## Platform Lockdown State Loading

Platform lockdown remains availability-oriented when the emergency-control state
cannot be loaded and no prior state is known. This avoids creating a permanent
self-lockout path if the database is temporarily unavailable before the API has
ever observed a lockdown state.

After the API has observed a lockdown state, middleware keeps a short-lived
in-process last-known state. If state loading later fails and the last-known
state says lockdown was active, non-allowed traffic remains locked down. This
prevents an active emergency lockdown from silently failing open during a
temporary control-store outage.

Superadmin recovery routes are still allowed through middleware during lockdown.
They must rely on normal route dependencies to validate token signature,
expiration, session JTI, database session state, actor type, and account status.
Middleware must not trust `account_type`, `actor_type`, or `role` claims by
themselves.
