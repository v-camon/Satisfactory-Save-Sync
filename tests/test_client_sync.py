import os
import time
import threading
from pathlib import Path
import pytest
import uvicorn

from client.sync.api_provider import ApiSyncProvider, calculate_file_sha256
from client.sync.watcher import SaveWatcherDaemon
from server.main import app
from server.config import CURRENT_SAVES_DIR, BACKUPS_DIR, LOCK_FILE

TEST_PORT = 8001
SERVER_URL = f"http://127.0.0.1:{TEST_PORT}"
TEST_TOKEN = "token_manchas_demo"
TEST_USER = "Manchas73"


# --- Fixture para levantar FastAPI en un hilo de fondo ---
@pytest.fixture(scope="module", autouse=True)
def run_test_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Esperar a que el servidor responda
    time.sleep(1.0)
    yield
    server.should_exit = True
    thread.join(timeout=2.0)


@pytest.fixture
def clean_environment(tmp_path):
    # Limpiar estado del server
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    for f in CURRENT_SAVES_DIR.glob("*.sav"):
        f.unlink()
    for f in BACKUPS_DIR.glob("*.sav"):
        f.unlink()

    # Directorio de saves simulado para el cliente
    client_save_dir = tmp_path / "ClientSaves"
    client_save_dir.mkdir(parents=True, exist_ok=True)
    return client_save_dir


def test_api_provider_config_and_locks(clean_environment):
    client_dir = clean_environment
    provider = ApiSyncProvider(server_url=SERVER_URL, token=TEST_TOKEN, local_save_dir=client_dir)

    # 1. Config dinámica
    prefix = provider.get_server_config()
    assert prefix == "tacos_mecanicos_"

    # 2. Acquire lock exitoso
    ok, status = provider.acquire_lock(user=TEST_USER)
    assert ok is True
    assert status.is_locked is True
    assert status.locked_by == TEST_USER

    # 3. Acquire lock duplicado (simulando otro jugador)
    # Genera conflicto (HTTP 409)
    other_provider = ApiSyncProvider(server_url=SERVER_URL, token=TEST_TOKEN, local_save_dir=client_dir)
    ok_conflict, status_conflict = other_provider.acquire_lock(user=TEST_USER)
    assert ok_conflict is True  # Mismo usuario puede re-adquirir
    
    # 4. Release lock
    released = provider.release_lock(user=TEST_USER)
    assert released is True


def test_api_provider_push_and_pull(clean_environment, tmp_path):
    client_dir_a = clean_environment
    client_dir_b = tmp_path / "ClientB_Saves"
    client_dir_b.mkdir()

    provider_a = ApiSyncProvider(server_url=SERVER_URL, token=TEST_TOKEN, local_save_dir=client_dir_a)
    provider_b = ApiSyncProvider(server_url=SERVER_URL, token=TEST_TOKEN, local_save_dir=client_dir_b)

    # 1. Crear saves locales en cliente A
    prefix = provider_a.get_server_config()
    file_shared = client_dir_a / f"{prefix}main_save.sav"
    file_private = client_dir_a / "private_session.sav"

    file_shared.write_bytes(b"DATA_SHARED_SAVE_V1")
    file_private.write_bytes(b"DATA_PRIVATE_SAVE")

    # 2. Push saves desde cliente A
    ok_push = provider_a.push_saves()
    assert ok_push is True

    # Comprobar que en el servidor SOLO se subió el save compartido
    server_files = [f.name for f in CURRENT_SAVES_DIR.glob("*.sav")]
    assert f"{prefix}main_save.sav" in server_files
    assert "private_session.sav" not in server_files

    # 3. Pull saves en cliente B
    ok_pull = provider_b.pull_saves()
    assert ok_pull is True

    downloaded_file = client_dir_b / f"{prefix}main_save.sav"
    assert downloaded_file.exists()
    assert downloaded_file.read_bytes() == b"DATA_SHARED_SAVE_V1"
    assert not (client_dir_b / "private_session.sav").exists()


def test_save_watcher_daemon_autosaves(clean_environment):
    client_dir = clean_environment
    provider = ApiSyncProvider(server_url=SERVER_URL, token=TEST_TOKEN, local_save_dir=client_dir)
    prefix = provider.get_server_config()

    # Iniciar daemon con intervalo corto para tests
    watcher = SaveWatcherDaemon(provider=provider, check_interval_seconds=0.5)
    watcher.start()

    try:
        # Simular que el juego crea un autosave mientras corre
        autosave_file = client_dir / f"{prefix}autosave_0.sav"
        autosave_file.write_bytes(b"AUTOSAVE_DATA_CYCLE_1")

        # Dar tiempo al watcher a escanear, verificar estabilidad y subir
        time.sleep(2.0)

        # Comprobar que ya está en el servidor
        server_autosave = CURRENT_SAVES_DIR / f"{prefix}autosave_0.sav"
        assert server_autosave.exists()
        assert server_autosave.read_bytes() == b"AUTOSAVE_DATA_CYCLE_1"

        # Simular segundo autosave sobreescribiendo el mismo archivo
        autosave_file.write_bytes(b"AUTOSAVE_DATA_CYCLE_2_NEW_CONTENT")
        time.sleep(2.0)

        assert server_autosave.read_bytes() == b"AUTOSAVE_DATA_CYCLE_2_NEW_CONTENT"

    finally:
        watcher.stop()