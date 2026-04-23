import asyncio
import sys
from pathlib import Path

# Add backend directory to import path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from orion.services.mongo_manager.mongo_controller import mongo_controller
from configs.metadata_constants import BILLING_REGION_CITY_OPTIONS
from orion.api.interactive.billing_manager.billing_manager import BillingManager


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


async def seed_guard_default_payrates() -> None:
    await mongo_controller.get_instance().link_connection()

    payload = []
    for location in BILLING_REGION_CITY_OPTIONS:
        code = location["region_code"]
        city_code = location["city_code"]
        rates = DUMMY_GUARD_RATES_CAD.get(code, {
            "standard_rate": 20.0,
            "weekend_rate": 22.0,
            "holiday_rate": 24.0,
        })
        payload.append({
            "region_code": code,
            "city_code": city_code,
            "standard_rate": rates["standard_rate"],
            "weekend_rate": rates["weekend_rate"],
            "holiday_rate": rates["holiday_rate"],
        })

    result = await BillingManager.get_instance().save_guard_rates(payload, current_user=None)
    print("Guard default payrate seeder completed")
    print(result)


if __name__ == "__main__":
    asyncio.run(seed_guard_default_payrates())
