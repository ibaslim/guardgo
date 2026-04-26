import asyncio
import sys
from pathlib import Path

# Add backend directory to import path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from orion.services.mongo_manager.mongo_controller import mongo_controller
from configs.metadata_constants import BILLING_REGION_CITY_OPTIONS
from orion.api.interactive.billing_manager.billing_manager import BillingManager


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


async def seed_provider_default_payrates() -> None:
    await mongo_controller.get_instance().link_connection()

    payload = []
    for location in BILLING_REGION_CITY_OPTIONS:
        code = location["region_code"]
        city_code = location["city_code"]
        rates = DUMMY_PROVIDER_RATES_CAD.get(code, {
            "standard_rate": 30.0,
            "weekend_rate": 33.0,
            "holiday_rate": 36.0,
        })
        payload.append({
            "region_code": code,
            "city_code": city_code,
            "standard_rate": rates["standard_rate"],
            "weekend_rate": rates["weekend_rate"],
            "holiday_rate": rates["holiday_rate"],
        })

    result = await BillingManager.get_instance().save_provider_default_rates(payload, current_user=None)
    print("Service provider default payrate seeder completed")
    print(result)


if __name__ == "__main__":
    asyncio.run(seed_provider_default_payrates())
