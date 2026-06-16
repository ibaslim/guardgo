# QA Guide: Authentication And Access

## What This Feature Does

This area controls how users enter the platform, verify their identity, recover access, and reach only the pages allowed for their role and account status.

## Main Roles Involved

- all tenant admins
- all platform admins
- invited users who have not finished account activation yet

## Core Scenarios

### 1. Signup

Test for each tenant type:

- client
- guard
- service provider

Verify:

- valid signup creates the account and routes the user to the welcome page
- invalid username is rejected
- invalid email is rejected
- password shorter than 8 characters is rejected
- confirm password mismatch is rejected
- tenant type is required
- duplicate username or email is rejected

### 2. Email verification

Verify:

- valid verification link activates the account
- expired or invalid verification link shows a clear failure message
- an unverified user cannot complete normal login
- resend verification works from the login screen when verification is pending

### 3. Login

Verify:

- valid login opens the dashboard
- invalid login shows an error
- protected pages redirect unauthenticated users to login
- the correct navigation appears after login based on the user role

### 4. Two-factor flow

Test this only if the target environment has 2FA-enabled accounts.

Verify:

- login can pause and request OTP code
- QR code or secret is shown when expected
- valid OTP completes login
- invalid OTP is rejected

### 5. Demo login

Verify only in environments where demo credentials are configured.

Verify:

- demo login enters the app without manual credential entry
- if demo login is configured to require 2FA, the normal 2FA screen still appears

### 6. Forgot password and reset password

Verify:

- a registered email can request a reset link
- an unknown email is rejected
- opening a valid reset link allows password change
- invalid or expired reset links are rejected
- new password must be different from the old password
- successful reset returns the user to login

### 7. Invite activation

Use this for:

- platform admin invite
- provider-owned guard invite

Verify:

- valid invite link opens the activation form
- invalid invite link is blocked
- full name is required
- username must follow format rules
- duplicate username is rejected
- successful activation returns the user to login

### 8. Logout and session handling

Verify:

- logout returns the user to login
- session is cleared after logout
- browser refresh during an active session keeps access when the token is still valid

## Route And Role Checks

Run a simple access check for each role:

- `admin`
- `ops_admin`
- `compliance_admin`
- `read_only_admin`
- `client_admin`
- `guard_admin`
- `sp_admin`

Verify:

- only allowed menu items appear
- blocked pages cannot be opened by URL
- onboarding or pending verification users are redirected to the correct gating page

## Expected UX Quality

Verify that errors are easy to understand:

- no blank failure states
- no raw backend trace
- no success message on failed action

Also verify:

- password fields behave correctly
- invite and reset links show meaningful expired-link messages
- pending verification users receive clear next-step guidance
