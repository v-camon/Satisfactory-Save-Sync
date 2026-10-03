# server/config.py
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CURRENT_SAVES_DIR = DATA_DIR / "current"
BACKUPS_DIR = DATA_DIR / "backups"
LOCK_FILE = DATA_DIR / "server_lock.json"
USERS_FILE = DATA_DIR / "users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

CURRENT_SAVES_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

# Plantilla de settings si no existe
if not SETTINGS_FILE.exists():
    SETTINGS_FILE.write_text(
        json.dumps(
            {"allowed_prefix": "tacos_mecanicos_", "max_backups_per_file": 10}, indent=2
        ),
        encoding="utf-8",
    )

# Plantilla de users con placeholders neutros
if not USERS_FILE.exists():
    USERS_FILE.write_text(
        json.dumps(
            {
                "tokens": {
                    "token_usuario_1": "PlayerOne",
                    "token_usuario_2": "PlayerTwo",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def get_server_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"allowed_prefix": "tacos_mecanicos_", "max_backups_per_file": 10}
