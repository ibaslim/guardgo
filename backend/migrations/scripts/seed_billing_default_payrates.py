import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

# Add backend directory to import path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from configs.metadata_constants import CANADIAN_PROVINCE_OPTIONS
from orion.api.interactive.billing_manager.billing_manager import BillingManager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_billing_model import BillingRate

AUTO_RUN = True


DUMMY_GUARD_RATES_CAD = {
    "AB": {"standard_rate": 22.0, "weekend_rate": 24.5, "holiday_rate": 27.0},
    "BC": {"standard_rate": 23.0, "weekend_rate": 25.5, "holiday_rate": 28.0},
    "MB": {"standard_rate": 21.0, "weekend_rate": 23.0, "holiday_rate": 25.5},
    "NB": {"standard_rate": 20.5, "weekend_rate": 22.5, "holiday_rate": 24.5},
    "NL": {"standard_rate": 21.5, "weekend_rate": 23.5, "holiday_rate": 26.0},
    "NS": {"standard_rate": 21.0, "weekend_rate": 23.0, "holiday_rate": 25.0},
    "NT": {"standard_rate": 26.0, "weekend_rate": 29.0, "holiday_rate": 32.0},
    "NU": {"standard_rate": 27.0, "weekend_rate": 30.0, "holiday_rate": 33.0},
    "ON": {"standard_rate": 23.5, "weekend_rate": 26.0, "holiday_rate": 29.0},
    "PE": {"standard_rate": 20.5, "weekend_rate": 22.5, "holiday_rate": 24.5},
    "QC": {"standard_rate": 22.5, "weekend_rate": 24.5, "holiday_rate": 27.5},
    "SK": {"standard_rate": 21.0, "weekend_rate": 23.5, "holiday_rate": 26.0},
    "YT": {"standard_rate": 25.0, "weekend_rate": 28.0, "holiday_rate": 31.0},
}

DUMMY_PROVIDER_RATES_CAD = {
    "AB": {"standard_rate": 31.0, "weekend_rate": 34.0, "holiday_rate": 38.0},
    "BC": {"standard_rate": 32.0, "weekend_rate": 35.0, "holiday_rate": 39.0},
    "MB": {"standard_rate": 29.5, "weekend_rate": 32.0, "holiday_rate": 35.5},
    "NB": {"standard_rate": 29.0, "weekend_rate": 31.5, "holiday_rate": 35.0},
    "NL": {"standard_rate": 30.0, "weekend_rate": 33.0, "holiday_rate": 36.5},
    "NS": {"standard_rate": 29.5, "weekend_rate": 32.0, "holiday_rate": 35.5},
    "NT": {"standard_rate": 37.0, "weekend_rate": 41.0, "holiday_rate": 45.0},
    "NU": {"standard_rate": 38.0, "weekend_rate": 42.0, "holiday_rate": 46.0},
    "ON": {"standard_rate": 33.0, "weekend_rate": 36.0, "holiday_rate": 40.0},
    "PE": {"standard_rate": 29.0, "weekend_rate": 31.5, "holiday_rate": 35.0},
    "QC": {"standard_rate": 31.5, "weekend_rate": 34.5, "holiday_rate": 38.5},
    "SK": {"standard_rate": 30.0, "weekend_rate": 33.0, "holiday_rate": 36.5},
    "YT": {"standard_rate": 36.0, "weekend_rate": 40.0, "holiday_rate": 44.0},
}


def _build_payload(rate_map: Dict[str, Dict[str, float]], fallback: Dict[str, float]) -> list[dict[str, Any]]:
    payload = []
    for region in CANADIAN_PROVINCE_OPTIONS:
        code = region["value"]
        rates = rate_map.get(code, fallback)
        payload.append({
            "region_code": code,
            "standard_rate": rates["standard_rate"],
            "weekend_rate": rates["weekend_rate"],
            "holiday_rate": rates["holiday_rate"],
        })
    return payload


async def seed_billing_default_payrates(force: bool = False) -> Dict[str, Any]:
    await mongo_controller.get_instance().link_connection()
    engine = mongo_controller.get_instance().get_engine()
    manager = BillingManager.get_instance()

    guard_count = await engine.count(BillingRate, BillingRate.scope == manager.SCOPE_GUARD_DEFAULT)
    provider_count = await engine.count(BillingRate, BillingRate.scope == manager.SCOPE_PROVIDER_DEFAULT)

    if not force and guard_count > 0 and provider_count > 0:
        return {
            "seeded": False,
            "reason": "already-seeded",
            "guard_default_rows": guard_count,
            "provider_default_rows": provider_count,
        }

    guard_payload = _build_payload(
        DUMMY_GUARD_RATES_CAD,
        {"standard_rate": 20.0, "weekend_rate": 22.0, "holiday_rate": 24.0},
    )
    provider_payload = _build_payload(
        DUMMY_PROVIDER_RATES_CAD,
        {"standard_rate": 30.0, "weekend_rate": 33.0, "holiday_rate": 36.0},
    )

    guard_result = await manager.save_guard_rates(guard_payload, current_user=None)
    provider_result = await manager.save_provider_default_rates(provider_payload, current_user=None)

    return {
        "seeded": True,
        "guard": guard_result,
        "provider": provider_result,
    }


async def run(force: bool = False) -> Dict[str, Any]:
    return await seed_billing_default_payrates(force=force)


async def _main(force: bool) -> None:
    result = await seed_billing_default_payrates(force=force)
    print("Billing default payrate seeder finished")
    print(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed billing default payrates for guards and service providers")
    parser.add_argument("--force", action="store_true", help="overwrite existing default rates")
    args = parser.parse_args()

    asyncio.run(_main(force=args.force))
