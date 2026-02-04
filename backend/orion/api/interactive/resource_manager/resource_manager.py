from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse



class ResourceManager:
    __instance = None

    def __init__(self):
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.USER_DIR = self.BASE_DIR / "static" / "resource" / "profile"
        self.TENANT_DIR = self.BASE_DIR / "static" / "resource" / "tenant"
        self.TENANT_IDENTITY_DIR = self.BASE_DIR / "static" / "resource" / "tenant_identity"
        self.SYSTEM_DIR = self.BASE_DIR / "static" / "resource" / "system"
        self.ROBOTS_FILE = self.BASE_DIR / "static" / "robots.txt"

        self.USER_DIR.mkdir(parents=True, exist_ok=True)
        self.TENANT_DIR.mkdir(parents=True, exist_ok=True)
        self.TENANT_IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        self.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)

        if ResourceManager.__instance is not None:
            raise Exception("This class is a singleton!")
        ResourceManager.__instance = self

    @staticmethod
    def get_instance():
        if ResourceManager.__instance is None:
            ResourceManager.__instance = ResourceManager()
        return ResourceManager.__instance

    async def get_tenant_image(self, id):
        default_path = self.TENANT_DIR / "default.png"
        image_path = self.TENANT_DIR / f"{id}.png"
        return FileResponse(image_path if image_path.is_file() else default_path)

    async def uploadTenantImage(self, file: UploadFile, current_user):
        contents = await file.read()

        if len(contents) > 500 * 1024:
            raise HTTPException(status_code=400, detail="File too large! Maximum allowed size is 500 KB")

        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Invalid file type")

        file_path = self.TENANT_DIR / f"{current_user.tenant_uuid}.png"
        with open(file_path, "wb") as f:
            f.write(contents)

        return {"tenant_image": "upload complete"}

    async def get_user_image(self, user_id: str):
        default_path = self.USER_DIR / "default.png"
        image_path = self.USER_DIR / f"{user_id}.png"
        return FileResponse(image_path if image_path.is_file() else default_path)

    async def get_system_image(self, _: str):
        default_path = self.SYSTEM_DIR / "default.png"
        image_path = self.SYSTEM_DIR / f"{'logo'}.png"
        return FileResponse(image_path if image_path.is_file() else default_path)

    async def update_system_image(self, file: UploadFile, current_user):
        contents = await file.read()
        if current_user.role not in ["admin"]:
            return

        if len(contents) > 500 * 1024:
            raise HTTPException(status_code=400, detail="File too large! Maximum allowed size is 500 KB")

        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Invalid file type")

        file_path = self.SYSTEM_DIR / f"logo.png"
        with open(file_path, "wb") as f:
            f.write(contents)

    async def update_user_image(self, file: UploadFile, current_user):
        contents = await file.read()

        if len(contents) > 500 * 1024:
            raise HTTPException(status_code=400, detail="File too large! Maximum allowed size is 500 KB")

        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Invalid file type")

        file_path = self.USER_DIR / f"{current_user.id}.png"
        with open(file_path, "wb") as f:
            f.write(contents)

        return {"user_image": "upload complete"}

    async def delete_user_image(self, current_user):
        image_path = self.USER_DIR / f"{current_user.id}.png"

        if image_path.is_file():
            image_path.unlink()

        return {"user_image": "deleted"}

    async def delete_tenant_image(self, current_user):
        image_path = self.TENANT_DIR / f"{current_user.tenant_uuid}.png"

        if image_path.is_file():
            image_path.unlink()

        return {"tenant_image": "deleted"}

    async def upload_tenant_identity_document(self, file: UploadFile, current_user):
        contents = await file.read()

        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large! Maximum allowed size is 10 MB")

        if not (file.content_type.startswith("image/") or file.content_type == "application/pdf"):
            raise HTTPException(status_code=415, detail="Invalid file type")

        extension_map = {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
        }
        original_extension = Path(file.filename or "").suffix.lower()
        extension = extension_map.get(file.content_type, original_extension or ".bin")

        tenant_dir = self.TENANT_IDENTITY_DIR / f"{current_user.tenant_uuid}"
        tenant_dir.mkdir(parents=True, exist_ok=True)

        file_id = uuid4().hex
        stored_name = f"{file_id}{extension}"
        file_path = tenant_dir / stored_name

        with open(file_path, "wb") as f:
            f.write(contents)

        return {
            "file_id": file_id,
            "file_name": file.filename,
            "stored_name": stored_name,
            "mime_type": file.content_type,
            "size": len(contents),
            "file_url": f"/api/tenant/files/identity/{file_id}",
        }

    async def get_tenant_identity_document(self, file_id: str, current_user):
        tenant_dir = self.TENANT_IDENTITY_DIR / f"{current_user.tenant_uuid}"
        if not tenant_dir.exists():
            raise HTTPException(status_code=404, detail="File not found")

        matches = list(tenant_dir.glob(f"{file_id}.*"))
        if not matches:
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(matches[0])

    async def delete_tenant_identity_document(self, file_id: str, current_user):
        tenant_dir = self.TENANT_IDENTITY_DIR / f"{current_user.tenant_uuid}"
        if not tenant_dir.exists():
            raise HTTPException(status_code=404, detail="File not found")

        matches = list(tenant_dir.glob(f"{file_id}.*"))
        if not matches:
            raise HTTPException(status_code=404, detail="File not found")

        for file_path in matches:
            if file_path.is_file():
                file_path.unlink()

        return {"identity_document": "deleted"}

    async def delete_system_image(self, current_user):
        image_path = self.SYSTEM_DIR / f"logo.png"
        if current_user.role not in ["admin"]:
            return {"system_image deletion": "failed"}

        if image_path.is_file():
            image_path.unlink()

        return {"system_image": "deleted"}

    async def get_robots_txt(self):
        if not self.ROBOTS_FILE.is_file():
            raise HTTPException(status_code=404, detail="robots.txt not found")

        return FileResponse(
            self.ROBOTS_FILE,
            media_type="text/plain"
        )
