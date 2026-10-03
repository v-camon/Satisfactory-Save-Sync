from abc import ABC, abstractmethod
from typing import Tuple
from common.models import LockStatus, SyncManifest


class BaseSyncProvider(ABC):
    """
    Contrato obligatorio para cualquier proveedor de sincronización (API REST, P2P, etc.)
    """

    @abstractmethod
    def acquire_lock(self, user: str) -> Tuple[bool, LockStatus]:
        """
        Intenta adquirir el lock para 'user'.
        Retorna (True, status) si se obtuvo con éxito.
        Retorna (False, status) si ya estaba ocupado o hubo error.
        """
        pass

    @abstractmethod
    def release_lock(self, user: str) -> bool:
        """
        Libera el lock si pertenece a 'user'.
        Retorna True si se liberó correctamente.
        """
        pass

    @abstractmethod
    def pull_saves(self, pattern: str) -> bool:
        """
        Descarga o actualiza localmente los archivos que coincidan con 'pattern'
        (ej: 'tacos_mecanicos_*.sav') solo si la versión remota es más reciente o difiere en hash.
        Retorna True si la operación se completó sin errores.
        """
        pass

    @abstractmethod
    def push_saves(self, pattern: str) -> bool:
        """
        Detecta saves locales que coincidan con 'pattern' y los sube/propaga.
        Retorna True si la subida fue exitosa.
        """
        pass
