````md
# Tenant Repository Documentation

This file is responsible for interacting directly with the database and performing tenant-related CRUD operations.

The repository should contain only database access logic and should not contain business logic.

---

# Imports

## Tenant

The Tenant SQLAlchemy model.

Used for all tenant database operations.

---

## TenantVerificationStatus

Enum used when checking whether a tenant has completed account verification.

Example:

```text
PENDING
VERIFIED
REJECTED
````

---

# Repository Class

## TenantRepository

Contains all tenant database operations.

---

## get_by_id_including_deleted

Fetches a single tenant using its `tenant_id`.

Unlike normal lookup methods, this method includes soft-deleted records.

### Parameters

* tenant_id

### Returns

```text
Tenant | None
```

### Use Case

```text
Superadmin wants to view a disabled tenant account.
```

---

## get_by_id

Fetches a single tenant using its `tenant_id`.

Only returns tenants that are not soft-deleted.

### Parameters

* tenant_id

### Returns

```text
Tenant | None
```

---

## get_by_slug

Fetches a tenant using its slug.

Only returns tenants that are not soft-deleted.

### Parameters

* slug

### Returns

```text
Tenant | None
```

### Example

```text
de-bright-school
```

---

## get_by_admission_prefix

Fetches a tenant using its admission number prefix.

Only returns tenants that are not soft-deleted.

### Parameters

* admission_prefix

### Returns

```text
Tenant | None
```

### Example

```text
WVS
```

---

## get_by_email

Fetches a tenant using its email address.

Only returns tenants that are not soft-deleted.

### Parameters

* email

### Returns

```text
Tenant | None
```

---

## get_by_email_including_deleted

Fetches a tenant using its email address even if they are soft_deleted

returns all tenants including soft-deleted.

### Parameters

* email

### Returns

```text
Tenant | None
```

---

## get_by_school_name

Fetches a tenant using the school name.

Only returns tenants that are not soft-deleted.

### Parameters

* school_name

### Returns

```text
Tenant | None
```

---

## get_by_school_bot_number

Fetches a tenant using the school's WhatsApp bot number.

Only returns tenants that are not soft-deleted.

### Parameters

* school_bot_number

### Returns

```text
Tenant | None
```

---

## get_all

Returns a paginated list of tenant records.

Can optionally include soft-deleted tenants.

### Parameters

* skip
* limit
* include_deleted

### Returns

```text
list[Tenant]
```

### Use Case

```text
Superadmin viewing all tenants on the platform.
```

---

## create

Creates a new tenant record.

This method should:

1. Add the tenant to the database session.
2. Refresh the instance.
3. Return the created tenant.

### Parameters

* tenant

### Returns

```text
Tenant
```

---

## save

Saves changes to a tenant instance without committing.

Useful when multiple database operations need to be committed together.

### Parameters

* tenant

### Returns

```text
Tenant
```

### Note

```text
This method should not call db.commit().
```

---

## email_exists

Checks whether a tenant email already exists.

### Parameters

* email

### Returns

```text
bool
```

### Example

```text
True  -> Email already exists
False -> Email is available
```

---

## slug_exists

Checks whether a tenant slug already exists.

### Parameters

* slug

### Returns

```text
bool
```

---

## school_bot_whatsapp_number_exists

Checks whether a WhatsApp bot number is already assigned to another tenant.

### Parameters

* school_bot_whatsapp_number

### Returns

```text
bool
```

---

## is_verified

Checks whether a tenant account has completed verification.

The lookup is performed using the tenant email.

A tenant is considered verified when:

```text
verification_status == VERIFIED
```

### Parameters

* email

### Returns

```text
bool
```

### Example

```text
True  -> Tenant account is verified
False -> Tenant account is not verified
```

```
```
