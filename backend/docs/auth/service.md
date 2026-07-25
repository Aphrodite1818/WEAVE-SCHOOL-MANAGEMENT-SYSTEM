# AUTH SERVICE

This file contains the business logic for authentication.

The auth service handles:

* Login
* Superadmin login
* OTP generation
* OTP verification
* Password reset
* Tenant activation
* Parent invite acceptance
* Teacher invite acceptance
* Superadmin invite acceptance

This service depends heavily on:

* AuthRecord table
* tenant_admins table
* tenants table
* auth_identity table
* teachers, parents , students table 

The `AuthRecord` table stores temporary authentication values like OTPs, reset tokens, invite tokens, and activation tokens.


The `AuthIdentity` table maps a login identifier to the actual account record.


It currently stores supported identifiers like `email` or `admission_number`, and it helps the backend determine which table to query based on that identifier.



---

# SIMPLE FLOW OF THE AUTH SERVICE

```txt
User performs auth action
↓
AuthService validates the request
AuthService tries to authenticate by checking superadmin table first if not superadmin 


looks up auth_identity and tries to find an active match and 
queries the right table based on actor_type 

authenticates user and returns jwt
```

---

# IMPORTS

## random

Used to generate OTP digits.

## secrets

Used to generate secure random tokens for invite links, activation links, and password reset tokens.

## string

Used together with `random` to generate numeric OTP codes.

## dataclass

Used to create a simple class for storing logged-in user information.

## datetime, timezone, timedelta

Used to handle token expiry times.

## quote

Used to safely place tokens inside URLs.

Example:

```txt
raw token → safe URL token
```

## FastAPI BackgroundTasks

Used to send emails in the background instead of blocking the request.

## SQLAlchemy tools

Used for direct database queries:

* `select`
* `delete`
* `func`
* `with_for_update`

## Security helpers

These helpers handle password, OTP, and token security:

* `hash_auth_secret`
* `hash_otp`
* `hash_password`
* `verify_otp_hash`
* `verify_password`

## Exceptions

Used to stop requests in a controlled way:

* `AccountNotVerifiedException`
* `BadRequestException`
* `NotFoundException`
* `TooManyRequestsException`
* `UnauthorizedException`

## Email helpers

Used to send authentication emails:

* OTP email
* Tenant activation email

---

# IMPORTANT IDEA

The auth service does not store raw OTPs or raw tokens.

Instead, it stores hashed values.

```txt
Raw token/code
↓
Hash it
↓
Store hashed value in database
```

When the user sends the raw token/code back:

```txt
Raw token/code from user
↓
Hash or verify it
↓
Compare with stored hash
```

This is safer because even if the database leaks, attackers do not directly see usable tokens.

---

# Auth related imports 

# models
* AuthPurpose 
* AuthRecord

# Schemas 
* LoginSessionUser
* LoginRequest
* RequestOTP
* TenantActivationRequest
* UpdatePassword
* VerifyOTP


# Auth_Identity related imports 

# models 
* ActorType
* IdentifierType


# Service 
* AuthIdentityService



# Parent related imports 

# models
* Parent
* ParentAccountStatus

# repository
* ParentRepository



# Student releated imports 

# models
* Student
* StudentAccountStatus


# repository
* StudentRepository



# Superadmin related imports 

# models

* SuperAdmin

# repository
* SuperAdminRepository


# Teacher releated imports 

# models
* Teacher
* TeacherAccountStatus

# repository
* TeacherRepository




# TenantAdmin related imports 


# models
* TenantAdmin 
* TenanAdminStatus

# repository
* TenantAdminRepository


# Tenant related imports 

# models 
* Tenant
* TenantStatus
* TenantVerificationStatus

# repository
* TenantRepository



# HELPER FUNCTIONS

## `_normalize_email`

Cleans an email before using it.

It:

* Removes extra spaces
* Converts email to lowercase

Example:

```txt
" Admin@School.com " → "admin@school.com"
```

---



## `_enum_value`
return a stable string representation for enum-like values 





## `_get_platform_email_conflicts`

Checks whether an email already exists in any major platform account table.

It checks:

* TenantAdmin table 
* Tenant table
* SuperAdmin table
* Teacher table
* Parent table

It returns:

```txt
existing_tenant_admin
existing_tenant
existing_superadmin
```

This is useful because the same email should not accidentally belong to different account types.

---

## `_authenticate_superadmin`

Handles superadmin login.

Flow:

```txt
Find superadmin by email
↓
If not found, return None
↓
Check password
↓
Check if superadmin is active
↓
Update last login time
↓
Save and return superadmin
```

If the password is wrong or the account is inactive, it raises `UnauthorizedException`.

---




## `_authenticate_tenant_admin`
Authenticates a tenant admin through AuthIdentity 

arguments:
db,
email
password
background_tasks


steps:
* normalizes the email 
* tries to resolve the identifier and pull relevant information (actor_type ,actor_id , tenant_id) returns None if not found exception is raised

* if the resolved actor type is not TENANT_ADMIN enum type it returns None 
* queries the TenantAdmin table to fetch info about the tenant  
* performs some verification checks 
*  if verification checks passes it updates the last_login_at for the tenant_admin commits that to the db and returns the admin object 






## `_tenant_allows_login`

Checks if a tenant is allowed to login.

A tenant can login only if:

* Tenant exists
* Tenant is not deleted
* Tenant verification status is `ACTIVE`
* Tenant status is either `ACTIVE` or `TRIAL`

This protects the system from allowing users under inactive, deleted, rejected, or unverified tenants to login.

---

## `_tenant_allows_activation_completion`

Checks if a tenant is in the correct state to complete tenant activation.

The tenant must:

* Exist
* Not be deleted
* Have verification status `PENDING_VERIFICATION`
* Have tenant status `INACTIVE`

This is for tenants manually created by a superadmin.

---

## `_tenant_allows_otp_verification`

Checks if a tenant is allowed to complete OTP verification.

The tenant must:

* Exist
* Not be deleted
* Have verification status `PENDING_VERIFICATION`
* Have status `ACTIVE` or `TRIAL`

This is mostly for public tenant signup accounts.

---


## `_resolve_identifier_type`
helper method to guess whether identifier is an email or an admission number 




## `_authenticate_tenant_actor`
this helper function helps authenticate any type of actor within the tenant 

procedures:
* tries to resolve the identity by checking the AuthIdentity table retuns None if not found 

* if found it calls the 

## `_user_can_reset_password`

Checks if a user is allowed to reset password.

The user must:

* Exist
* Have account status `ACTIVE`
* Be verified
* Belong to a tenant that allows login

This prevents password reset for pending, unverified, deleted, or inactive accounts.

---

# DATACLASS

## `AuthenticatedActor`

This dataclass stores information about the person who successfully logged in.

It stores:

* `account_type`
* `actor_id`
* `email`
* `role`
* `tenant_id`

This is useful because the system supports different login types:

```txt
superadmin
tenant user
```

---

# AuthService

This class handles the main authentication logic.

---

## `_build_verification_required_payload`

Builds the JSON response body that tells the frontend a user needs OTP verification.

It returns data like:

```txt
message
verification_required
email
purpose
redirect_to
resend_otp_available
```

This is response formatting only.

It does not generate or verify OTP.

---

## `_otp_verification_headers`

Builds custom HTTP headers that tell the frontend a user needs OTP verification.

The headers include:

* Verification required
* Email
* OTP purpose
* Redirect page
* Whether OTP can be resent

This is also response formatting only.

It gives the frontend extra information.

---

## `_raise_verification_required`

This method is called when a user tries to continue but their account is not verified.

Flow:

```txt
Normalize email
↓
Try to send a fresh OTP
↓
If OTP was sent successfully:
    prepare success verification message
↓
If OTP was sent too recently:
    catch TooManyRequestsException
    prepare wait/retry message
    add Retry-After header
↓
Raise AccountNotVerifiedException
```

Important point:

This method always raises `AccountNotVerifiedException`.

The reason is simple:

```txt
Even if OTP was sent,
the user is still not verified yet.
```

So the current login/request must still stop.

---

## `authenticate_actor`

This method handles login.

It supports both:

* Superadmin login
* Tenant user login

Flow:

```txt
Try superadmin login first
↓
If superadmin exists and password is valid:
    return AuthenticatedActor for superadmin
↓
If not superadmin:
    check normal user table
↓
Verify user password
↓
Fetch user's tenant
↓
Check tenant status
↓
Check user status
↓
Return AuthenticatedActor for tenant user
```

Important checks:

### If user does not exist

Raise:

```txt
Invalid email or password
```

This is safer than saying “user does not exist.”

### If password is wrong

Raise:

```txt
Invalid email or password
```

### If tenant is pending verification

If tenant is inactive, user must use activation link.

If tenant is pending but not inactive, OTP verification is required.

### If tenant is rejected

Login is blocked.

### If tenant is deleted or inactive

Login is blocked.

### If user account is pending

If the pending user is the public tenant admin, OTP verification is required.

If the pending user is not the tenant admin, they must complete the relevant canonical account verification or invitation flow.

### If all checks pass

The method returns an `AuthenticatedActor`.

---

## `reset_password`

This method completes password reset after the user already received a valid reset token.

Flow:

```txt
Normalize email
↓
Hash the reset token from payload
↓
Find matching password reset AuthRecord
↓
Lock the record with with_for_update
↓
If token does not exist:
    raise invalid/expired token error
↓
If token expired:
    delete token
    raise invalid/expired token error
↓
Find user
↓
Check if user is allowed to reset password
↓
Hash new password
↓
Replace old password hash
↓
Delete reset token
↓
Commit
```

Important point:

`with_for_update()` helps prevent race conditions.

It stops two requests from using the same reset token at the same time.

---

# TenantActivationService

This class handles activation for tenants created manually by the superadmin.

This is different from public tenant signup.

Public signup uses OTP verification.

Superadmin-created tenants use activation links.

---

## `_build_invite_link`

Builds the frontend invite/activation URL.

Example:

```txt
https://app.school.com/invite?token=raw_token_here
```

The frontend reads the token from the URL and sends it back to the backend.

---

## `create_activation_record`

Creates an activation token for a tenant admin.

Flow:

```txt
Generate raw token
↓
Set expiry time
↓
Delete old tenant activation records for that email
↓
Store new hashed token in AuthRecord
↓
Return frontend invite link
```

Important point:

The raw token is sent to the user through email.

The hashed token is stored in the database.

---

## `send_activation_email`

Sends the activation email to the tenant admin.

Flow:

```txt
Build email subject
↓
Build email HTML body
↓
If background_tasks exists:
    send email in background
↓
Else:
    send email immediately
↓
If email fails:
    raise BadRequestException
```

---

## `activate_tenant`

Activates a tenant account when the tenant admin clicks the invite link and submits the form.

Flow:

```txt
Hash submitted token
↓
Find matching tenant activation AuthRecord
↓
Check if token exists
↓
Check if token has expired
↓
Check if submitted email matches token email
↓
Fetch user
↓
Fetch tenant
↓
Check user and tenant relationship
↓
Check tenant is allowed to activate
↓
Set user password
↓
Mark user active
↓
Mark user verified
↓
Mark tenant verification status active
↓
Move tenant from inactive to trial
↓
Delete activation record
↓
Commit
```

After this, the tenant admin can login.


## `accept_superadmin_invite`

Completes account setup for a superadmin invite.

Flow:

```txt
Hash submitted token
↓
Find superadmin invite record
↓
Check if invite exists
↓
Check if invite has already been used
↓
Check if invite has expired
↓
Check submitted email matches invite email
↓
Check email does not already belong to user or tenant
↓
Check email does not already belong to active superadmin
↓
Create new SuperAdmin account
↓
Mark invite as used
↓
Delete other active invites for same email
↓
Commit
```

After this, the new superadmin can login.

---

# OTPService

This class handles OTP generation and OTP verification.

It is used for:

* Tenant signup verification
* Password reset verification

---

## `_replace_otp_record`

Creates a new OTP record and removes old OTP records for the same email and purpose.

Flow:

```txt
Normalize email
↓
Find user
↓
If user does not exist:
    raise NotFoundException
↓
Delete old OTP record for same email and purpose
↓
Create new AuthRecord with hashed OTP
↓
Flush database
↓
Return user
```

Important point:

Only the latest OTP should remain valid.

---

## `generate_otp`

Generates and sends an OTP.

Flow:

```txt
Find user by email
↓
Find user's tenant
↓
Check OTP purpose
↓
If purpose is verification:
    only allow public tenant admin verification
    block inactive tenant activation accounts
    check tenant allows OTP verification
↓
If purpose is password reset:
    check user can reset password
↓
Check OTP rate limiter
↓
If too many requests:
    raise TooManyRequestsException
↓
Generate 6-digit OTP
↓
Set expiry time
↓
Replace old OTP record
↓
Commit if allowed
↓
Build OTP email
↓
Send email in background or immediately
↓
If email fails:
    raise BadRequestException
```

Important point:

This method does both:

* OTP database creation
* OTP email sending

---

## `verify_otp`

Verifies an OTP submitted by the user.

Flow:

```txt
Normalize email
↓
Find latest unused OTP AuthRecord for email and purpose
↓
Check OTP exists and code matches
↓
Check OTP has not expired
↓
Find user
↓
Find tenant
↓
If purpose is verification:
    check user is public tenant admin
    check tenant allows OTP verification
    activate user
    activate tenant verification
    mark OTP as used
↓
If purpose is password_reset:
    check user can reset password
    generate reset token
    delete previous password reset records
    store new reset token
    return raw reset token
↓
Commit
↓
Return response data
```

For verification OTP:

```txt
OTP code activates the account.
```

For password reset OTP:

```txt
OTP code does not directly change password.
It gives the user a reset token.
The reset token is later used by reset_password.
```

---

# FULL AUTH FLOW SUMMARY

## Public Tenant Signup Flow

```txt
Tenant registers
↓
Tenant + admin user created
↓
OTP sent
↓
Admin submits OTP
↓
verify_otp activates user and tenant
↓
Admin can login
```

---

## Superadmin-Created Tenant Flow

```txt
Superadmin creates tenant
↓
Activation record created
↓
Activation email sent
↓
Tenant admin clicks invite link
↓
Frontend sends token + email + password
↓
activate_tenant validates token
↓
Tenant and admin account become active
↓
Admin can login
```

---


## Superadmin Invite Flow

```txt
Existing superadmin sends invite
↓
Invite record created
↓
New superadmin clicks invite link
↓
Frontend sends token + email + password
↓
accept_superadmin_invite validates token
↓
New superadmin account is created
↓
New superadmin can login
```

---

## Password Reset Flow

```txt
User requests password reset OTP
↓
generate_otp sends OTP
↓
User submits OTP
↓
verify_otp returns reset_token
↓
User submits reset_token + new password
↓
reset_password updates password
```

---

# THINGS THAT CAN BREAK OR NEED ATTENTION

## 1. AuthService has no repository

This service directly queries `AuthRecord` using SQLAlchemy.

That is not automatically wrong, but it makes the service heavier.

Later, you may create an `AuthRepository` to move database queries out of the service.

---

## 2. Token purpose must always be checked

The same `AuthRecord` table stores different auth values.

So every query must check `purpose`.

Example:

```txt
PASSWORD_RESET token should not work as a tenant activation token.
```

---

## 3. Raw token must never be stored

Only hashed tokens should be stored.

The raw token should only be sent to the user once through email/link.

---

## 4. Expiry checks are important

Every OTP/token must be checked against `expires_at`.

Expired values should not be accepted.

---

## 5. Used tokens should not work again

Invite tokens and OTPs should not be reusable.

That is why `is_used` exists.

---

## 6. Tenant state controls almost everything

Even if a user exists, they should not be able to login or accept invites if their tenant is inactive, deleted, rejected, or not verified.

---

## 7. Email matching is important

For invite and activation flows, the submitted email must match the email attached to the token.

This prevents someone from using another person's invite link.

---

## 8. `with_for_update()` is used for safety

This locks records during sensitive operations.

It helps prevent two requests from using the same token at the same time.

---

# SIMPLE MENTAL MODEL

The AuthService is mostly a gatekeeper.

It asks:

```txt
Who are you?
Is your password correct?
Is your tenant active?
Is your account verified?
Is your token valid?
Is your token expired?
Has your token already been used?
Are you allowed to perform this action?
```

If all checks pass, it updates the account.

If any check fails, it raises an exception.
