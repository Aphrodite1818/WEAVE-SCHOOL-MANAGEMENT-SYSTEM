# Email delivery

Weave uses a single application-facing `EmailService` for transactional, security, and bulk email. The active transport is environment controlled.

## Environment policy

- **Production (`ENV=prod`)**: Resend is the only permitted provider. Set `EMAIL_PROVIDER=resend`. Production startup fails if the Resend API key or any category sender is missing.
- **Development/staging**: Resend is intentionally rejected. Existing `legacy` delivery remains available, and SES can still be selected explicitly for non-production testing.
- **Amazon SES**: the implementation and configuration are retained for future use, but AWS credentials are no longer startup requirements. The SES adapter validates its required values lazily if SES is actually selected and a send is attempted.

All email-outbox work and direct transactional/security/bulk sends already pass through `EmailService`, so the production provider policy applies to the general email worker as well as application-triggered messages.

## Production variables

Required:

```text
ENV=prod
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_...
RESEND_TRANSACTIONAL_FROM_EMAIL=no-reply@notifications.weavecloudspace.com
RESEND_SECURITY_FROM_EMAIL=security@notifications.weavecloudspace.com
RESEND_BULK_FROM_EMAIL=updates@updates.weavecloudspace.com
```

Optional shared values:

```text
EMAIL_SENDER_NAME=WEAVE
EMAIL_REPLY_TO=support@weavecloudspace.com
```

The configured sender domains must be verified in Resend before production delivery. Do not put the API key in source control, logs, test fixtures, or pull-request descriptions.

## Provider behavior

The Resend adapter uses the official async Python SDK so FastAPI/ARQ execution does not block the event loop. Provider failures are translated into Weave's `EmailProviderError`; HTTP 429 and 5xx-style failures are marked retryable so the existing outbox retry policy can handle transient delivery failures.

No production fallback to SES, Apps Script, or SMTP is performed. This is deliberate: a provider outage should surface through the existing retry/error path rather than silently switching delivery infrastructure and risking duplicate sends or configuration drift.
