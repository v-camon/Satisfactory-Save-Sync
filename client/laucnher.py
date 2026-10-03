import sys
import json
import subprocess
from pathlib import Path

from client.utils.paths import get_save_directory
from client.utils.ui import show_error, show_info, show_timed_info, ask_yes_no
from client.sync.api_provider import ApiSyncProvider
from client.sync.p2p_provider import P2PSyncProvider
from client.sync.watcher import SaveWatcherDaemon

REAL_EXE_NAME = "FactoryGameSteam_real.exe"
CONFIG_FILE_NAME = "config.json"


def load_config(base_dir: Path) -> dict:
    config_path = base_dir / CONFIG_FILE_NAME
    if not config_path.exists():
        show_error(
            "Configuración ausente",
            f"No se encontró '{CONFIG_FILE_NAME}' en:\n{base_dir}\n\n"
            "Crea el archivo con server_url, user y token."
        )
        sys.exit(1)

    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        show_error("Error de Configuración", f"JSON inválido en config.json:\n{e}")
        sys.exit(1)


def main():
    base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    real_exe = base_dir / REAL_EXE_NAME

    # 1. Validar existencia del binario original renombrado
    if not real_exe.exists():
        show_error(
            "Binario no encontrado",
            f"No se encuentra el binario oficial:\n{real_exe}\n\n"
            f"Renombra el ejecutable de Steam a '{REAL_EXE_NAME}'."
        )
        sys.exit(1)

    config = load_config(base_dir)
    user = config.get("user")
    mode = config.get("mode", "api")

    if not user:
        show_error("Configuración incompleta", "El campo 'user' es obligatorio en config.json.")
        sys.exit(1)

    local_save_dir = get_save_directory()

    # 2. Instanciar proveedor de sincronización
    watcher = None
    if mode == "api":
        server_url = config.get("server_url")
        token = config.get("token")
        if not server_url or not token:
            show_error("Error API", "'server_url' y 'token' son obligatorios en modo API.")
            sys.exit(1)
        provider = ApiSyncProvider(server_url=server_url, token=token, local_save_dir=local_save_dir)
    elif mode == "p2p":
        provider = P2PSyncProvider(local_save_dir=local_save_dir)
    else:
        show_error("Modo inválido", f"Modo desconocido en config.json: '{mode}'")
        sys.exit(1)

    # 3. Adquirir lock exclusivo
    should_manage_lock = True
    try:
        acquired, status = provider.acquire_lock(user=user)
    except Exception as e:
        proceed = ask_yes_no(
            "Fallo de conexión",
            f"No se pudo conectar con el servidor:\n{e}\n\n"
            "¿Deseas jugar en modo offline sin sincronización?"
        )
        if not proceed:
            sys.exit(0)
        acquired = False
        should_manage_lock = False

    if should_manage_lock and not acquired:
        owner = status.locked_by or "Desconocido"
        proceed = ask_yes_no(
            "Partida en uso",
            f"{owner} está jugando actualmente a la partida compartida.\n\n"
            "- Pulsa 'No' para cancelar y esperar a que termine.\n"
            "- Pulsa 'Sí' si vas a jugar a otra partida privada.\n\n"
            "¿Iniciar de todos modos?"
        )
        if not proceed:
            sys.exit(0)
        should_manage_lock = False

    # 4. Sincronización inicial (Pull) y arranque del Watcher
    if should_manage_lock:
        show_timed_info("Satisfactory Sync", "Descargando últimas partidas...", timeout_ms=3000)
        try:
            provider.pull_saves()
        except Exception as e:
            show_error("Error de descarga", f"Fallo al descargar saves: {e}")

        # Iniciar observador en caliente si estamos en modo API
        if isinstance(provider, ApiSyncProvider):
            watcher = SaveWatcherDaemon(provider=provider, check_interval_seconds=8.0)
            watcher.start()

    # 5. Ejecutar FactoryGameSteam_real.exe y esperar su cierre
    try:
        args = [str(real_exe)] + sys.argv[1:]
        process = subprocess.Popen(args, cwd=str(base_dir))
        process.wait()
    finally:
        # 6. Detener watcher, subida final exhaustiva (Push) y liberar lock
        if watcher:
            watcher.stop()

        if should_manage_lock:
            show_timed_info("Satisfactory Sync", "Subiendo guardado final...", timeout_ms=3000)
            try:
                provider.push_saves()
            except Exception as e:
                show_error("Aviso", f"Error en la subida final: {e}")

            try:
                provider.release_lock(user=user)
            except Exception:
                pass


if __name__ == "__main__":
    main()