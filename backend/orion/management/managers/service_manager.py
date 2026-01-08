import asyncio
import json
from asyncio import sleep

from jinja2 import Environment, FileSystemLoader

from orion.api.server.config_manager.config_controller import config_controller
from orion.management.managers.cronjob_manager import cronjob_manager
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

    def check_status(self):
        return self._is_available

    @staticmethod
    async def build_assets(build_dir):
        allowed_keys.clear()
        mail_templete_env = Environment(loader=FileSystemLoader(build_dir / "assets" / "data" / "mail_template_data"))
        constant.mail_template = mail_templete_env.get_template("mail_template.html")
        license_rules_env = Environment(loader=FileSystemLoader(build_dir / "assets" / "data" / "licenses"))
        license_rules_template = license_rules_env.get_template("license_rules.json")
        license_rules_json_str = license_rules_template.render()
        constant.license_rules = json.loads(license_rules_json_str)
