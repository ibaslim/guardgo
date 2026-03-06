from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model


async def migrate_tenant_pending_activation():
    engine = mongo_controller.get_instance().get_engine()
    collection = engine.get_collection(db_tenant_model)

    await collection.update_many(
        {"status": "pending_verification"},
        {"$set": {"status": "pending_activation"}}
    )

    await collection.update_many(
        {"approvals_required": {"$exists": False}},
        {"$set": {"approvals_required": 2}}
    )

    await collection.update_many(
        {"approval_actors": {"$exists": False}},
        {"$set": {"approval_actors": []}}
    )
