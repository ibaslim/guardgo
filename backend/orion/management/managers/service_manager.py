import asyncio
import json
from asyncio import sleep
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from orion.api.server.config_manager.config_controller import config_controller
from orion.management.managers.cronjob_manager import cronjob_manager
from orion.management.managers.request_shift_maintenance_manager import request_shift_maintenance_manager
from orion.management.managers.test_manager import test_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.redis_manager.redis_controller import redis_controller
from orion.constants.constant import allowed_keys
from orion.constants import constant


class service_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if service_manager.__instance is None:
            service_manager()
        return service_manager.__instance

    def __init__(self):
        if service_manager.__instance is not None:
            return

        service_manager.__instance = self
        self._is_available = False

    async def init_services(self):
        await test_manager.get_instance().apply_test_overrides()

        while not self._is_available:
            try:
                await mongo_controller.get_instance().link_connection()
                await mongo_controller.get_instance().ensure_indexes()
                await mongo_controller.get_instance().initialize()

                await test_manager.get_instance().reset_test_mongo_and_import_mocks()

                await redis_controller.getInstance().initialize()
                await config_controller.getInstance().load_config()
                await asyncio.sleep(5)

                self._is_available = True
                return True
            except (OSError, ConnectionRefusedError):
                await asyncio.sleep(5)

        return False

    async def init_cronjobs(self):
        while not self._is_available:
            await sleep(5)
        await request_shift_maintenance_manager.get_instance().start()

    def check_status(self):
        return self._is_available

    @staticmethod
    def _resolve_asset_data_dir(build_dir: Path) -> Path:
        build_asset_data_dir = build_dir / "assets" / "data"
        if (
            (build_asset_data_dir / "mail_template_data" / "mail_template.html").exists()
            and (build_asset_data_dir / "licenses" / "license_rules.json").exists()
        ):
            return build_asset_data_dir

        fallback_asset_data_dir = build_dir.parent / "asset_data"
        if (
            (fallback_asset_data_dir / "mail_template_data" / "mail_template.html").exists()
            and (fallback_asset_data_dir / "licenses" / "license_rules.json").exists()
        ):
            return fallback_asset_data_dir

        raise FileNotFoundError(
            "Frontend asset data is missing from both the compiled build directory and the bundled fallback assets"
        )

    @staticmethod
    async def build_assets(build_dir):
        allowed_keys.clear()
        asset_data_dir = service_manager._resolve_asset_data_dir(build_dir)
        mail_templete_env = Environment(loader=FileSystemLoader(asset_data_dir / "mail_template_data"))
        constant.mail_template = mail_templete_env.get_template("mail_template.html")
        license_rules_env = Environment(loader=FileSystemLoader(asset_data_dir / "licenses"))
        license_rules_template = license_rules_env.get_template("license_rules.json")
        license_rules_json_str = license_rules_template.render()
        constant.license_rules = json.loads(license_rules_json_str)
