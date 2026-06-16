# QA Guide: Onboarding And Profiles

## What This Feature Does

This area collects the business and compliance information that makes a tenant usable in the system.

It matters because profile data is reused by:

- matching
- request creation
- billing
- approvals
- attendance operations

## Main Flows

- first-time onboarding after signup
- later profile updates from Settings
- document upload and deletion
- image upload and deletion

## Guard Profile

### What The guard profile must support

- personal information
- home address
- phone numbers
- identity document details and file
- one or more security licenses and files
- one or more police clearances and files
- one or more training certificates and files
- weekly availability
- travel radius and operating location
- preferred guard types
- emergency contact

### Happy-path scenarios

Verify:

- guard can save a complete profile
- uploaded documents appear after save
- saved availability stays in the same pattern after page refresh
- preferred guard types stay selected after save
- profile picture upload works

### Important rule checks

Verify:

- at least one security license is required
- at least one police clearance is required
- training certificate fields validate correctly when filled
- issue dates cannot be in the future
- expiry date cannot be before issue date
- expired security license is rejected
- weekly availability cannot be empty
- preferred guard type cannot be empty
- latitude and longitude must both be present when used

### Onboarding status behavior

Verify:

- a first-time guard profile save does not directly self-activate the tenant
- the tenant moves into pending activation review

## Client Profile

### What The client profile must support

- legal or company identity
- website
- primary contact
- secondary contact
- billing address
- billing method
- preferred guard types
- one or more saved sites

### Saved site checks

For each saved site, verify:

- site name can be saved
- site type is required
- address fields are required
- country, province, and city validation works
- Canadian postal code format is validated
- latitude and longitude are required
- coordinates can be reused later during request creation
- manager email validates when provided
- recommended number of guards must be at least 1 when provided

### Billing method checks

Verify:

- billing method is required
- cardholder name is required
- last 4 digits must be exactly four numbers
- expiry month and year validation works

### Onboarding status behavior

Verify:

- a first-time client profile save can activate the tenant once the required data is complete

## Service Provider Profile

### What The provider profile must support

- company details
- head office address
- security licenses and files
- insurance details and file
- operating regions
- city-level coverage entries
- coverage radius
- guard categories offered
- emergency contact
- profile picture

### Happy-path scenarios

Verify:

- provider can save a complete profile
- operating regions can be added and removed
- more than one city can be entered under a province
- security license upload works
- insurance upload works
- offered guard categories stay saved

### Important rule checks

Verify:

- at least one security license is required
- at least one operating region is required
- each selected operating city has a coverage radius
- each selected operating city has valid latitude and longitude
- head office latitude and longitude must both be present when used
- guard categories offered cannot be empty
- insurance fields validate correctly when partially filled

### Onboarding status behavior

Verify:

- first-time provider onboarding remains in pending activation flow

## File Handling Checks For All Tenant Types

Verify:

- upload success message is shown
- uploaded file still exists after refresh
- delete removes the file
- deleted file is no longer accessible from the profile
- user cannot open another tenant's protected documents through direct URL guessing

## Read-Only Profile Review

When platform users open a tenant detail drawer, verify:

- the correct tenant type layout is shown
- saved profile values are readable
- the page is review-only, not editable

## Regression Checks

After any profile edit, confirm these still work:

- login
- dashboard load
- tenant settings reopen correctly
- request creation still sees client sites
- matching still sees guard or provider location data
