from typing import Literal

from pydantic import BaseModel

from ao3_sync.api.enums import ItemType


class Work(BaseModel):
    """
    Represents an AO3 work

    Attributes:
        item_type (ItemType): work
        id (str): Work ID
        title (str): Work title
        url (str): Work URL (computed)
    """

    item_type: Literal[ItemType.WORK] = ItemType.WORK
    id: str | None = None
    title: str | None = None
