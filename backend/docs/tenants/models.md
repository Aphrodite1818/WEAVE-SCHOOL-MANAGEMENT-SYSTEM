````md
# Tenant Model Documentation

This file contains the model definition used to store tenant (school) information.

## Shared Imports

The Tenant model inherits from:

- `Base`
  Base SQLAlchemy model.

- `UUIDMixin`
  Automatically provides a UUID primary key (`id`).

- `TimestampMixin`
  Automatically provides:
  - `created_at`
  - `updated_at`

---

# Enumerations

## TenantStatus

Represents the current state of a tenant account.

Examples:
- TRIAL
- ACTIVE
- SUSPENDED
- EXPIRED

---

## SubscriptionPlan

Represents the subscription package assigned to a tenant.

Examples:
- FREE
- BASIC
- PREMIUM

---

## TenantVerificationStatus

Represents whether the tenant has completed account verification.

Examples:
- PENDING
- VERIFIED
- REJECTED

---





# Model Fields

## school_name

The official name of the school.

- Nullable: Yes
- Usually completed during onboarding.

---

## slug

A unique identifier generated from the school name.

Example:

```text
De Bright School
↓
de-bright-school
````

* Unique
* Auto-generated

---

## admission_number_prefix

Prefix used when generating student admission numbers.

Example:

```text
WVS00001
WVS00002
```

Where `WVS` is the prefix.

* Nullable: Yes
* If not set, student and teacher creation should be blocked.

---

## school_bot_whatsapp_number

The WhatsApp number connected to the school's AI assistant.

* Nullable: Yes

---

## email

Official school email address.

* Nullable: No
* Required during tenant registration.

---

## phone

Official school phone number.

* Nullable: Yes
* Can be added during profile completion.

---

## address

Official school address.

* Nullable: Yes

---

## city

City where the school is located.

* Nullable: Yes

---

## state

State where the school is located.

* Nullable: Yes

---

## country

Country where the school is located.

* Nullable: Yes

---

## logo_url

URL of the school's logo.

* Nullable: Yes

---

## status

Current status of the tenant account.

* Nullable: No
* Default: `TRIAL`
* Updated through business logic.

---

## plan

Current subscription plan.

* Nullable: No
* Default: `FREE`
* Updated through business logic.

---

## trial_ends_at

Date and time when the tenant's trial period ends.

* Nullable: Yes
* Managed through business logic.

---

## subscription_ends_at

Date and time when the current subscription expires.

* Nullable: Yes
* Managed through business logic.

---

## is_deleted

Soft-delete flag used to temporarily disable a tenant.

* Nullable: No
* Default: `False`

---

## max_students

Maximum number of students the tenant can create.

* Nullable: No
* Default: `500`

---

## max_teachers

Maximum number of teachers the tenant can create.

* Nullable: No
* Default: `50`

---

## feature_flags

Stores the features available to the tenant based on their subscription plan.

Examples:

* AI Assistant

* Attendance Module

* Finance Module

* Library Module

* Nullable: Yes

* Controlled through business logic.

---

## timezone

Default timezone used by the tenant.

Example:

```text
Africa/Lagos
```

* Nullable: Yes

---

## language

Default language used by the tenant.

Examples:

```text
English
French
Yoruba
```

* Nullable: Yes

---

## onboarding_completed

Indicates whether the tenant has finished setting up their school profile.

* Nullable: No
* Default: `False`

---

## branches

Stores the list of school branches owned by the tenant.

Examples:

```text
Main Campus
Ikeja Branch
Lekki Branch
```

* Nullable: Yes

---

## verification_status

Represents the tenant verification state.

Used to track OTP verification during onboarding.

Examples:

* PENDING

* VERIFIED

* Nullable: No

* Managed through authentication and onboarding logic.

```
```
