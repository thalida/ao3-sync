from enum import Enum


class DownloadFormat(Enum):
    """
    Enum for AO3 download formats

    Attributes:
        ALL (str): all

        HTML (str): HTML
        EPUB (str): EPUB
        MOBI (str): MOBI
        PDF (str): PDF
        AZW3 (str): AZW3
    """

    ALL = "all"

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
