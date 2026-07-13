# Tenant Service Documentation

## Overview

`tenant_management/service.py` contains all business logic for managing school tenants on the platform. It sits between the API routes and the data layer, delegating database operations to the relevant repositories.

```
Router → TenantService → TenantRepository / TenantAdminRepository / OTPService
```

### Responsibilities

- Registering a new tenant and its admin user
- Checking email registration state to prevent duplicates
- Generating unique URL-friendly slugs
- Sending OTP verification during registration
- Fetching tenant records by ID
- Updating tenant profile and onboarding data

---

## Key Imports

### Logging

| Import       | Purpose                                      |
| ------------ | -------------------------------------------- |
| `get_logger` | Records important tenant registration events |

### Security

| Import          | Purpose                                             |
| --------------- | --------------------------------------------------- |
| `hash_password` | Hashes the tenant admin password before persistence |

### Exceptions

| Import                     | Purpose                                                      |
| -------------------------- | ------------------------------------------------------------ |
| `BadRequestException`      | Invalid input (e.g. email mismatch on update)                |
| `ConflictException`        | Duplicate record (e.g. school name, prefix, WhatsApp number) |
| `NotFoundException`        | Tenant not found                                             |
| `TooManyRequestsException` | OTP rate limit exceeded                                      |

### Utilities

| Import          | Purpose                                       |
| --------------- | --------------------------------------------- |
| `generate_slug` | Produces URL-friendly slugs from school names |

### Auth

| Import        | Purpose                                     |
| ------------- | ------------------------------------------- |
| `AuthPurpose` | Defines OTP purposes such as `VERIFICATION` |
| `RequestOTP`  | Schema for requesting an OTP                |
| `OTPService`  | Generates and sends verification OTPs       |

### Tenant Admin

| Import                  | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `TenantAdmin`           | Tenant admin model                         |
| `TenantAdminStatus`     | Defines admin account states               |
| `TenantAdminRepository` | DB operations for tenant admins            |
| `TenantAdminCreate`     | Schema for creating a tenant admin profile |
| `TenantAdminService`    | Business logic for the tenant admin module |

### Tenant Management

| Import                           | Purpose                                                 |
| -------------------------------- | ------------------------------------------------------- |
| `Tenant`                         | Tenant model                                            |
| `TenantVerificationStatus`       | Verification states: `PENDING_VERIFICATION`, `REJECTED` |
| `TenantStatus`                   | Lifecycle states of a tenant account                    |
| `TenantRepository`               | DB operations for tenants                               |
| `TenantRegisterRequest`          | Schema for tenant registration                          |
| `TenantUpdate`                   | Schema for tenant profile updates                       |
| `TenantOnboardingStatusResponse` | Response schema for onboarding status                   |
| `TenantOnboardingUpdate`         | Input schema for completing tenant onboarding           |

---

## `EmailRegistrationState`

An enum that determines how the system should treat a given email during registration.

| State       | Meaning                                  | System Behaviour                           |
| ----------- | ---------------------------------------- | ------------------------------------------ |
| `AVAILABLE` | No user or tenant exists with this email | Proceed with new registration              |
| `PENDING`   | Account exists but is not yet verified   | Resend OTP instead of creating a duplicate |
| `ACTIVE`    | Email belongs to an active account       | Prompt user to log in                      |
| `REJECTED`  | Tenant registration was rejected         | Direct user to contact support             |
| `DELETED`   | A deleted tenant owns the email          | Block reuse of the email                   |

---

## Helper Functions

### `_normalize_email(email: str)`

Strips whitespace and lowercases the email before any comparison or save.

```
" Admin@School.com " → "admin@school.com"
```

---

### `_normalize_school_name(school_name: str)`

Strips leading and trailing whitespace from the school name.

```
"  Bright College  " → "Bright College"
```

---

### `_normalize_admission_number_prefix(prefix: str | None)`

Strips whitespace, uppercases the prefix, and returns `None` if the result is empty.

```
" wvs " → "WVS"
```

---

### `_is_tenant_onboarding_complete(...)`

Returns `True` only when the tenant has all of the following fields populated:

- `school_name`
- `email`
- `admission_number_prefix`

Returns `False` otherwise.

---

## TenantService

### Class Constant

```python
ONBOARDING_REQUIRED_FIELDS = [
    "admission_number_prefix",
    "address",
    "city",
    "state",
]
```

These are the fields a tenant must fill in to complete onboarding.

---

### `get_email_registration_state(user, tenant)`

Determines the registration state of an email by inspecting existing user and tenant records.

**Logic (evaluated top to bottom):**

1. Tenant exists and is **deleted** → return `DELETED`
2. Tenant exists and verification status is **`REJECTED`** → return `REJECTED`
3. No user and no tenant exist → return `AVAILABLE`
4. User exists and account status is **`PENDING`** → return `PENDING`
5. Tenant exists and verification status is **`PENDING_VERIFICATION`** → return `PENDING`
6. None of the above → return `ACTIVE`

This prevents duplicate tenant registration and allows pending users to resume verification.

---

### `_unique_slug(db, school_name)`

Generates a unique slug for a **new** tenant.

```
"De Bright College" → "de-bright-college"
```

If the slug is already taken, a numeric suffix is appended:

```
de-bright-college
de-bright-college-1
de-bright-college-2
```

Uses `TenantRepository.slug_exists()` to check availability.

---

### `_unique_slug_for_tenant(db, school_name, tenant_id)`

Generates a unique slug when an **existing** tenant updates their school name.

Unlike `_unique_slug`, this method allows the current tenant to retain its own existing slug, preventing an unnecessary suffix from being added when the name has not actually changed.

---

### `register_tenant(db, payload, background_tasks=None)`

Handles the full tenant registration flow.

**Step 1 — Normalize Input**
Cleans `school_name`, `email`, and `admission_number_prefix` for consistent comparison.

**Step 2 — Open Transaction**
Wraps tenant and admin creation in `async with db.begin()` so that any failure rolls back all changes atomically.

**Step 3 — Duplicate Checks**
Validates that the following are not already in use:

- School name
- Email (user and tenant)
- Admission number prefix

**Step 4 — Determine Email State**
Calls `get_email_registration_state()` to classify the email as `AVAILABLE`, `PENDING`, `ACTIVE`, `REJECTED`, or `DELETED`.

**Step 5 — Block Conflicting States**
Raises `ConflictException` if the state is `DELETED`, `ACTIVE`, or `REJECTED`.

**Step 6 — Handle Pending Registration**
If the state is `PENDING`, the existing tenant is reused and an OTP resend is prepared instead of creating a new record.

**Step 7 — Create Tenant and Admin**
If the email is `AVAILABLE`:

1. Generate a unique slug
2. Hash the password
3. Create and save the `Tenant` record
4. Create and save a `TenantAdmin` record with:
   - `role = ADMIN`
   - `account_status = PENDING`
   - `tenant_id = tenant.id`
   - `is_verified = False`

**Step 8 — Generate OTP**
Calls `OTPService.generate_otp()` with purpose `VERIFICATION` to send a code to the admin email.

**Step 9 — Handle OTP Rate Limiting**
If `TooManyRequestsException` is raised:

- New registrations fail.
- Pending registrations return a message telling the user to wait or use the latest OTP.

**Step 10 — Return Response**
Key response fields:

| Field                   | Purpose                              |
| ----------------------- | ------------------------------------ |
| `verification_required` | Indicates OTP verification is needed |
| `purpose`               | The OTP purpose                      |
| `redirect_to`           | Where the frontend should navigate   |
| `resend_otp_available`  | Whether OTP resend is applicable     |

---

### `get_tenant_by_id(db, tenant_id)`

Fetches a tenant by its UUID.

- Returns the tenant object if found.
- Raises `NotFoundException` with `"Tenant not found"` if the ID does not match any record.

---

### `update_tenant_profile(db, tenant_id, payload)`

Updates tenant profile or onboarding information.

**Step 1 — Fetch Tenant**
Calls `get_tenant_by_id`. Raises `NotFoundException` if the tenant does not exist.

**Step 2 — Extract Fields**
Only processes fields that were explicitly provided in the request. Returns early with no changes if the payload is empty.

**Step 3 — Update School Name**
If `school_name` is provided:

- Strips whitespace
- Validates it is not empty
- Checks it is not already in use by another tenant
- Generates a new slug if the name changed

**Step 4 — Validate Email**
If `email` is provided, it is normalized. The tenant email cannot be changed via this endpoint — it is tied to the admin onboarding flow. A different email raises `BadRequestException`.

**Step 5 — Validate WhatsApp Bot Number**
If `school_bot_whatssap_number` is provided, the service verifies no other tenant is using it. Raises `ConflictException` on a clash.

**Step 6 — Validate Admission Number Prefix**
If `admission_number_prefix` is provided:

- Normalizes the value
- Checks that no other tenant already holds the prefix
- Raises `ConflictException` if taken

**Step 7 — Recalculate Onboarding Status**
Calls `_is_tenant_onboarding_complete()` to determine whether `onboarding_completed` should be set to `True`.

**Step 8 — Save and Return**
Applies changes through the repository, commits the transaction, refreshes the record, and returns the updated tenant.

---

### `update_tenant_onboarding(db, tenant_id, payload)`

A thin wrapper that updates onboarding-specific fields.

Internally calls `update_tenant_profile()` with the data from `payload` (`TenantOnboardingUpdate`).

**Arguments:**

| Parameter   | Type                     |
| ----------- | ------------------------ |
| `db`        | `AsyncSession`           |
| `tenant_id` | `uuid.UUID`              |
| `payload`   | `TenantOnboardingUpdate` |

---

### `get_tenant_onboarding_status(db, tenant_id)`

Returns the current onboarding status for a tenant.

**Arguments:**

| Parameter   | Type           |
| ----------- | -------------- |
| `db`        | `AsyncSession` |
| `tenant_id` | `uuid.UUID`    |

**Returns:** `TenantOnboardingStatusResponse`

**Procedure:**

1. Fetches the tenant by calling `get_tenant_by_id()`
2. Constructs and returns a `TenantOnboardingStatusResponse`

**Response fields:**

| Field                  | Value                                      | Notes                                |
| ---------------------- | ------------------------------------------ | ------------------------------------ |
| `actor_type`           | `"tenant_admin"`                           | Hardcoded                            |
| `tenant_id`            | `tenant.id`                                |                                      |
| `onboarding_required`  | `not tenant.onboarding_completed`          | `True` means onboarding still needed |
| `onboarding_completed` | `tenant.onboarding_completed`              | Direct value from DB                 |
| `completion_target`    | `"tenant"`                                 | Hardcoded                            |
| `required_fields`      | `TenantService.ONBOARDING_REQUIRED_FIELDS` | Class-level constant                 |
| `current_values`       | `dict[str, Any]`                           | Snapshot of tracked profile fields   |

**Fields tracked in `current_values`:**

```
school_name, email, admission_number_prefix,
phone, address, city, state, country,
logo_url, timezone, language, school_bot_whatssap_number
```

> `onboarding_required` and `onboarding_completed` are intentionally redundant — consumers can use whichever is more convenient without having to negate the value themselves.

---

## Integration Summary

The core registration integration follows this chain:

```
TenantService.register_tenant()
        │
        ├── TenantRepository       → creates Tenant record
        ├── TenantAdminRepository  → creates TenantAdmin record
        └── OTPService             → sends verification OTP
```

The service controls the full tenant lifecycle: from first registration through OTP verification, profile updates, and onboarding completion.
