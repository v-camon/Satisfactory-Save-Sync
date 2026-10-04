import json
import shutil
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, status, Depends
from fastapi.responses import FileResponse

from common.models import (
    LockStatus,
    LockRequest,
    SyncManifest,
    SaveFileInfo,
    ServerConfig,
)
from server.config import CURRENT_SAVES_DIR, LOCK_FILE, USERS_FILE
from server.config import get_server_settings
from server.storage import get_manifest, save_uploaded_file


# Determinar si estamos en entorno de producción o desarrollo
# Si ENVIRONMENT no está definido o es 'production', ocultamos la documentación interactiva
IS_DEV = os.getenv("ENVIRONMENT", "production").lower() in ("development", "dev", "local")

app = FastAPI(
    title="Satisfactory Save Sync Server",
    description="Centralized synchronization backend with atomic locking for Satisfactory saves",
    version="1.0.1",
    docs_url="/docs" if IS_DEV else None,
    redoc_url="/redoc" if IS_DEV else None,
    openapi_url="/openapi.json" if IS_DEV else None,
)

current_lock = LockStatus(is_locked=False)


def load_lock_from_disk():
    global current_lock
    if LOCK_FILE.exists():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            current_lock = LockStatus(**data)
        except Exception:
            current_lock = LockStatus(is_locked=False)


def save_lock_to_disk():
    LOCK_FILE.write_text(current_lock.model_dump_json(indent=2), encoding="utf-8")


load_lock_from_disk()


def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Valida la cabecera 'Authorization: Bearer <token>' contra users.json."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cabecera Authorization Bearer ausente o malformada.",
        )

    token = authorization.split("Bearer ", 1)[1].strip()

    if not USERS_FILE.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Archivo de usuarios no configurado en el servidor.",
        )

    try:
        users_data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        tokens_map = users_data.get("tokens", {})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error leyendo archivo de usuarios en el servidor.",
        )

    username = tokens_map.get(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no válido o revocado.",
        )

    return username


# --- Endpoints de Bloqueo ---


@app.get("/lock/status", response_model=LockStatus)
def get_lock_status(auth_user: str = Depends(get_current_user)):
    return current_lock


@app.post("/lock/acquire", response_model=LockStatus)
def acquire_lock(payload: LockRequest, auth_user: str = Depends(get_current_user)):
    global current_lock

    # Garantizar que el usuario que pide el lock coincide con el dueño del token
    if payload.user != auth_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Identidad no autorizada: tu token pertenece a '{auth_user}', no a '{payload.user}'",
        )

    if current_lock.is_locked and current_lock.locked_by != auth_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Partida bloqueada actualmente por: {current_lock.locked_by}",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    current_lock = LockStatus(is_locked=True, locked_by=auth_user, locked_at=now_iso)
    save_lock_to_disk()
    return current_lock


@app.post("/lock/release", response_model=LockStatus)
def release_lock(payload: LockRequest, auth_user: str = Depends(get_current_user)):
    global current_lock

    if payload.user != auth_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No puedes liberar con la identidad de otro usuario.",
        )

    if not current_lock.is_locked:
        return current_lock

    if current_lock.locked_by != auth_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No puedes liberar el lock: pertenece a {current_lock.locked_by}",
        )

    current_lock = LockStatus(is_locked=False)
    save_lock_to_disk()
    return current_lock


# --- Endpoints de Archivos ---


@app.get("/saves/manifest", response_model=SyncManifest)
def list_saves(auth_user: str = Depends(get_current_user)):
    return get_manifest()


@app.get("/saves/download/{filename}")
def download_save(filename: str, auth_user: str = Depends(get_current_user)):
    prefix = get_server_settings().get("allowed_prefix", "tacos_mecanicos_")
    if not filename.startswith(prefix) or not filename.endswith(".sav"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se permiten archivos que comiencen por '{prefix}' y terminen en '.sav'",
        )

    file_path = CURRENT_SAVES_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="El archivo solicitado no existe.")

    return FileResponse(
        path=file_path, filename=filename, media_type="application/octet-stream"
    )


@app.post("/saves/upload", response_model=SaveFileInfo)
async def upload_save(
    file: UploadFile = File(...), auth_user: str = Depends(get_current_user)
):
    filename = file.filename
    prefix = get_server_settings().get("allowed_prefix", "tacos_mecanicos_")
    if not filename.startswith(prefix) or not filename.endswith(".sav"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se permiten archivos que comiencen por '{prefix}' y terminen en '.sav'",
        )

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        saved_info = save_uploaded_file(filename, tmp_path)
        return saved_info
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# --- Endpoints de Configuración ---


@app.get("/config", response_model=ServerConfig)
def get_config(auth_user: str = Depends(get_current_user)):
    settings = get_server_settings()
    return ServerConfig(
        allowed_prefix=settings.get("allowed_prefix", "tacos_mecanicos_")
    )
