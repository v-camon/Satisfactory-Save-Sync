from pydantic import BaseModel, Field, model_validator
from typing import Optional, List


class LockStatus(BaseModel):
    is_locked: bool = Field(..., description="Indica si hay una sesión activa")
    locked_by: Optional[str] = Field(
        None, description="Nombre de usuario que posee el lock"
    )
    locked_at: Optional[str] = Field(
        None, description="Timestamp ISO del momento de bloqueo"
    )

    @model_validator(mode="after")
    def validate_lock_owner(self):
        if self.is_locked:
            if not self.locked_by or not self.locked_by.strip():
                raise ValueError(
                    "Si is_locked es True, locked_by es estrictamente obligatorio."
                )
            if not self.locked_at:
                raise ValueError(
                    "Si is_locked es True, locked_at es estrictamente obligatorio."
                )
        else:
            # Si no está bloqueado, no debe tener dueño asociado
            self.locked_by = None
            self.locked_at = None
        return self


class LockRequest(BaseModel):
    user: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Nombre del usuario que solicita el lock",
    )


class SaveFileInfo(BaseModel):
    filename: str = Field(..., description="Nombre del archivo con extensión .sav")
    size_bytes: int = Field(..., ge=0, description="Tamaño del archivo en bytes")
    modified_time: float = Field(..., description="Timestamp de última modificación")
    sha256: str = Field(..., description="Hash SHA-256 del contenido")


class SyncManifest(BaseModel):
    saves: List[SaveFileInfo] = Field(
        default_factory=list, description="Lista de saves gestionados"
    )


class ServerConfig(BaseModel):
    allowed_prefix: str = Field(
        ..., description="Prefijo de los archivos de guardado compartidos"
    )
