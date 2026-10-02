import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.config import CURRENT_SAVES_DIR, BACKUPS_DIR, LOCK_FILE

client = TestClient(app)

TOKEN_MANCHAS = "token_manchas_demo"
HEADERS_AUTH = {"Authorization": f"Bearer {TOKEN_MANCHAS}"}


def setup_function():
    # Limpiar estado antes de cada test
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    for f in CURRENT_SAVES_DIR.glob("*.sav"):
        f.unlink()
    for f in BACKUPS_DIR.glob("*.sav"):
        f.unlink()


def test_auth_failure():
    # Sin header
    res = client.get("/lock/status")
    assert res.status_code == 401

    # Token inválido
    res = client.get("/lock/status", headers={"Authorization": "Bearer token_falso"})
    assert res.status_code == 401


def test_config_endpoint():
    res = client.get("/config", headers=HEADERS_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["allowed_prefix"] == "tacos_mecanicos_"


def test_lock_acquire_and_release():
    # 1. Adquirir lock para Manchas73 (dueño del token)
    res = client.post("/lock/acquire", headers=HEADERS_AUTH, json={"user": "Manchas73"})
    assert res.status_code == 200
    assert res.json()["is_locked"] is True
    assert res.json()["locked_by"] == "Manchas73"

    # 2. Intento de adquirir por otro usuario -> Conflicto (409)
    # Suponiendo que tuviéramos otro token; con el mismo token intentar usar otro user da 403
    res_fake = client.post("/lock/acquire", headers=HEADERS_AUTH, json={"user": "OtroUser"})
    assert res_fake.status_code == 403

    # 3. Liberar lock
    res_rel = client.post("/lock/release", headers=HEADERS_AUTH, json={"user": "Manchas73"})
    assert res_rel.status_code == 200
    assert res_rel.json()["is_locked"] is False


def test_save_upload_download_rotation():
    filename = "tacos_mecanicos_partida1.sav"
    content_v1 = b"DATOS_SAVE_V1"
    content_v2 = b"DATOS_SAVE_V2"

    # 1. Subir archivo inválido (prefijo erróneo)
    bad_file = io.BytesIO(b"hack")
    res_bad = client.post(
        "/saves/upload",
        headers=HEADERS_AUTH,
        files={"file": ("otra_partida.sav", bad_file, "application/octet-stream")},
    )
    assert res_bad.status_code == 400

    # 2. Subir V1
    file_v1 = io.BytesIO(content_v1)
    res_up1 = client.post(
        "/saves/upload",
        headers=HEADERS_AUTH,
        files={"file": (filename, file_v1, "application/octet-stream")},
    )
    assert res_up1.status_code == 200
    assert res_up1.json()["filename"] == filename

    # 3. Comprobar manifiesto
    res_man = client.get("/saves/manifest", headers=HEADERS_AUTH)
    assert res_man.status_code == 200
    saves = res_man.json()["saves"]
    assert len(saves) == 1
    assert saves[0]["filename"] == filename

    # 4. Subir V2 (debe crear backup de V1)
    file_v2 = io.BytesIO(content_v2)
    res_up2 = client.post(
        "/saves/upload",
        headers=HEADERS_AUTH,
        files={"file": (filename, file_v2, "application/octet-stream")},
    )
    assert res_up2.status_code == 200

    # Comprobar que existe backup generado
    backups = list(BACKUPS_DIR.glob(f"{Path(filename).stem}_*.sav"))
    assert len(backups) == 1

    # 5. Descargar versión actual
    res_down = client.get(f"/saves/download/{filename}", headers=HEADERS_AUTH)
    assert res_down.status_code == 200
    assert res_down.content == content_v2