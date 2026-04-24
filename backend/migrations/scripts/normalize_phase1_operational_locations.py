import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantType
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager


async def normalize_phase1_operational_locations() -> None:
    await mongo_controller.get_instance().link_connection()
    engine = mongo_controller.get_instance().get_engine()

    tenants = await engine.find(
        db_tenant_model,
        (db_tenant_model.tenant_type == TenantType.GUARD)
        | (db_tenant_model.tenant_type == TenantType.SERVICE_PROVIDER),
    )

    scanned = 0
    updated = 0
    failed = 0

    for tenant in tenants:
        scanned += 1
        profile = tenant.profile if isinstance(tenant.profile, dict) else {}
        normalized_profile = dict(profile)

        try:
            normalized_profile = TenantManager._validate_and_normalize_profile_for_tenant_type(
                tenant.tenant_type,
                normalized_profile,
            )
        except Exception as ex:
            failed += 1
            print(f"[FAILED] tenant={tenant.id} type={tenant.tenant_type} reason={ex}")
            continue

        if normalized_profile != profile:
            tenant.profile = normalized_profile
            await engine.save(tenant)
            updated += 1

    print("Phase 1 operational location normalization complete")
    print(f"scanned={scanned} updated={updated} failed={failed}")


if __name__ == "__main__":
    asyncio.run(normalize_phase1_operational_locations())
