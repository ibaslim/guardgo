import importlib
import inspect
import os
from typing import Any, Dict, List, Tuple


class seeder_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if seeder_manager.__instance is None:
            seeder_manager.__instance = seeder_manager()
        return seeder_manager.__instance

    def __init__(self):
        if seeder_manager.__instance is not None:
            raise Exception("This class is a singleton! Use get_instance() instead.")
        seeder_manager.__instance = self
        self.script_dir = os.path.join(os.path.dirname(__file__), "scripts")

    def _discover_seeders(self) -> List[Tuple[str, Any]]:
        if not os.path.exists(self.script_dir):
            return []

        seeder_files = [
            f for f in os.listdir(self.script_dir)
            if f.startswith("seed_") and f.endswith(".py")
        ]
        seeder_files.sort()

        modules: List[Tuple[str, Any]] = []
        for file_name in seeder_files:
            module_name = file_name.replace(".py", "")
            full_module = f"migrations.scripts.{module_name}"
            module = importlib.import_module(full_module)
            modules.append((module_name, module))

        return modules

    @staticmethod
    async def _invoke_module(module: Any, force: bool = False) -> Dict[str, Any]:
        if not hasattr(module, "run"):
            return {"executed": False, "reason": "no-run-entrypoint"}

        run_fn = getattr(module, "run")
        signature = inspect.signature(run_fn)

        if "force" in signature.parameters:
            result = run_fn(force=force)
        else:
            result = run_fn()

        if inspect.isawaitable(result):
            result = await result

        return {"executed": True, "result": result}

    async def run_auto_seeders(self, force: bool = False) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for module_name, module in self._discover_seeders():
            auto_run = bool(getattr(module, "AUTO_RUN", False))
            if not auto_run:
                continue
            results[module_name] = await self._invoke_module(module, force=force)
        return results

    async def run_seeder(self, seeder_module_name: str, force: bool = False) -> Dict[str, Any]:
        target = seeder_module_name.replace(".py", "")
        for module_name, module in self._discover_seeders():
            if module_name == target:
                return await self._invoke_module(module, force=force)
        raise ValueError(f"Seeder not found: {seeder_module_name}")

    def list_seeders(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for module_name, module in self._discover_seeders():
            items.append({
                "name": module_name,
                "auto_run": bool(getattr(module, "AUTO_RUN", False)),
                "has_run_entrypoint": hasattr(module, "run"),
            })
        return items
