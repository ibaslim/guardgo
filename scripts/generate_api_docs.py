"""Generate one readable Markdown reference file for every FastAPI route.

The route decorators remain the source of truth. Run from the repository root:

    python3 scripts/generate_api_docs.py
"""

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = ROOT / "backend" / "routes"
OUTPUT_DIR = ROUTES_DIR / "docs" / "api_docs" / "endpoints"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
MODEL_FIELDS = {}


def literal(node, default=""):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def annotation(node):
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{annotation(node.value)}.{node.attr}"
    if isinstance(node, ast.Subscript):
        return f"{annotation(node.value)}[{annotation(node.slice)}]"
    if isinstance(node, ast.Tuple):
        return ", ".join(annotation(item) for item in node.elts)
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return ast.unparse(node)


def decorator_details(decorator):
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    method = decorator.func.attr.lower()
    if method not in HTTP_METHODS or not decorator.args:
        return None
    path = literal(decorator.args[0], "")
    if not path:
        return None
    values = {keyword.arg: literal(keyword.value) for keyword in decorator.keywords if keyword.arg}
    return method.upper(), path, values


def clean_path(path):
    path = re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-").lower()
    return path or "root"


def sample_for(name, type_name):
    lowered = name.lower()
    if "email" in lowered:
        return "alex.morgan@example.com"
    if "password" in lowered:
        return "ChangeMe123!"
    if lowered in {"id", "token", "user_id", "tenant_id", "request_id", "file_id"} or lowered.endswith("_id"):
        return "507f1f77bcf86cd799439011"
    if type_name in {"int", "Integer"}:
        return "1"
    if type_name in {"float", "Float"}:
        return "1.0"
    if type_name in {"bool", "Boolean"}:
        return "true"
    return "example-value"


def json_value(value):
    if value == "true" or value == "false" or re.fullmatch(r"-?\d+(\.\d+)?", value):
        return value
    return f'"{value}"'


def response_example_for(path, method):
    lowered_path = path.lower()
    lowered_method = method.lower()

    if lowered_path == "/api/token":
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
    if lowered_path == "/api/token/demo":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo...",
            "token_type": "bearer",
            "twofa_required": False,
        }
    if lowered_path == "/api/token/2fa/verify":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.verified...",
            "token_type": "bearer",
            "status": "verified",
        }
    if lowered_path == "/api/token/refresh":
        return {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refreshed...",
            "token_type": "bearer",
        }
    if lowered_path == "/api/logout":
        return {"detail": "Logged out"}
    if lowered_path == "/api/signup":
        return {
            "message": "User registered successfully. Please verify your email.",
            "tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
            "username": "client_corp",
            "status": "pending_activation",
        }
    if lowered_path == "/api/signup/verificaion":
        return {"message": "Verification email resent successfully"}
    if lowered_path.startswith("/api/verify/"):
        return {"message": "Email verified successfully. Account is now active."}
    if lowered_path == "/api/forgot":
        return {"message": "If the email is registered, password reset instructions have been sent."}
    if lowered_path == "/api/updatepassword":
        return {"message": "Password updated successfully"}
    if lowered_path.startswith("/api/reset/context/"):
        return {"valid": True, "email": "user@example.com", "expires_at": "2026-11-03T12:00:00Z"}
    if lowered_path.startswith("/api/invite/context/"):
        return {
            "valid": True,
            "email": "invitee@example.com",
            "role": "guard_admin",
            "tenant_name": "Apex Security Services",
        }
    if lowered_path == "/api/invite/activate":
        return {"message": "Account activated successfully. You can now log in."}

    if lowered_path == "/api/public":
        return {
            "name": "GuardGo Security Platform",
            "version": "1.0.0",
            "logo_url": "/api/s/static/system/logo-main",
            "support_email": "support@guardgo.ca",
            "maintenance_mode": False,
        }
    if lowered_path == "/api/public/guard-metadata":
        return {
            "countries": ["Canada"],
            "canadianProvinces": [{"code": "ON", "name": "Ontario"}, {"code": "BC", "name": "British Columbia"}],
            "identityDocumentTypes": [{"code": "PASSPORT", "label": "Passport"}, {"code": "DRIVERS_LICENSE", "label": "Driver's License"}],
            "securityLicenseTypes": [{"code": "ONTARIO_SECURITY_GUARD", "label": "Ontario Security Guard License"}],
        }
    if lowered_path == "/api/public/client-metadata":
        return {
            "siteTypeOptions": [{"value": "commercial", "label": "Commercial Building"}, {"value": "residential", "label": "Residential Complex"}],
            "guardTypeOptions": [{"value": "static", "label": "Static Guard"}, {"value": "patrol", "label": "Patrolling Guard"}],
        }
    if lowered_path == "/api/public/role-metadata":
        return {
            "platformRoles": ["admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"],
            "tenantSettingsRoles": ["client_admin", "guard_admin", "sp_admin"],
        }

    if lowered_path == "/api/tenant" and lowered_method == "get":
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
    if lowered_path == "/api/tenants" and lowered_method == "get":
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
    if lowered_path == "/api/me" and lowered_method == "get":
        return {
            "id": "651a2b3c4d5e6f7a8b9c0d1e",
            "username": "guard_mvance",
            "email": "marcus.vance@example.com",
            "full_name": "Marcus Vance",
            "role": "guard_admin",
            "tenant_uuid": "651a2b3c4d5e6f7a8b9c0d2f",
            "status": "active",
        }
    if lowered_path == "/api/users" and lowered_method == "get":
        return [
            {
                "id": "651a2b3c4d5e6f7a8b9c0d1e",
                "username": "guard_mvance",
                "email": "marcus.vance@example.com",
                "role": "guard_admin",
                "status": "active",
            }
        ]

    if lowered_path.startswith("/api/sp/guards"):
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

    if lowered_path == "/api/requests" and lowered_method == "get":
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
    if lowered_path == "/api/requests/pricing-preview":
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
    if lowered_path == "/api/request-matching/preview":
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
    if lowered_path == "/api/shifts":
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
    if "/shift-slots/" in lowered_path:
        return {
            "slot_id": "651d5e6f7a8b9c0d5e6f7a8b",
            "status": "in_progress",
            "checked_in_at": "2026-11-10T21:58:32Z",
            "confirmed_by_client": True,
        }

    if "invoice" in lowered_path:
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
    if lowered_path == "/api/billing/metadata":
        return {
            "provinces": ["ON", "BC", "AB", "QC"],
            "citiesByProvince": {
                "ON": ["TORONTO", "OTTAWA", "MISSISSAUGA", "HAMILTON"],
                "BC": ["VANCOUVER", "VICTORIA", "SURREY"],
            },
        }
    if lowered_path.startswith("/api/billing/"):
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

    if lowered_path == "/api/notifications/unread-count":
        return {"unread_count": 3}
    if lowered_path.startswith("/api/notifications"):
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

    if lowered_path == "/api/admin/platform-roles":
        return [
            {"value": "ops_admin", "label": "Ops Admin"},
            {"value": "support_admin", "label": "Support Admin"},
            {"value": "compliance_admin", "label": "Compliance Admin"},
            {"value": "read_only_admin", "label": "Read Only Admin"},
        ]
    if lowered_path.startswith("/api/admin/platform-users"):
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

    if lowered_method == "delete":
        return {"detail": "Resource deleted successfully"}
    return {"message": "Operation completed successfully", "status": "success"}


def model_fields(model_name):
    if model_name == "OAuth2PasswordRequestForm":
        return [("username", "str", True), ("password", "str", True), ("scope", "str", False)]
    return MODEL_FIELDS.get(model_name, [])


def collect_models():
    for source_file in ROOT.glob("backend/**/*.py"):
        try:
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            fields = []
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                name = statement.target.id
                if name.startswith("_") or name == "model_config":
                    continue
                type_name = annotation(statement.annotation)
                if type_name.startswith("ClassVar"):
                    continue
                required = statement.value is None
                if isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name):
                    if statement.value.func.id == "Field":
                        required = not any(keyword.arg in {"default", "default_factory"} for keyword in statement.value.keywords)
                fields.append((name, type_name or "string", required))
            if fields:
                MODEL_FIELDS[node.name] = fields


def make_doc(source_file, function, details, ordinal):
    method, path, values = details
    args = [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    defaults = [None] * (len(args) - len(function.args.defaults)) + list(function.args.defaults)
    parameters = []
    body_model = None
    for arg, default in zip(args, defaults):
        name = arg.arg
        type_name = annotation(arg.annotation)
        if name in {"self", "current_user", "request", "response", "_current_user", "file"}:
            continue
        if (
            "BaseModel" in type_name
            or type_name.endswith("Payload")
            or type_name.endswith("Request")
            or type_name == "OAuth2PasswordRequestForm"
            or type_name.startswith(("List[", "Dict[", "list[", "dict["))
        ):
            body_model = type_name
            continue
        required = default is None
        parameters.append((name, type_name or "string", required))

    summary = values.get("summary") or function.name.replace("_", " ").capitalize()
    description = values.get("description") or "No additional description has been provided."
    response_description = values.get("response_description") or "Successful response."
    status_code = values.get("status_code") or (201 if method == "POST" and (path.endswith("/signup") or path.endswith("/invite")) else 200)
    operation_id = values.get("operation_id") or function.name
    tags = values.get("tags") or []
    if not tags:
        file_stem = source_file.stem
        if "auth" in file_stem:
            tags = ["Authentication & Session"]
        elif "admin" in file_stem:
            tags = ["Platform Administration"]
        elif "tenant" in file_stem:
            tags = ["Tenant Management"]
        elif "billing" in file_stem:
            tags = ["Billing"]
        elif "notification" in file_stem:
            tags = ["Notifications"]
        elif "request_matching" in file_stem:
            tags = ["Request Matching"]
        elif "request" in file_stem:
            tags = ["Client Requests"]
        elif "public" in file_stem:
            tags = ["Public & System Metadata"]
    tag_str = ", ".join(tags) if tags else "General"

    auth = "Authentication is required unless this endpoint is explicitly documented as public."
    if path.startswith("/api/token") or path in {"/api/signup", "/api/forgot", "/api/updatePassword"} or path.startswith("/api/public"):
        auth = "Authentication is not required (Public endpoint)."

    resp_example = response_example_for(path, method)

    lines = [
        f"# {summary}",
        "",
        f"`{method} {path}`", "",
        description.strip(), "",
        "## At a glance", "",
        f"- **Operation ID:** `{operation_id}`",
        f"- **Tag / Domain:** `{tag_str}`",
        f"- **Source:** `{source_file.relative_to(ROOT)}` (`{function.name}`)",
        f"- **Success status:** `{status_code}`",
        f"- **Authentication:** {auth}",
        "",
    ]
    if parameters:
        lines += ["## Parameters", "", "| Name | Type | Required | Example |", "| --- | --- | --- | --- |"]
        for name, type_name, required in parameters:
            lines.append(f"| `{name}` | `{type_name}` | {'Yes' if required else 'No'} | `{sample_for(name, type_name)}` |")
        lines.append("")
    else:
        lines += ["## Parameters", "", "This endpoint does not define ordinary path, query, or form parameters.", ""]

    if body_model:
        fields = model_fields(body_model)
        if fields:
            body_json = ["{"]
            for index, (name, type_name, _) in enumerate(fields):
                comma = "," if index < len(fields) - 1 else ""
                body_json.append(f'  "{name}": {json_value(sample_for(name, type_name))}{comma}')
            body_json.append("}")
        else:
            body_json = ["{", '  "example_field": "example-value"', "}"]
        lines += [
            "## Request body", "",
            f"The request body is validated by `{body_model}`.", "",
            "```json", *body_json, "```", "",
            "> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.", "",
        ]
    else:
        lines += ["## Request body", "", "This endpoint does not declare a JSON request body.", ""]

    lines += [
        "## Response", "", response_description.strip(), "", "```json",
        *json.dumps(resp_example, indent=2).splitlines(), "```", "",
        "## Errors", "",
        "- `400 Bad Request` — input is invalid or a path identifier has the wrong format.",
        "- `401 Unauthorized` — authentication is missing, expired, or invalid.",
        "- `403 Forbidden` — the authenticated user does not have the required role or status.",
        "- `404 Not Found` — the requested resource does not exist.",
        "- `422 Unprocessable Entity` — FastAPI validation failed before the handler ran.",
        "",
        "## cURL", "",
        "```bash",
        f"curl -X {method} 'https://api.example.com{path}' \\",
        "  -H 'Accept: application/json' \\",
        "  -H 'Authorization: Bearer <access-token>'",
        "```", "",
        "## Notes", "",
        "Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.",
        "",
    ]
    return "\n".join(lines)


def main():
    collect_models()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for source_file in sorted(ROUTES_DIR.glob("*_routes.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for ordinal, decorator in enumerate(node.decorator_list, start=1):
                details = decorator_details(decorator)
                if not details:
                    continue
                method, path, _ = details
                filename = f"{source_file.stem.removesuffix('_routes')}-{method.lower()}-{clean_path(path)}-{node.name}-{ordinal}.md"
                (OUTPUT_DIR / filename).write_text(
                    make_doc(source_file, node, details, ordinal), encoding="utf-8"
                )
                written += 1
    index = [
        "# GuardGo API endpoint documentation", "",
        "This directory contains one Markdown reference file per registered FastAPI route operation.",
        "The files are generated from route decorators. Regenerate them after changing routes with:", "",
        "```bash", "python3 scripts/generate_api_docs.py", "```", "",
        f"Generated endpoint documents: **{written}**.", "",
    ]
    for file in sorted(OUTPUT_DIR.glob("*.md")):
        if file.name == "README.md":
            continue
        index.append(f"- [{file.stem}]({file.name})")
    (OUTPUT_DIR / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Generated {written} endpoint Markdown files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
