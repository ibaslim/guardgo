import json
from pathlib import Path
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
    def build_assets():
        build_dir = BASE_DIR / "build"
        allowed_keys.clear()
        asset_data_dir = cronjob_manager._resolve_asset_data_dir(build_dir)
        mail_templete_env = Environment(loader=FileSystemLoader(asset_data_dir / "mail_template_data"))
        constant.mail_template = mail_templete_env.get_template("mail_template.html")
        license_rules_env = Environment(loader=FileSystemLoader(asset_data_dir / "licenses"))
        license_rules_template = license_rules_env.get_template("license_rules.json")
        license_rules_json_str = license_rules_template.render()
        constant.license_rules = json.loads(license_rules_json_str)


