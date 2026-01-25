"""
Migration: Move root-level tenant fields into typed profiles
Date: 2026-01-24
Description: Migrates legacy tenant documents by moving name, phone, city, postal_code, 
country, email from root level into the appropriate typed profile sub-object.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantType
from orion.services.encryption_manager.key_manager import KeyManager
from cryptography.fernet import Fernet
from datetime import datetime


async def migrate_tenants():
    """Migrate existing tenants to typed profile schema."""
    engine = mongo_controller.get_instance().get_engine()

    print("Starting tenant migration to typed profiles...")

    collection = engine.get_collection(db_tenant_model)
    tenants = await collection.find({}).to_list(length=None)
    total = len(tenants)
    migrated = 0
    skipped = 0

    print(f"Found {total} tenant(s) to process")

    for doc in tenants:
        tenant_id = doc.get("_id")
        tenant_type = TenantType.ADMIN if doc.get("is_default") else (doc.get("tenant_type") or TenantType.CLIENT)
        has_legacy_fields = any(doc.get(key) for key in ['name', 'phone', 'city', 'postal_code', 'country', 'email'])

        # Even if there are no legacy fields, ensure default tenant type is corrected.
        if not has_legacy_fields:
            if doc.get("is_default") and doc.get("tenant_type") != TenantType.ADMIN:
                await collection.update_one({"_id": tenant_id}, {"$set": {"tenant_type": TenantType.ADMIN}})
                print(f"  Tenant {tenant_id}: Set tenant_type to ADMIN (default tenant)")
            else:
                print(f"  Tenant {tenant_id}: Already migrated, skipping")
            skipped += 1
            continue

        print(f"  Tenant {tenant_id}: Migrating legacy fields...")

        dek = await KeyManager.get_instance().get_or_create_dek(str(tenant_id))
        enc = Fernet(dek)

        def _decrypt(val: str) -> str:
            if not val:
                return ""
            try:
                return enc.decrypt(val.encode()).decode()
            except Exception:
                return val

        legacy_data = {
            'name': _decrypt(doc.get('name', '')),
            'phone': _decrypt(doc.get('phone', '')),
            'city': _decrypt(doc.get('city', '')),
            'postal_code': _decrypt(doc.get('postal_code', '')),
            'country': _decrypt(doc.get('country', '')),
            'email': _decrypt(doc.get('email', '')),
        }

        existing_profile = doc.get('profile') or {}

        if tenant_type == TenantType.GUARD:
            profile = {
                'full_name': legacy_data.get('name', ''),
                'home_address': {
                    'street': '',
                    'city': legacy_data.get('city', ''),
                    'country': legacy_data.get('country', ''),
                    'postal_code': legacy_data.get('postal_code', ''),
                },
                **existing_profile
            }
        elif tenant_type == TenantType.CLIENT:
            profile = {
                'legal_entity_name': legacy_data.get('name', ''),
                'primary_contact': {
                    'name': legacy_data.get('name', ''),
                    'email': legacy_data.get('email', ''),
                    'phone': legacy_data.get('phone', ''),
                },
                'billing_address': {
                    'street': '',
                    'city': legacy_data.get('city', ''),
                    'country': legacy_data.get('country', ''),
                    'postal_code': legacy_data.get('postal_code', ''),
                },
                **existing_profile
            }
        elif tenant_type == TenantType.SERVICE_PROVIDER:
            profile = {
                'legal_company_name': legacy_data.get('name', ''),
                'company_phone': legacy_data.get('phone', ''),
                'company_email': legacy_data.get('email', ''),
                'head_office_address': {
                    'street': '',
                    'city': legacy_data.get('city', ''),
                    'country': legacy_data.get('country', ''),
                    'postal_code': legacy_data.get('postal_code', ''),
                },
                **existing_profile
            }
        else:
            profile = {
                'name': legacy_data.get('name', ''),
                'phone': legacy_data.get('phone', ''),
                'email': legacy_data.get('email', ''),
                'address': {
                    'city': legacy_data.get('city', ''),
                    'country': legacy_data.get('country', ''),
                    'postal_code': legacy_data.get('postal_code', ''),
                },
                **existing_profile
            }

        update_doc = {
            "$set": {
                "tenant_type": tenant_type,
                "profile": profile,
                "updated_at": datetime.utcnow(),
            },
            "$unset": {k: "" for k in ['name', 'phone', 'city', 'postal_code', 'country', 'email']},
        }

        await collection.update_one({"_id": tenant_id}, update_doc)
        migrated += 1
        print(f"    ✓ Migrated successfully (type: {tenant_type})")

    print(f"\nMigration complete:")
    print(f"  Total: {total}")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {total - migrated - skipped}")


if __name__ == "__main__":
    asyncio.run(migrate_tenants())
