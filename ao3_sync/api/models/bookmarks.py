from pydantic import BaseModel, Field

from ao3_sync.api.models.series import Series
from ao3_sync.api.models.works import Work


class Bookmark(BaseModel):
    """
    Represents an AO3 bookmark

    Attributes:
        id (str): Bookmark ID
        item (Work | Series): Bookmarked item
    """

    id: str
    item: Work | Series = Field(discriminator="item_type")
