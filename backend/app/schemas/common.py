from pydantic import BaseModel


class CommentBody(BaseModel):
    comment: str | None = None

