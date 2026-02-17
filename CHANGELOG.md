# Changelog

All notable changes to GuardGo will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [Unreleased]

### Added
- Issuing authority support for guard and service provider security licenses.
- Provincial issuing authority lookup for Canadian provinces and territories.
- Guard types multiselect selector reused across tenants with a generic selector.
- Built end-to-end onboarding flows for guard, client, and service provider tenants.

### Changed
- Profile picture/logo section moved to the top of all tenant onboarding pages.
- Profile picture upload component spacing aligned to Tailwind defaults.
- Service provider onboarding form aligned with expanded backend schema.

### Fixed
- Guard/service provider payload mappings for license fields and provinces.
- Region creation requiring province for Canada.

## [0.1.0] - 2026-02-11

### Added
- Initial GuardGo application structure.
- FastAPI backend with tenant profile APIs.
- Angular frontend with tenant onboarding flows.
