import argparse
import asyncio
import json

from orion.services.mongo_manager.mongo_controller import mongo_controller
from migrations.seeder_manager import seeder_manager


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run project seeders")
    parser.add_argument("--list", action="store_true", help="list available seeders")
    parser.add_argument("--auto", action="store_true", help="run only AUTO_RUN seeders")
    parser.add_argument("--seeder", type=str, help="run one specific seeder module name")
    parser.add_argument("--force", action="store_true", help="force rerun / overwrite when supported")
    args = parser.parse_args()

    manager = seeder_manager.get_instance()

    if args.list:
        print(json.dumps(manager.list_seeders(), indent=2))
        return

    await mongo_controller.get_instance().link_connection()

    if args.auto:
        result = await manager.run_auto_seeders(force=args.force)
        print(json.dumps(result, indent=2, default=str))
        return

    if args.seeder:
        result = await manager.run_seeder(args.seeder, force=args.force)
        print(json.dumps({args.seeder: result}, indent=2, default=str))
        return

    # Default behavior: run auto seeders.
    result = await manager.run_auto_seeders(force=args.force)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
