import os
import uuid

from app.config import settings


def save_upload(data: bytes, filename: str, subdir: str) -> str:
    safe = filename.replace("/", "_").replace("\\", "_")
    d = os.path.join(settings.storage_dir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{uuid.uuid4().hex}_{safe}")
    with open(path, "wb") as f:
        f.write(data)
    return path
