import hashlib
import shutil
import time
from pathlib import Path
from typing import List
from common.models import SaveFileInfo, SyncManifest
from server.config import CURRENT_SAVES_DIR, BACKUPS_DIR, get_server_settings


def calculate_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_manifest() -> SyncManifest:
    settings = get_server_settings()
    prefix = settings.get("allowed_prefix", "tacos_mecanicos_")
    saves: List[SaveFileInfo] = []
    
    for file in CURRENT_SAVES_DIR.glob(f"{prefix}*.sav"):
        if file.is_file():
            stat = file.stat()
            saves.append(
                SaveFileInfo(
                    filename=file.name,
                    size_bytes=stat.st_size,
                    modified_time=stat.st_mtime,
                    sha256=calculate_sha256(file),
                )
            )
    return SyncManifest(saves=saves)


def backup_existing_save(target_file: Path):
    if not target_file.exists():
        return

    settings = get_server_settings()
    max_backups = settings.get("max_backups_per_file", 10)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = f"{target_file.stem}_{timestamp}{target_file.suffix}"
    backup_path = BACKUPS_DIR / backup_name
    shutil.copy2(target_file, backup_path)

    # Rotación: mantener solo los N backups más recientes del mismo archivo base
    pattern = f"{target_file.stem}_*{target_file.suffix}"
    existing_backups = sorted(
        BACKUPS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime
    )

    while len(existing_backups) > max_backups:
        oldest = existing_backups.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass


def save_uploaded_file(filename: str, source_path: Path) -> SaveFileInfo:
    target_path = CURRENT_SAVES_DIR / filename

    # 1. Crear copia de seguridad antes de sobreescribir
    backup_existing_save(target_path)

    # 2. Reemplazar archivo atómicamente
    shutil.move(str(source_path), str(target_path))

    stat = target_path.stat()
    return SaveFileInfo(
        filename=filename,
        size_bytes=stat.st_size,
        modified_time=stat.st_mtime,
        sha256=calculate_sha256(target_path),
    )