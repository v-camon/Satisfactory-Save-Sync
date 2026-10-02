import sys
import os
import subprocess
import ctypes
from pathlib import Path

REAL_EXE_NAME = "FactoryGameSteam_real.exe"
LOCK_FILE_NAME = "session.lock"

# Constantes Win32
MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONERROR = 0x10
MB_ICONWARNING = 0x30
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
IDYES = 6

user32 = ctypes.windll.user32


def show_msg(title: str, message: str, flags: int) -> int:
    return user32.MessageBoxW(0, message, title, flags)


def show_timed_info(title: str, message: str, timeout_ms: int = 5000):
    try:
        user32.MessageBoxTimeoutW(
            0, message, title, MB_ICONINFORMATION | MB_OK, 0, timeout_ms
        )
    except Exception:
        import time

        time.sleep(timeout_ms / 1000)


def is_syncthing_running() -> bool:
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq syncthing.exe", "/NH"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            text=True,
        )
        return "syncthing.exe" in output.lower()
    except Exception:
        return True


def get_syncthing_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return Path.cwd()

    save_base = Path(local_app_data) / "FactoryGame" / "Saved" / "SaveGames"
    if save_base.exists():
        subdirs = [d for d in save_base.iterdir() if d.is_dir()]
        if subdirs:
            return subdirs[0]
        return save_base
    return Path.cwd()


def main():
    base_dir = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).parent
    )
    real_exe = base_dir / REAL_EXE_NAME

    # 1. Comprobar binario original renombrado
    if not real_exe.exists():
        show_msg(
            "Error de Lanzamiento",
            f"No se encuentra el binario oficial:\n{real_exe}\n\n"
            f"Asegúrate de renombrar el original a '{REAL_EXE_NAME}'.",
            MB_ICONERROR | MB_OK,
        )
        sys.exit(1)

    # 2. Comprobar ejecución de Syncthing
    if not is_syncthing_running():
        ans = show_msg(
            "Syncthing no detectado",
            "Syncthing NO parece estar ejecutándose.\n\n"
            "Si continúas, las partidas no se sincronizarán con los demás.\n"
            "¿Deseas lanzar el juego de todos modos?",
            MB_ICONWARNING | MB_YESNO,
        )
        if ans != IDYES:
            sys.exit(0)

    sync_dir = get_syncthing_dir()
    lock_file = sync_dir / LOCK_FILE_NAME
    current_user = os.environ.get("USERNAME", "Desconocido")
    should_manage_lock = True

    # 3. Comprobar lock activo de otro jugador
    if lock_file.exists():
        try:
            player_name = lock_file.read_text(encoding="utf-8").strip()
        except Exception:
            player_name = "Desconocido"

        if player_name != current_user:
            ans = show_msg(
                "Partida en uso",
                f"{player_name} está jugando a Satisfactory en este momento.\n\n"
                "- Pulsa 'No' para cancelar y esperar a que termine.\n"
                "- Pulsa 'Sí' si vas a jugar a OTRO save personal.\n\n"
                "¿Deseas lanzar el juego de todos modos?",
                MB_ICONQUESTION | MB_YESNO,
            )
            if ans != IDYES:
                sys.exit(0)
            should_manage_lock = False

    # 4. Adquirir lock y sincronizar durante 5 segundos
    if should_manage_lock:
        try:
            lock_file.write_text(current_user, encoding="utf-8")
        except Exception as e:
            show_msg(
                "Error", f"No se pudo escribir el lock:\n{e}", MB_ICONERROR | MB_OK
            )
            sys.exit(1)

        # Diálogo informativo con autocierre tras 5s
        show_timed_info(
            "Sincronizando Satisfactory",
            "Sincronizando partidas compartidas...\n"
            "Por favor, espera unos segundos antes de iniciar.",
            timeout_ms=5000,
        )

        # Mitigación de colisiones simultáneas
        try:
            owner = lock_file.read_text(encoding="utf-8").strip()
            if owner != current_user:
                ans = show_msg(
                    "Colisión detectada",
                    f"{owner} abrió el juego prácticamente al mismo tiempo.\n\n"
                    "¿Deseas cancelar para no sobreescribir la partida compartida?",
                    MB_ICONWARNING | MB_YESNO,
                )
                if ans == IDYES:
                    sys.exit(0)
                should_manage_lock = False
        except Exception:
            pass

    # 5. Lanzamiento del juego y reenvío de argumentos
    try:
        args = [str(real_exe)] + sys.argv[1:]
        process = subprocess.Popen(args, cwd=str(base_dir))
        process.wait()
    finally:
        # 6. Limpieza segura del lock al salir
        if should_manage_lock and lock_file.exists():
            try:
                if lock_file.read_text(encoding="utf-8").strip() == current_user:
                    lock_file.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
