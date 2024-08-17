import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import parsel
from tqdm import tqdm

from ao3_sync.api.client import AO3ApiClient
from ao3_sync.api.enums import DownloadFormat

# warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


class WorksApi:
    """
    API for handling AO3 works

    Args:
        client (AO3ApiClient): AO3ApiClient instance

    Attributes:
        URL_PATH (str): URL path for works
    """

    URL_PATH: str = "/works"

    def __init__(self, client: AO3ApiClient):
        self._client = client

    def sync(self, work_id: str, formats: list[DownloadFormat] = [DownloadFormat.ALL]):
        """
        Syncs a work from AO3.

        Args:
            work_id (str): Work ID to sync
            formats (list[DownloadFormat]): Formats to download. Defaults to [DownloadFormat.ALL]
        """

        download_links = self.fetch_download_links(work_id, formats)
        progress_bar = tqdm(total=len(download_links), desc=f"Work {work_id}", unit="file")
        for link_path in download_links:
            self.download(work_id, link_path)
            progress_bar.update(1)
        progress_bar.close()

    def fetch_download_links(self, work_id: str, formats: list[DownloadFormat] = [DownloadFormat.ALL]) -> list[str]:
        """
        Fetches the download links for the given work.

        Args:
            work_id (str): Work ID to fetch download links for
            formats (list[DownloadFormat]): Formats to download. Defaults to [DownloadFormat.ALL]

        Returns:
            download_links (list[str]): List of download links
        """
        work_url = f"{self.URL_PATH}/{work_id}"
        work_page: Any = self._client.get_or_fetch(work_url)

        download_links = (
            parsel.Selector(work_page).css("#main ul.work.navigation li.download ul li a::attr(href)").getall()
        )

        filtered_links = []
        for link_path in download_links:
            parsed_path = urlparse(link_path)
            filename = os.path.basename(parsed_path.path)
            ext = Path(filename).suffix

            is_all = DownloadFormat.ALL in formats
            is_valid_format = ext[1:] in [format.value for format in formats]
            if is_all or is_valid_format:
                filtered_links.append(link_path)

        return filtered_links

    def download(
        self,
        work_id: str,
        download_url: str,
    ):
        """
        Downloads the work download files for the given work.

        Args:
            work_id (str): Work ID to download
            download_url (str): URL of the work download file
        """
        self._client._debug_log(f"Downloading {download_url} for work: {work_id}")
        self._client.download_file(download_url)
        self._client._debug_log("Downloaded work:", work_id)
