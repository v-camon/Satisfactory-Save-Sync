import os
from pathlib import Path
from typing import Optional


def get_save_directory() -> Path:
    """
    Localiza la carpeta concreta de partidas guardadas de Satisfactory en %LOCALAPPDATA%.
    Si hay una subcarpeta de SteamID, entra directamente en ella.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        raise RuntimeError("Variable de entorno LOCALAPPDATA no disponible.")

    save_base = Path(local_app_data) / "FactoryGame" / "Saved" / "SaveGames"

    if not save_base.exists():
        save_base.mkdir(parents=True, exist_ok=True)
        return save_base

    # Satisfactory suele crear una subcarpeta numérica con el SteamID/AccountID
    subdirs = [d for d in save_base.iterdir() if d.is_dir()]
    if subdirs:
        # Devuelve el subdirectorio de usuario más recientemente modificado
        subdirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return subdirs[0]

    return save_base