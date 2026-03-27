import asyncio
import sys
from pathlib import Path

# Add backend directory to import path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from configs.metadata_constants import CANADIAN_PROVINCE_OPTIONS
from orion.api.interactive.billing_manager.billing_manager import BillingManager
from orion.services.mongo_manager.mongo_controller import mongo_controller


DUMMY_PROVIDER_COMMISSION_RATES_CAD = {
    "AB": {"standard_rate": 3.0, "weekend_rate": 3.5, "holiday_rate": 4.0},
    "BC": {"standard_rate": 3.5, "weekend_rate": 4.0, "holiday_rate": 4.5},
    "MB": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "NB": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "NL": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "NS": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "NT": {"standard_rate": 4.0, "weekend_rate": 4.5, "holiday_rate": 5.0},
    "NU": {"standard_rate": 4.5, "weekend_rate": 5.0, "holiday_rate": 5.5},
    "ON": {"standard_rate": 3.5, "weekend_rate": 4.0, "holiday_rate": 4.5},
    "PE": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "QC": {"standard_rate": 3.0, "weekend_rate": 3.5, "holiday_rate": 4.0},
    "SK": {"standard_rate": 2.5, "weekend_rate": 3.0, "holiday_rate": 3.5},
    "YT": {"standard_rate": 4.0, "weekend_rate": 4.5, "holiday_rate": 5.0},
}


async def seed_provider_commission_default_rates() -> None:
    await mongo_controller.get_instance().link_connection()

    payload = []
    for region in CANADIAN_PROVINCE_OPTIONS:
        code = region["value"]
        rates = DUMMY_PROVIDER_COMMISSION_RATES_CAD.get(code, {
            "standard_rate": 3.0,
            "weekend_rate": 3.5,
            "holiday_rate": 4.0,
        })
        payload.append({
            "region_code": code,
            "standard_rate": rates["standard_rate"],
            "weekend_rate": rates["weekend_rate"],
            "holiday_rate": rates["holiday_rate"],
        })

    result = await BillingManager.get_instance().save_provider_commission_rates(payload, current_user=None)
    print("Provider commission default rate seeder completed")
    print(result)


if __name__ == "__main__":
    asyncio.run(seed_provider_commission_default_rates())