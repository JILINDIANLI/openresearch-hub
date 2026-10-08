from pydantic import BaseModel


class ModelCreate(BaseModel):
    resource_id: int
    framework: str = ""
    parameters: str = ""
    task: str = ""
    model_url: str | None = None
