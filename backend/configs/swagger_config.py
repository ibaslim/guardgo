from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

TAGS_METADATA = [
    {
        "name": "Authentication & Session",
        "description": (
            "User credentials validation, OAuth2 password flow, Two-Factor Authentication (2FA TOTP), "
            "token refresh, session invalidation, account registration, and password recovery workflows."
        ),
    },
    {
        "name": "Tenant",
        "description": (
            "Tenant organization lifecycle across Guards, Clients, and Service Providers. "
            "Includes profile updates, multi-tier compliance approvals, verification, and compliance document uploads."
        ),
    },
    {
        "name": "Tenant Management",
        "description": (
            "Tenant administration: status changes, bulk datatable queries, approvals, and activations."
        ),
    },
    {
        "name": "Users",
        "description": (
            "Tenant team member management: creating, listing, updating, and removing users within the tenant organization."
        ),
    },
    {
        "name": "User Profile",
        "description": (
            "Personal profile management for the currently authenticated user, including profile image and contact details."
        ),
    },
    {
        "name": "Service Provider Guards",
        "description": (
            "Service provider guard fleet management: guard onboarding invitations, operational coverage dispatch zones, "
            "status change requests, and provider linkage."
        ),
    },
    {
        "name": "Client Requests",
        "description": (
            "Security guard service requests created by clients or platform operators. "
            "Covers creation, pricing estimation preview, status transitions, broadcast waves, shifts, attendance, and invoicing."
        ),
    },
    {
        "name": "Request Matching",
        "description": (
            "Candidate matching engine: distance radius calculations, provincial eligibility, and reason-coded match previews."
        ),
    },
    {
        "name": "Billing",
        "description": (
            "Provincial and city pay rate configuration, guard margin defaults, service provider commission schedules, "
            "and travel distance pricing policies."
        ),
    },
    {
        "name": "Notifications",
        "description": (
            "In-app notifications delivery, unread counter queries, and batch read updates."
        ),
    },
    {
        "name": "Platform Administration",
        "description": (
            "Internal administration: platform configuration updates, staff user invites, administrative role assignments, "
            "and audit logging."
        ),
    },
    {
        "name": "Activity",
        "description": (
            "Platform activity audit log queries with entity and module filtering."
        ),
    },
    {
        "name": "System",
        "description": (
            "Platform system-level asset and branding management (admin only)."
        ),
    },
    {
        "name": "Public & System Metadata",
        "description": (
            "Public platform identity, dropdown choices (provinces, cities, document types, role groups), "
            "and authenticated document/image streaming."
        ),
    },
]

API_DESCRIPTION = """
# GuardGo API Documentation

Welcome to the interactive REST API reference for **GuardGo**, an Uber-like platform connecting clients with licensed security guards and security guard provider companies.

---

## 🏛 Supported Tenant Types

The platform supports three primary tenant types:
- **Guard** (`guard`): Individual licensed security guards managing their credentials, availability, and shift jobs.
- **Client** (`client`): Individuals or commercial entities requesting security coverage across one or more locations.
- **Service Provider** (`service_provider`): Security guard provider companies managing fleets of guards, rosters, and operational zones.

---

## 🔐 Authentication & Security

GuardGo supports multiple authentication mechanisms:
1. **OAuth2 Bearer Token**: Pass your access token in the `Authorization` header:
   ```http
   Authorization: Bearer <your_jwt_access_token>
   ```
2. **HTTP-Only Session Cookie**: Web clients automatically receive and store an `access_token` cookie upon login.
3. **Two-Factor Authentication (2FA)**:
   - When calling `POST /api/token`, if 2FA is active, the response returns `{"twofa_required": true}` and a temporary token.
   - Submit the 6-digit TOTP code to `POST /api/token/2fa/verify` to receive the full session access token.

### 🧪 Testing in Swagger UI
Click the green **Authorize** button at the top right of this page:
- Enter your registered `username` and `password` to obtain a bearer token via `POST /api/token`.
- Alternatively, paste an existing Bearer token into the `OAuth2PasswordBearer` field.
- Your authorization is persisted across page refreshes for convenient testing.

---

## 👥 Role-Based Access Control (RBAC)

Endpoints enforce role-based access control and account status (`ACTIVE`):

| Role Code | Role Name | Scope |
| :--- | :--- | :--- |
| `admin` | Super Admin | Full unrestricted platform administration |
| `ops_admin` | Operations Admin | Shift operations, broadcast reviews, and matching management |
| `support_admin` | Support Admin | User troubleshooting and customer assistance |
| `compliance_admin` | Compliance Admin | Tenant verification, license vetting, and audit approvals |
| `read_only_admin` | Read Only Admin | Read-only reporting and audit access |
| `client_admin` | Client Administrator | Creates and manages client requests, sites, and billing |
| `guard_admin` | Guard Administrator | Manages individual guard profile, licenses, and shift attendance |
| `sp_admin` | Service Provider Admin | Manages guard fleet, rosters, and provider default rates |

---

## 🔄 Core Operational Lifecycle

```
[1. Onboarding] -> [2. Verification] -> [3. Request Creation] -> [4. Candidate Matching]
       |                                                                |
       v                                                                v
[8. Payout & Invoicing] <- [7. Shift Completion] <- [6. Clock-in/out] <- [5. Rostering]
```

1. **Onboarding (`/api/signup`)**: Self-service tenant creation in `pending_activation` state.
2. **Verification (`/api/tenant/files/*`)**: Upload ID, security licenses, insurance, followed by admin approval (`/api/tenants/{id}/approve`).
3. **Request Creation (`/api/requests`)**: Client defines site location, hours, guard type, and pricing preview (`/api/requests/pricing-preview`).
4. **Matching Engine (`/api/request-matching/preview`)**: Evaluates candidates by distance radius, license eligibility, and availability.
5. **Rostering (`/api/shifts/{id}/roster`)**: Allocates guards to specific shift instances.
6. **Attendance Tracking (`/api/shift-slots/{id}/check-in`)**: Guard checks in and checks out with GPS/timestamp records.
7. **Relief & Leaves (`/api/shift-guard-leaves`)**: Handles callouts with auto-matched relief guards.
8. **Billing & Invoices (`/api/requests/{id}/invoices`, `/api/payout-invoices`)**: Automated invoice generation and payout adjustments.

---

## ⚠️ Standard Error Formats

All error responses return structured JSON:
- `400 Bad Request`: Invalid parameters or malformed identifiers.
- `401 Unauthorized`: Missing, expired, or invalid authentication token.
- `403 Forbidden`: Insufficient permissions or unverified account status.
- `404 Not Found`: Target resource does not exist.
- `422 Unprocessable Entity`: Request body validation failed (field-level error details provided).
"""


def _example_from_schema(schema: dict[str, Any], schemas: dict[str, Any], seen: set[str] | None = None) -> Any:
    """Build a useful, non-sensitive example from an OpenAPI schema."""
    seen = seen or set()

    if "$ref" in schema:
        ref_name = schema["$ref"].rsplit("/", 1)[-1]
        if ref_name in seen:
            return {}
        seen.add(ref_name)
        return _example_from_schema(schemas.get(ref_name, {}), schemas, seen)

    if "example" in schema:
        return deepcopy(schema["example"])
    if "examples" in schema and schema["examples"]:
        return deepcopy(schema["examples"][0])
    if "default" in schema:
        return deepcopy(schema["default"])
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]

    if schema.get("allOf"):
        merged = {}
        for part in schema["allOf"]:
            value = _example_from_schema(part, schemas, seen.copy())
            if isinstance(value, dict):
                merged.update(value)
        return merged

    for alternative in ("anyOf", "oneOf"):
        if schema.get(alternative):
            non_null = [item for item in schema[alternative] if item.get("type") != "null"]
            return _example_from_schema(non_null[0] if non_null else schema[alternative][0], schemas, seen)

    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        result = {}
        for name, property_schema in schema.get("properties", {}).items():
            if property_schema.get("readOnly"):
                continue
            result[name] = _example_from_schema(property_schema, schemas, seen.copy())
        return result
    if schema_type == "array":
        return [_example_from_schema(schema.get("items", {}), schemas, seen.copy())]
    if schema_type == "integer":
        return schema.get("minimum", 1)
    if schema_type == "number":
        return schema.get("minimum", 1.0)
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        fmt = schema.get("format")
        if fmt == "email":
            return "alex.morgan@example.com"
        if fmt == "date-time":
            return "2026-01-15T09:30:00Z"
        if fmt == "date":
            return "2026-01-15"
        title = str(schema.get("title", "")).lower()
        if "password" in title:
            return "ChangeMe123!"
        return "example-value"
    return {}


def _parameter_example(parameter: dict[str, Any]) -> Any:
    schema = parameter.get("schema", {})
    name = str(parameter.get("name", "")).lower()
    if "example" in parameter:
        return parameter["example"]
    if "examples" in parameter and parameter["examples"]:
        return next(iter(parameter["examples"].values())).get("value")
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if schema.get("type") == "integer":
        if name in {"page", "page_number"}:
            return 1
        if name in {"rows", "limit", "page_size"}:
            return 20
        return schema.get("default", 1)
    if schema.get("type") == "boolean":
        return schema.get("default", True)
    if parameter.get("in") == "path":
        if "token" in name:
            return "c8f3b2a19e4d075bc6e91f24"
        return "507f1f77bcf86cd799439011"
    if "status" in name:
        return "active"
    if "keyword" in name:
        return "security"
    return "example-value"


def _response_example(path: str, method: str) -> Any:
    """Rich, domain-accurate response examples for endpoints."""
    # Auth endpoints
    if path == "/api/token":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "twofa_required": False,
            "user": {
                "id": "651a2b3c4d5e6f7a8b9c0d1e",
                "username": "guard_admin",
                "email": "guard@example.com",
                "role": "guard_admin",
                "tenant_uuid": "651a2b3c4d5e6f7a8b9c0d2f",
            },
        }
    if path == "/api/token/demo":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo...",
            "token_type": "bearer",
            "twofa_required": False,
        }
    if path == "/api/token/2fa/verify":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.verified...",
            "token_type": "bearer",
            "status": "verified",
        }
    if path == "/api/token/refresh":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refreshed...",
            "token_type": "bearer",
        }
    if path == "/api/logout":
        return {"detail": "Logged out"}
    if path == "/api/signup":
        return {
            "message": "User registered successfully. Please verify your email.",
            "tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
            "username": "client_corp",
            "status": "pending_activation",
        }
    if path == "/api/signup/verificaion":
        return {"message": "Verification email resent successfully"}
    if path.startswith("/api/verify/"):
        return {"message": "Email verified successfully. Account is now active."}
    if path == "/api/forgot":
        return {"message": "If the email is registered, password reset instructions have been sent."}
    if path == "/api/updatePassword":
        return {"message": "Password updated successfully"}
    if path.startswith("/api/reset/context/"):
        return {"valid": True, "email": "user@example.com", "expires_at": "2026-11-03T12:00:00Z"}
    if path.startswith("/api/invite/context/"):
        return {
            "valid": True,
            "email": "invitee@example.com",
            "role": "guard_admin",
            "tenant_name": "Apex Security Services",
        }
    if path == "/api/invite/activate":
        return {"message": "Account activated successfully. You can now log in."}

    # Public metadata
    if path == "/api/public":
        return {
            "name": "GuardGo Security Platform",
            "version": "1.0.0",
            "logo_url": "/api/s/static/system/logo-main",
            "support_email": "support@guardgo.ca",
            "maintenance_mode": False,
        }
    if path == "/api/public/guard-metadata":
        return {
            "countries": ["Canada"],
            "canadianProvinces": [{"code": "ON", "name": "Ontario"}, {"code": "BC", "name": "British Columbia"}],
            "identityDocumentTypes": [{"code": "PASSPORT", "label": "Passport"}, {"code": "DRIVERS_LICENSE", "label": "Driver's License"}],
            "securityLicenseTypes": [{"code": "ONTARIO_SECURITY_GUARD", "label": "Ontario Security Guard License"}],
        }
    if path == "/api/public/client-metadata":
        return {
            "siteTypeOptions": [{"value": "commercial", "label": "Commercial Building"}, {"value": "residential", "label": "Residential Complex"}],
            "guardTypeOptions": [{"value": "static", "label": "Static Guard"}, {"value": "patrol", "label": "Patrolling Guard"}],
        }
    if path == "/api/public/role-metadata":
        return {
            "platformRoles": ["admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"],
            "tenantSettingsRoles": ["client_admin", "guard_admin", "sp_admin"],
        }

    # Tenant endpoints
    if path == "/api/tenant" and method == "get":
        return {
            "id": "651a2b3c4d5e6f7a8b9c0d2f",
            "tenant_type": "guard",
            "status": "active",
            "verified": True,
            "profile": {
                "first_name": "Marcus",
                "last_name": "Vance",
                "phone": "+1-416-555-0199",
                "address": {"city": "Toronto", "province": "ON", "postal_code": "M5V 2T6"},
            },
            "approvals_required": 2,
            "approvals_done": 2,
            "approvals_remaining": 0,
        }
    if path == "/api/tenants" and method == "get":
        return {
            "items": [
                {
                    "id": "651a2b3c4d5e6f7a8b9c0d2f",
                    "name": "Marcus Vance",
                    "tenant_type": "guard",
                    "status": "active",
                    "verified": True,
                }
            ],
            "total": 1,
            "page": 1,
            "rows": 20,
        }
    if path == "/api/me" and method == "get":
        return {
            "id": "651a2b3c4d5e6f7a8b9c0d1e",
            "username": "guard_mvance",
            "email": "marcus.vance@example.com",
            "full_name": "Marcus Vance",
            "role": "guard_admin",
            "tenant_uuid": "651a2b3c4d5e6f7a8b9c0d2f",
            "status": "active",
        }
    if path == "/api/users" and method == "get":
        return [
            {
                "id": "651a2b3c4d5e6f7a8b9c0d1e",
                "username": "guard_mvance",
                "email": "marcus.vance@example.com",
                "role": "guard_admin",
                "status": "active",
            }
        ]

    # Service provider guards
    if path.startswith("/api/sp/guards"):
        return {
            "items": [
                {
                    "guard_tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
                    "name": "Marcus Vance",
                    "email": "marcus.vance@example.com",
                    "status": "active",
                    "operational_region_code": "ON",
                    "operational_city_code": "TORONTO",
                    "max_travel_radius_km": 35.0,
                }
            ],
            "total": 1,
            "page": 1,
            "rows": 20,
        }

    # Requests & shifts
    if path == "/api/requests" and method == "get":
        return {
            "items": [
                {
                    "id": "651b3c4d5e6f7a8b9c0d3e4f",
                    "title": "Commercial Plaza Overnight Security",
                    "status": "published",
                    "fulfillment_mode": "auto_match",
                    "site": {"name": "Metro Square", "city": "Toronto", "province": "ON"},
                    "start_date": "2026-11-10",
                    "end_date": "2026-11-20",
                    "estimated_total": 4800.00,
                }
            ],
            "total": 1,
            "page": 1,
            "rows": 20,
        }
    if path == "/api/requests/pricing-preview":
        return {
            "estimated_hours": 80.0,
            "base_rate_per_hour": 32.50,
            "holiday_rate_per_hour": 48.75,
            "travel_allowance": 120.00,
            "subtotal": 2720.00,
            "tax": 353.60,
            "estimated_total": 3073.60,
            "currency": "CAD",
        }
    if path == "/api/request-matching/preview":
        return {
            "candidates": [
                {
                    "guard_tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
                    "name": "Marcus Vance",
                    "distance_km": 8.4,
                    "eligible": True,
                    "match_score": 96.5,
                    "reasons": ["VALID_LICENSE", "WITHIN_RADIUS", "AVAILABLE"],
                }
            ],
            "total_candidates": 1,
        }
    if path == "/api/shifts":
        return {
            "items": [
                {
                    "shift_id": "651c4d5e6f7a8b9c0d4e5f6a",
                    "request_id": "651b3c4d5e6f7a8b9c0d3e4f",
                    "date": "2026-11-10",
                    "start_time": "22:00",
                    "end_time": "06:00",
                    "status": "scheduled",
                    "assigned_guard": "Marcus Vance",
                }
            ],
            "total": 1,
        }
    if "/shift-slots/" in path:
        return {
            "slot_id": "651d5e6f7a8b9c0d5e6f7a8b",
            "status": "in_progress",
            "checked_in_at": "2026-11-10T21:58:32Z",
            "confirmed_by_client": True,
        }

    # Invoices & Billing
    if "invoice" in path.lower():
        return {
            "items": [
                {
                    "invoice_id": "INV-2026-00841",
                    "invoice_number": "GG-841",
                    "subtotal": 1200.00,
                    "tax": 156.00,
                    "total": 1356.00,
                    "currency": "CAD",
                    "status": "approved",
                    "due_date": "2026-11-25",
                }
            ],
            "total": 1,
        }
    if path == "/api/billing/metadata":
        return {
            "provinces": ["ON", "BC", "AB", "QC"],
            "citiesByProvince": {
                "ON": ["TORONTO", "OTTAWA", "MISSISSAUGA", "HAMILTON"],
                "BC": ["VANCOUVER", "VICTORIA", "SURREY"],
            },
        }
    if path.startswith("/api/billing/"):
        return [
            {
                "region_code": "ON",
                "city_code": "TORONTO",
                "standard_rate": 28.50,
                "weekend_rate": 32.00,
                "holiday_rate": 42.75,
                "currency": "CAD",
            }
        ]

    # Notifications
    if path == "/api/notifications/unread-count":
        return {"unread_count": 3}
    if path.startswith("/api/notifications"):
        return {
            "items": [
                {
                    "id": "651e6f7a8b9c0d6e7f8a9b0c",
                    "title": "Shift Assignment Confirmed",
                    "message": "You have been assigned to shift on 2026-11-10 at Metro Square.",
                    "read": False,
                    "created_at": "2026-11-02T16:00:00Z",
                }
            ],
            "total": 1,
            "unread_count": 3,
        }

    # Platform Admin
    if path == "/api/admin/platform-roles":
        return [
            {"value": "ops_admin", "label": "Ops Admin"},
            {"value": "support_admin", "label": "Support Admin"},
            {"value": "compliance_admin", "label": "Compliance Admin"},
            {"value": "read_only_admin", "label": "Read Only Admin"},
        ]
    if path.startswith("/api/admin/platform-users"):
        return [
            {
                "id": "651f7a8b9c0d7e8f9a0b1c2d",
                "username": "sarah.compliance",
                "email": "sarah.c@guardgo.ca",
                "role": "compliance_admin",
                "status": "active",
                "invite_pending": False,
            }
        ]

    if method == "delete":
        return {"detail": "Resource deleted successfully"}
    return {"message": "Operation completed successfully", "status": "success"}


def _add_openapi_examples(document: dict[str, Any]) -> dict[str, Any]:
    schemas = document.setdefault("components", {}).setdefault("schemas", {})

    # Ensure security schemes include OAuth2 password bearer
    sec_schemes = document.setdefault("components", {}).setdefault("securitySchemes", {})
    sec_schemes["OAuth2PasswordBearer"] = {
        "type": "oauth2",
        "description": (
            "Authenticate using OAuth2 password flow via `/api/token`, or provide an existing Bearer token. "
            "Click **Authorize** to log in."
        ),
        "flows": {
            "password": {
                "tokenUrl": "/api/token",
                "scopes": {},
            }
        },
    }

    # Walk all paths and enhance parameters, request bodies, and responses
    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue

            # Enrich parameters with parameter examples and descriptions
            for parameter in operation.get("parameters", []):
                parameter.setdefault("example", _parameter_example(parameter))
                pname = parameter.get("name", "")
                if not parameter.get("description"):
                    if parameter.get("in") == "path":
                        parameter["description"] = f"Unique resource identifier for {pname}."
                    elif pname in {"page", "page_number"}:
                        parameter["description"] = "Pagination page number (1-indexed)."
                    elif pname in {"rows", "limit"}:
                        parameter["description"] = "Number of items to return per page."
                    elif pname == "keyword":
                        parameter["description"] = "Keyword search query to filter results."
                    elif pname == "status":
                        parameter["description"] = "Lifecycle status filter."

            # Enrich request bodies
            request_body = operation.get("requestBody")
            if request_body:
                for media_type, media in request_body.get("content", {}).items():
                    if media_type in {"application/json", "application/*+json", "application/x-www-form-urlencoded"}:
                        schema = media.get("schema", {})
                        media.setdefault("example", _example_from_schema(schema, schemas))

            # Enrich responses
            responses = operation.setdefault("responses", {})

            # 2xx Success response
            for status, response in responses.items():
                if not status.startswith("2"):
                    continue
                content = response.setdefault("content", {})
                media = content.setdefault("application/json", {"schema": {"type": "object"}})
                media.setdefault("example", _example_from_schema(media.get("schema", {}), schemas))
                if not media.get("example") or media["example"] == {}:
                    media["example"] = _response_example(path, method)

            # Standard error responses for comprehensive documentation
            if "400" not in responses:
                responses["400"] = {
                    "description": "Bad Request — invalid input payload or malformed identifiers.",
                    "content": {
                        "application/json": {
                            "example": {"detail": "Invalid request parameters or payload structure."}
                        }
                    },
                }
            if "401" not in responses and not (path.startswith("/api/token") or path.startswith("/api/public") or path.startswith("/api/signup") or path.startswith("/api/forgot")):
                responses["401"] = {
                    "description": "Unauthorized — missing, invalid, or expired session token.",
                    "content": {
                        "application/json": {
                            "example": {"detail": "Authentication credentials were not provided or expired."}
                        }
                    },
                }
            if "403" not in responses and not (path.startswith("/api/public") or path == "/api/token"):
                responses["403"] = {
                    "description": "Forbidden — user does not hold the required role or active status.",
                    "content": {
                        "application/json": {
                            "example": {"detail": "Access forbidden: insufficient role permissions."}
                        }
                    },
                }
            if "404" not in responses and ("{" in path):
                responses["404"] = {
                    "description": "Not Found — target resource identifier does not exist.",
                    "content": {
                        "application/json": {
                            "example": {"detail": "The requested resource could not be found."}
                        }
                    },
                }
            if "422" not in responses and method in {"post", "put", "patch"}:
                responses["422"] = {
                    "description": "Validation Error — request schema or field validation constraint failure.",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": [
                                    {
                                        "loc": ["body", "email"],
                                        "msg": "value is not a valid email address",
                                        "type": "value_error",
                                    }
                                ]
                            }
                        }
                    },
                }

    return document


def configure_swagger(app: FastAPI):
    app.swagger_ui_init_oauth = {
        "appName": "GuardGo API",
        "usePkceWithAuthorizationCodeGrant": False,
    }

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="GuardGo Security Guard Management Platform API",
            version="1.0.0",
            summary="REST API for clients, security guards, service providers, and administrators.",
            description=API_DESCRIPTION,
            routes=app.routes,
            tags=TAGS_METADATA,
        )

        app.openapi_schema = _add_openapi_examples(schema)
        return app.openapi_schema

    app.openapi = custom_openapi

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui():
        swagger_ui_parameters = {
            "docExpansion": "none",
            "filter": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
            "syntaxHighlight.theme": "monokai",
            "defaultModelsExpandDepth": 1,
            "defaultModelExpandDepth": 1,
        }

        swagger_ui_html = get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="GuardGo API Documentation",
            swagger_css_url="/static/swagger-code.css",
            swagger_favicon_url="/static/guardgo-favicon.svg",
            oauth2_redirect_url="/docs/oauth2-redirect",
            swagger_ui_parameters=swagger_ui_parameters,
        ).body.decode("utf-8")

        swagger_ui_html += """
        <script>
            window.addEventListener('load', function() {
                var token = localStorage.getItem('swagger_access_token');
                if (token && window.ui) {
                    window.ui.preauthorizeApiKey("OAuth2PasswordBearer", "Bearer " + token);
                }
            });
        </script>
        """

        return HTMLResponse(content=swagger_ui_html)

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_ui():
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="GuardGo API Reference (ReDoc)",
            redoc_favicon_url="/static/guardgo-favicon.svg",
        )
