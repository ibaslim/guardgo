import asyncio
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from configs.app_dependency import license_required, role_required, status_required
from configs.limiter_dependency import limiter_dependency
from orion.services.mongo_manager.shared_model.db_auth_models import (UserStatus, user_role, )

_DOCS_DIR = Path(__file__).resolve().parent / "docs" / "api_docs"


def _read_md(rel_path: str) -> str:
    p = _DOCS_DIR / rel_path
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Documentation file not found: {p}"


def _doc(rel_path: str) -> dict:
    text = _read_md(f"/app/docs/api_docs/{rel_path.lstrip('/')}")
    m = re.search(
        r"^##\s*Response Description\s*\n(.*?)(?:\n##\s|\Z)", text, flags=re.MULTILINE | re.DOTALL, )
    resp = "Success"
    if m:
        block = m.group(1).strip()
        if block:
            resp = block.splitlines()[0].strip() or "Success"
    return {"description": text, "response_description": resp}


SYSTEM_INFO_DOCS = {"directory": _doc("system-info/directory.md"), "dumps": _doc(
    "system-info/dumps.md"), "insight": _doc("system-info/insight.md"), }

REPORT_DOCS = {"defacement": _doc("reports/defacement.md"), "breach": _doc("reports/breach.md"), "news": _doc(
    "reports/news.md"), "exploit": _doc("reports/exploit.md"), "strategic": _doc("reports/strategic.md"), "chat": _doc(
    "reports/chat.md"), "social": _doc("reports/social.md"), "breach_screenshot": _doc(
    "reports/breach_screenshot.md"), "stix": _doc("reports/stix.md"), }

DYNAMIC_DOCS = {"dynamic_user_email": _doc("dynamic/dynamic_user_email.md"), "dynamic_cracked": _doc(
    "dynamic/dynamic_cracked.md"), "dynamic_software": _doc("dynamic/dynamic_software.md"), "dynamic_social": _doc(
    "dynamic/dynamic_social.md"), "domain_scan": _doc("dynamic/domain_scan.md"), }

SEARCH_DOCS = {"strategic": _doc("search/strategic.md"), "stealerlogs": _doc(
    "search/stealerlogs.md"), "consolidated": _doc("search/consolidated.md"), "consolidated_ranked": _doc(
    "search/consolidated_ranked.md"), "telegram": _doc("search/telegram.md"), "social": _doc(
    "search/social.md"), "breach": _doc("search/breach.md"), "exploit": _doc("search/exploit.md"), "defacement": _doc(
    "search/defacement.md"), }

api_routes = APIRouter(dependencies=[Depends(status_required([UserStatus.ACTIVE]))])







