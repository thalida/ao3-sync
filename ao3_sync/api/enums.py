from enum import Enum


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


DEFAULT_DOWNLOAD_FORMATS = [
    DownloadFormat.HTML,
    DownloadFormat.EPUB,
    DownloadFormat.MOBI,
    DownloadFormat.PDF,
    DownloadFormat.AZW3,
]

DEFAULT_DOWNLOAD_FORMATS_VALUES = [format.value for format in DEFAULT_DOWNLOAD_FORMATS]


class ItemType(Enum):
    """
    Enum for AO3 item types

    Attributes:
        WORK (str): work
        SERIES (str): series
    """

    WORK = "work"
    SERIES = "series"


class BookmarksSortOption(Enum):
    DATE_BOOKMARKED = "date-bookmarked"
    DATE_UPDATED = "date-updated"


DEFAULT_BOOKMARKS_SORT_OPTION = BookmarksSortOption.DATE_BOOKMARKED
DEFAULT_BOOKMARKS_SORT_OPTION_VALUE = DEFAULT_BOOKMARKS_SORT_OPTION.value

BOOKMARKS_SORT_QUERY_PARAM = {
    BookmarksSortOption.DATE_BOOKMARKED: "created_at",
    BookmarksSortOption.DATE_UPDATED: "bookmarkable_date",
}
