from pydantic import BaseModel, computed_field


class ObjectTypes:
    """
    Enum for AO3 object types

    Attributes:
        WORK (str): Work object type. Value is "works"
        SERIES (str): Series object type. Value is "series"
    """

    WORK = "works"
    SERIES = "series"


class Work(BaseModel):
    """
    Represents an AO3 work

    Attributes:
        type (ObjectTypes): works
        id (str): Work ID
        title (str): Work title
        url (str): Work URL (computed)
    """

    type: str = ObjectTypes.WORK
    id: str | None = None
    title: str | None = None

    @computed_field
    @property
    def url(self) -> str:
        return f"/{self.type}/{self.id}"


class Series(BaseModel):
    """
    Represents an AO3 series

    Attributes:
        type (ObjectTypes): series
        id (str): Series ID
        title (str): Series title
        url (str): Series URL (computed)
    """

    type: str = ObjectTypes.SERIES
    id: str | None = None
    title: str | None = None

    @computed_field
    @property
    def url(self) -> str:
        return f"/{self.type}/{self.id}"


class Bookmark(BaseModel):
    """
    Represents an AO3 bookmark

    Attributes:
        id (str): Bookmark ID
        object (Work | Series): Bookmark object
    """

    id: str
    object: Work | Series
