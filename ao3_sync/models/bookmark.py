from pydantic import BaseModel


class Bookmark(BaseModel):
    title: str
