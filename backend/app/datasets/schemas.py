from pydantic import BaseModel


class DatasetCreate(BaseModel):
    resource_id: int
    name: str
    size: str = ""
    format: str = ""
    download_count: int = 0
    dataset_url: str | None = None
