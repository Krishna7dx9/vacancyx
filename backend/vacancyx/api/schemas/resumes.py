"""Resume upload and metadata response contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeRead(BaseModel):
    """Safe resume metadata; never expose a local filesystem path."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    original_filename: str
    media_type: str
    file_size_bytes: int
    checksum_sha256: str
    parse_status: str
    created_at: datetime
    updated_at: datetime
