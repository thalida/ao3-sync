from dataclasses import dataclass

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
