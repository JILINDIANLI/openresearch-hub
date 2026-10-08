from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


FILE_KINDS = {"MODEL_WEIGHT", "DATASET", "PAPER", "CODE", "IMAGE", "VIDEO", "DOCUMENT", "CONFIG", "RESULT", "OTHER"}


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    version_id: int | None = None
    original_filename: str
    file_kind: str
    mime_type: str
    file_extension: str
    file_size: int
    sha256: str
    description: str | None = None
    download_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    uploader: dict = Field(default_factory=dict)
    can_preview: bool = False
    download_url: str
    preview_url: str | None = None
