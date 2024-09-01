from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from ao3_sync.api.enums import ItemType


@dataclass
class Bookmark:
    """
    Represents an AO3 bookmark

    Attributes:
        item_type (ItemType): Bookmark item type
        item_id (str): Bookmark item ID
    """

    id: str
    item_type: ItemType
    item_id: str


class ApiBookmarksHistory(BaseModel):
    date_bookmarked_last_bookmark: str | None = None
    date_updated_last_bookmark: str | None = None


class ApiHistory(BaseModel):
    """
    Represents an API history

    Attributes:
        last_bookmark_id (str): Last bookmark ID
        last_bookmark_item_type (ItemType): Last bookmark item type
    """

    updated_at: datetime | None = None
    bookmarks: ApiBookmarksHistory = ApiBookmarksHistory()
