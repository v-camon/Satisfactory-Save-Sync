import time
import threading
from pathlib import Path
from typing import Dict
from client.sync.api_provider import ApiSyncProvider, calculate_file_sha256


class SaveWatcherDaemon:
    def __init__(self, provider: ApiSyncProvider, check_interval_seconds: float = 8.0):
        self.provider = provider
        self.interval = check_interval_seconds
        self.stop_event = threading.Event()
        self.thread: threading.Thread = None
        self._tracked_hashes: Dict[str, str] = {}

    def _is_file_ready(self, filepath: Path) -> bool:
        """Verifica que el archivo no esté bloqueado o escribiéndose por el juego."""
        try:
            size1 = filepath.stat().st_size
            time.sleep(0.4)
            size2 = filepath.stat().st_size
            if size1 != size2:
                return False
            # Intentar abrir en modo lectura/escritura exclusiva
            with open(filepath, "r+b"):
                pass
            return True
        except (OSError, PermissionError):
            return False

    def _scan_and_sync(self):
        prefix = self.provider.get_server_config()
        for file in self.provider.local_save_dir.glob(f"{prefix}*.sav"):
            if not file.is_file():
                continue

            if not self._is_file_ready(file):
                continue

            current_hash = calculate_file_sha256(file)
            last_hash = self._tracked_hashes.get(file.name)

            if current_hash != last_hash:
                print(f"[WATCHER] Modificación detectada en {file.name}. Subiendo...")
                if self.provider.upload_single_file(file):
                    self._tracked_hashes[file.name] = current_hash
                    print(f"[WATCHER] {file.name} sincronizado correctamente.")

    def _run(self):
        # Inicializar el estado de los hashes existentes para no re-subir lo recién descargado
        prefix = self.provider.get_server_config()
        for file in self.provider.local_save_dir.glob(f"{prefix}*.sav"):
            if file.is_file():
                self._tracked_hashes[file.name] = calculate_file_sha256(file)

        while not self.stop_event.is_set():
            try:
                self._scan_and_sync()
            except Exception as e:
                print(f"[WATCHER ERROR] Error en ciclo de vigilancia: {e}")
            self.stop_event.wait(self.interval)

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="SaveWatcherThread")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)