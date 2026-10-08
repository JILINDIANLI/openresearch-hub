from pydantic import BaseModel


class ProjectCreate(BaseModel):
    resource_id: int
    leader: str = ""
    members: list[str] = []
    status: str = "published"
    github_url: str | None = None
    paper_url: str | None = None
    demo_url: str | None = None
