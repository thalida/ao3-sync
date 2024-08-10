from pydantic import BaseModel, computed_field


class ObjectTypes:
    WORK = "works"
    SERIES = "series"


class Work(BaseModel):
    type: str = ObjectTypes.WORK
    id: str | None = None
    title: str | None = None

    @computed_field
    @property
    def url(self) -> str:
        return f"https://archiveofourown.org/{self.type}/{self.id}"


class Series(BaseModel):
    type: str = ObjectTypes.SERIES
    id: str | None = None
    title: str | None = None

    @computed_field
    @property
    def url(self) -> str:
        return f"https://archiveofourown.org/{self.type}/{self.id}"


class Bookmark(BaseModel):
    id: str
    object: Work | Series
