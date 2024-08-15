from typing import Literal

from pydantic import BaseModel

from ao3_sync.api.enums import ItemType


class Series(BaseModel):
    """
    Represents an AO3 series

    Attributes:
        item_type (ItemType): series
        id (str): Series ID
        title (str): Series title
        url (str): Series URL (computed)
    """

    item_type: Literal[ItemType.SERIES] = ItemType.SERIES
    id: str | None = None
    title: str | None = None
