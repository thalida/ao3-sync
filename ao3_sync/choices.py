from enum import Enum


class SYNC_TYPES(Enum):
    BOOKMARKS = "bookmarks"


SYNC_TYPES_VALUES = [e.value for e in SYNC_TYPES]
DEFAULT_SYNC_TYPE = SYNC_TYPES.BOOKMARKS.value
