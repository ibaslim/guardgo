import re
import traceback
import json
import html

from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_422_UNPROCESSABLE_ENTITY
from passlib.exc import PasswordSizeError
from starlette_admin.exceptions import FormValidationError

from configs import config
from orion.shared_models.expection_handlers.expection_handlers_models import ErrorResponseModel, ValidationErrorDetail, ValidationErrorResponseModel
from orion.helper_manager.env_handler import env_handler
from orion.services.mail_manager.mail_manager import mail_manager


REDACT_KEYS = {"password", "token", "authorization", "cookie", "secret", "api_key", "access_token", "refresh_token"}


def _mask_sensitive(value):
    if value is None:
        return None
    text = str(value)
    if len(text) <= 6:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def _redact_data(data):
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if any(marker in str(key).lower() for marker in REDACT_KEYS):
                redacted[key] = _mask_sensitive(value)
            else:
                redacted[key] = _redact_data(value)
        return redacted
    if isinstance(data, list):
        return [_redact_data(item) for item in data]
    return data


def _truncate(value, limit=4000):
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


async def _extract_request_payload(request: Request):
    try:
        body_bytes = await request.body()
    except Exception:
        body_bytes = b""

    if not body_bytes:
        return None

    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            data = json.loads(body_bytes.decode("utf-8"))
            return _redact_data(data)
        except Exception:
            pass

    try:
        text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = str(body_bytes)
    return _truncate(text)


def _alert_recipients():
    raw = env_handler.get_instance().env("ERROR_ALERT_RECIPIENTS", "")
    recipients = [item.strip() for item in str(raw).split(",") if item.strip()]
    if recipients:
        return recipients

    fallback = env_handler.get_instance().env("ACCOUNTS_MAIL", "")
    return [fallback] if fallback else []


async def _notify_internal_error(request: Request, exc: Exception):
    if config.DEBUG:
        return

    recipients = _alert_recipients()
    if not recipients:
        return

    request_payload = await _extract_request_payload(request)
    safe_query = _redact_data(dict(request.query_params))
    traceback_lines = clean_traceback(exc)[:30]
    headers_for_context = {
        "host": request.headers.get("host"),
        "content-type": request.headers.get("content-type"),
        "user-agent": request.headers.get("user-agent"),
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
    }

    context = {
        "method": request.method,
        "path": request.url.path,
        "url": str(request.url),
        "query": safe_query,
        "client": request.client.host if request.client else None,
        "headers": headers_for_context,
        "payload": request_payload,
        "error": str(exc),
        "traceback": traceback_lines,
    }

    pretty_context = _truncate(json.dumps(context, indent=2, ensure_ascii=True), limit=20000)
    subject = f"[GuardGo][PROD] 500 Error {request.method} {request.url.path}"
    body = (
        "<h3>GuardGo production exception alert</h3>"
        f"<p><strong>Path:</strong> {html.escape(request.url.path)}<br>"
        f"<strong>Method:</strong> {html.escape(request.method)}<br>"
        f"<strong>Error:</strong> {html.escape(str(exc))}</p>"
        f"<pre>{html.escape(pretty_context)}</pre>"
    )

    try:
        await mail_manager.get_instance().send_verification_mail_list(
            to_list=recipients,
            subject=subject,
            body=body,
        )
    except Exception as mail_exc:
        print(f"Failed to send 500 alert email: {mail_exc}")


def clean_traceback(exc: Exception):
    error_trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
    cleaned_trace = [re.sub(r"\s*\^+\s*", "", line.strip()) for line in error_trace if line.strip()]
    return cleaned_trace[::-1]


async def global_exception_handler(request: Request, exc: Exception):
    status_code = exc.status_code if isinstance(exc, HTTPException) else HTTP_500_INTERNAL_SERVER_ERROR

    if status_code >= HTTP_500_INTERNAL_SERVER_ERROR:
        await _notify_internal_error(request, exc)

    if config.DEBUG:
        error_response = ErrorResponseModel(
            error=str(exc), traceback=clean_traceback(exc))
        return JSONResponse(status_code=status_code, content=error_response.model_dump())

    return RedirectResponse(url=f"/{status_code}")


async def validation_exception_handler(_: Request, exc: RequestValidationError):
    if config.DEBUG:
        errors = [ValidationErrorDetail(
            field=".".join(str(loc) for loc in error["loc"][1:]), message=error["msg"], type=error["type"]) for error in
            exc.errors()]
        error_response = ValidationErrorResponseModel(
            validation_errors=errors, traceback=clean_traceback(exc))
        return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=error_response.model_dump())

    return RedirectResponse(url=f"/{HTTP_422_UNPROCESSABLE_ENTITY}")


async def password_size_exception_handler(_: Request, exc: PasswordSizeError):
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": "Password too long"})


async def value_error_exception_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})


async def form_validation_exception_handler(_: Request, exc: FormValidationError):
    return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.messages})
