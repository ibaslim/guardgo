import asyncio
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from interface import BASE_DIR
from orion.constants import constant
from orion.constants.constant import allowed_keys


class cronjob_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if cronjob_manager.__instance is None:
            cronjob_manager()
        return cronjob_manager.__instance

    def __init__(self):
        if cronjob_manager.__instance is not None:
            pass
        else:
            cronjob_manager.__instance = self
            self.build_assets()

    @staticmethod
    def build_assets():
        build_dir = BASE_DIR / "build"
        allowed_keys.clear()
        mail_templete_env = Environment(loader=FileSystemLoader(build_dir / "assets" / "data" / "mail_template_data"))
        constant.mail_template = mail_templete_env.get_template("mail_template.html")
        license_rules_env = Environment(loader=FileSystemLoader(build_dir / "assets" / "data" / "licenses"))
        license_rules_template = license_rules_env.get_template("license_rules.json")
        license_rules_json_str = license_rules_template.render()
        constant.license_rules = json.loads(license_rules_json_str)
        

   
