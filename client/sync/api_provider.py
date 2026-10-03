import hashlib
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Tuple, Optional, Dict

from common.models import LockStatus, SyncManifest
from client.sync.base import BaseSyncProvider


def calculate_file_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ApiSyncProvider(BaseSyncProvider):
    def __init__(self, server_url: str, token: str, local_save_dir: Path):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.local_save_dir = local_save_dir
        self._allowed_prefix: Optional[str] = None

    def _headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def get_server_config(self) -> str:
        """Obtiene el prefijo autorizado dinámicamente desde el servidor."""
        if self._allowed_prefix:
            return self._allowed_prefix

        req = urllib.request.Request(
            f"{self.server_url}/config",
            headers=self._headers(),
            method="GET"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self._allowed_prefix = data["allowed_prefix"]
            return self._allowed_prefix

    def acquire_lock(self, user: str) -> Tuple[bool, LockStatus]:
        req_data = json.dumps({"user": user}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.server_url}/lock/acquire",
            data=req_data,
            headers=self._headers("application/json"),
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return True, LockStatus(**data)
        except urllib.error.HTTPError as e:
            if e.code == 409:
                # Conflicto: partida ocupada
                body = json.loads(e.read().decode("utf-8"))
                locked_by = body.get("detail", "Otro jugador").replace("Partida bloqueada actualmente por: ", "")
                return False, LockStatus(is_locked=True, locked_by=locked_by, locked_at="activo")
            raise

    def release_lock(self, user: str) -> bool:
        req_data = json.dumps({"user": user}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.server_url}/lock/release",
            data=req_data,
            headers=self._headers("application/json"),
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return not data["is_locked"]
        except Exception:
            return False

    def pull_saves(self, pattern: Optional[str] = None) -> bool:
        """Descarga del servidor las partidas que no existen localmente o difieren en hash."""
        req = urllib.request.Request(
            f"{self.server_url}/saves/manifest",
            headers=self._headers(),
            method="GET"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                manifest_data = json.loads(resp.read().decode("utf-8"))
                manifest = SyncManifest(**manifest_data)
        except Exception as e:
            print(f"[ERROR] No se pudo obtener el manifiesto: {e}")
            return False

        for remote_file in manifest.saves:
            local_path = self.local_save_dir / remote_file.filename

            # Si ya existe con el mismo hash exacto, se salta la descarga
            if local_path.exists():
                local_sha = calculate_file_sha256(local_path)
                if local_sha == remote_file.sha256:
                    continue

            # Descarga binaria con reemplazo seguro
            temp_path = local_path.with_suffix(".tmp")
            down_req = urllib.request.Request(
                f"{self.server_url}/saves/download/{remote_file.filename}",
                headers=self._headers(),
                method="GET"
            )
            try:
                with urllib.request.urlopen(down_req) as d_resp, open(temp_path, "wb") as f_out:
                    while chunk := d_resp.read(65536):
                        f_out.write(chunk)
                temp_path.replace(local_path)
            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                print(f"[ERROR] Fallo al descargar {remote_file.filename}: {e}")
                return False

        return True

    def upload_single_file(self, file_path: Path) -> bool:
        """Sube un archivo individual mediante multipart/form-data."""
        boundary = "----WebKitFormBoundarySatisfactorySyncBoundary"
        c_type = f"multipart/form-data; boundary={boundary}"

        filename = file_path.name
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            f"{self.server_url}/saves/upload",
            data=body,
            headers=self._headers(c_type),
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[ERROR] Error al subir {filename}: {e}")
            return False

    def push_saves(self, pattern: Optional[str] = None) -> bool:
        """Sube todos los archivos locales que coincidan con el prefijo autorizado."""
        prefix = pattern or self.get_server_config()
        all_ok = True

        for file_path in self.local_save_dir.glob(f"{prefix}*.sav"):
            if file_path.is_file():
                success = self.upload_single_file(file_path)
                if not success:
                    all_ok = False

        return all_ok