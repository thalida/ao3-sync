from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DownloadFormat(Enum):
    """
    Enum for AO3 download formats

    Attributes:
        HTML (str): HTML
        EPUB (str): EPUB
        MOBI (str): MOBI
        PDF (str): PDF
        AZW3 (str): AZW3
    """

    HTML = "html"
    EPUB = "epub"
    MOBI = "mobi"
    PDF = "pdf"
    AZW3 = "azw3"


class ItemType(Enum):
    """
    Enum for AO3 item types

    Attributes:
        WORK (str): work
        SERIES (str): series
    """

    WORK = "work"
    SERIES = "series"


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


class Bookmark(BaseModel):
    """
    Represents an AO3 bookmark

    Attributes:
        id (str): Bookmark ID
        item (Work | Series): Bookmarked item
    """

    id: str
    item: Work | Series = Field(discriminator="item_type")
