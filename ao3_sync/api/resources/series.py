from typing import Any

import parsel
from tqdm import tqdm

from ao3_sync.api.enums import DEFAULT_DOWNLOAD_FORMATS, DownloadFormat


class SeriesApi:
    """
    API for handling AO3 series

    Args:
        client (AO3ApiClient): AO3ApiClient instance

    Attributes:
        URL_PATH (str): URL path for series
    """

    URL_PATH: str = "/series"

    def __init__(self, client):
        self._client = client

    def sync(self, series_id: str, formats: list[DownloadFormat] = DEFAULT_DOWNLOAD_FORMATS):
        """
        Syncs all the works in a series from AO3.

        Args:
            series_id (str): Series ID to sync
            formats (list[DownloadFormat]): Formats to download. Defaults to DEFAULT_DOWNLOAD_FORMATS
        """

        works = self.fetch_works(series_id)
        progress_bar = tqdm(total=len(works), desc=f"Series {series_id}", unit="work")
        for work_id in works:
            self._client.works.sync(work_id, formats=formats)
            progress_bar.update(1)
        progress_bar.close()

    def fetch_works(self, series_id: str) -> list[str]:
        """
        Fetches a series from AO3.

        Returns:
            works_list (list[str]): List of work IDs in the series
        """

        series_page: Any = self._client.get_or_fetch(f"{self.URL_PATH}/{series_id}")
        works_element_list = parsel.Selector(series_page).css("ul.series.work > li")

        works_list: list[str] = []
        for idx, work_el in enumerate(works_element_list, start=1):
            work_id = work_el.css("::attr(id)").get()
            if not work_id:
                self._client._debug_error(f"Skipping work {idx} as it has no ID")
                continue

            work_id = work_id.split("_")[-1]

            works_list.append(work_id)

        return works_list
