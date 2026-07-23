# SCHEMAS

This file contains the Pydantic schemas used by the authentication module.

These schemas are responsible for validating incoming request data and defining the structure of authentication-related responses returned by the API.

The authentication module uses these schemas for:

* Login
* OTP requests
* OTP verification
* Password reset
* Tenant activation
* JWT token responses

---

# IMPORTS

## BaseModel

Base Pydantic class used to create schemas.

## EmailStr

Validates that a field contains a properly formatted email address.

Example:

```txt
admin@school.com
```

Invalid example:

```txt
adminschool.com
```

---

## Field

Used to add validation constraints to schema fields.

Example:

```python
password: str = Field(..., min_length=8)
```

This ensures the password meets minimum requirements.

---

# SCHEMAS

## Token

Used when returning JWT authentication tokens to the client.

### Fields

#### access_token

Stores the generated JWT access token.

#### token_type

Defines the token type.

Default value:

```txt
bearer
```

### Example Response

```json
{
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
}
```

---

## LoginSessionUser
compact authenticated actor payload returned to the frontend 

it captures just enough information for the frontend to pull 
data about logged in user





## LoginRequest

Used when a user attempts to log into the system.

### Fields

#### email

User email address.

Validated using `EmailStr`.

#### password

User password.

### Purpose

This schema is submitted to the login endpoint.

Example:

```json
{
    "email": "admin@school.com",
    "password": "Password123"
}
```

---

## UpdatePassword

Used when a user resets their password.

### Fields

#### email

Email address associated with the account.

#### new_password

The new password chosen by the user.

#### reset_token

Password reset token previously issued by the system.

### Purpose

Allows a verified password reset request to update the user's password.

---

## RequestOTP

Used when requesting an OTP from the backend.

### Fields

#### email

Email address that will receive the OTP.

#### purpose

Specifies why the OTP is being generated.

Allowed values:

```txt
verification
password_reset
```

### Purpose

The backend generates and sends an OTP to the supplied email address.

---

## VerifyOTP

Used when verifying an OTP code.

### Fields

#### email

Email address that received the OTP.

#### code

OTP code entered by the user.

#### purpose

Purpose of the OTP.

Allowed values:

```txt
verification
password_reset
```

### Purpose

Confirms that the submitted OTP is valid, not expired, and belongs to the correct purpose.

---

## TenantActivationRequest

Used when activating a tenant account that was created by a superadmin.

### Fields

#### email

Tenant administrator email address.

#### password

Password chosen by the tenant administrator.

Validation:

```txt
Minimum Length: 8
Maximum Length: 64
```

#### token

Tenant activation token.

Validation:

```txt
Minimum Length: 20
```

### Purpose

Allows a tenant administrator to claim and activate a tenant account.

---

# Authentication Flow

```txt
Login
    ↓
LoginRequest
    ↓
Token
   ↓
LoginSessionUser


Request OTP
    ↓
RequestOTP
    ↓
VerifyOTP


Forgot Password
    ↓
RequestOTP(password_reset)
    ↓
VerifyOTP(password_reset)
    ↓
UpdatePassword


Tenant Activation
    ↓
TenantActivationRequest

```
