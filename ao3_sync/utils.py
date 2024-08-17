from ao3_sync.api.enums import DownloadFormat


def seralize_download_format(format_values: list[str] | None) -> list[DownloadFormat]:
    """
    Converts a list of strings to a list of DownloadFormat enums.

    Args:
        format_values (list[str]): List of format strings

    Returns:
        list[DownloadFormat]: List of DownloadFormat enums
    """

    if format_values is None:
        return [DownloadFormat.ALL]

    if DownloadFormat.ALL.value in format_values:
        return [DownloadFormat.ALL]

    return [DownloadFormat(format) for format in format_values]
