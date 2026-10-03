import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional

from common.models import LockStatus
from client.sync.base import BaseSyncProvider

LOCK_FILE_NAME = "session.lock"


class P2PSyncProvider(BaseSyncProvider):
    def __init__(self, local_save_dir: Path):
        self.local_save_dir = local_save_dir
        self.lock_file = self.local_save_dir / LOCK_FILE_NAME

    def is_syncthing_running(self) -> bool:
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq syncthing.exe", "/NH"],
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                text=True
            )
            return "syncthing.exe" in output.lower()
        except Exception:
            return True

    def acquire_lock(self, user: str) -> Tuple[bool, LockStatus]:
        if self.lock_file.exists():
            try:
                owner = self.lock_file.read_text(encoding="utf-8").strip()
            except Exception:
                owner = "Desconocido"

            if owner != user:
                return False, LockStatus(is_locked=True, locked_by=owner, locked_at="p2p-session")

        try:
            self.lock_file.write_text(user, encoding="utf-8")
            return True, LockStatus(is_locked=True, locked_by=user, locked_at="p2p-session")
        except Exception:
            return False, LockStatus(is_locked=False)

    def release_lock(self, user: str) -> bool:
        if not self.lock_file.exists():
            return True

        try:
            owner = self.lock_file.read_text(encoding="utf-8").strip()
            if owner == user:
                self.lock_file.unlink()
                return True
            return False
        except Exception:
            return False

    def pull_saves(self, pattern: Optional[str] = None) -> bool:
        # En modo P2P puro, Syncthing sincroniza en background
        return self.is_syncthing_running()

    def push_saves(self, pattern: Optional[str] = None) -> bool:
        return self.is_syncthing_running()