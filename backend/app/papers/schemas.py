from pydantic import BaseModel


class PaperCreate(BaseModel):
    resource_id: int
    title: str
    authors: list[str] = []
    journal: str | None = None
    year: int | None = None
    doi: str | None = None
    pdf_url: str | None = None
    abstract: str = ""
