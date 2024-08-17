from ao3_sync.api.enums import (
    DEFAULT_BOOKMARKS_SORT_OPTION,
    DEFAULT_DOWNLOAD_FORMATS,
    BookmarksSortOption,
    DownloadFormat,
)


def seralize_download_format(format_values: list[str] | None) -> list[DownloadFormat]:
    """
    Converts a list of strings to a list of DownloadFormat enums.

    Args:
        format_values (list[str]): List of format strings

    Returns:
        list[DownloadFormat]: List of DownloadFormat enums
    """

    if format_values is None:
        return DEFAULT_DOWNLOAD_FORMATS

    return [DownloadFormat(format) for format in format_values]


def seralize_sort_by(sort_by: str | None) -> BookmarksSortOption:
    """
    Converts a string to a BookmarksSortOption enum.

    Args:
        sort_by (str): Sort by string

    Returns:
        BookmarksSortOption: BookmarksSortOption enum
    """

    if sort_by is None:
        return DEFAULT_BOOKMARKS_SORT_OPTION

    return BookmarksSortOption(sort_by)
