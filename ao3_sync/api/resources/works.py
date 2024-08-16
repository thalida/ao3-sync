import os
import warnings
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import parsel
from tqdm import TqdmExperimentalWarning

from ao3_sync.api.client import AO3ApiClient
from ao3_sync.api.enums import DownloadFormat

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


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

    def sync(self, work_id: str, formats: list[DownloadFormat] | Literal["all"] = "all"):
        """
        Syncs a work from AO3.

        Args:
            work (Work): Work to sync
        """

        download_links = self.fetch_download_links(work_id, formats)
        for link_path in download_links:
            self.download(work_id, link_path)

    def fetch_download_links(self, work_id: str, formats: list[DownloadFormat] | Literal["all"] = "all"):
        """
        Fetches the download links for the given work.

        Args:
            work (Work): Work to fetch download links for

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

            if formats == "all" or "all" in formats or ext[1:] in formats:
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
            work (Work): Work to download
            download_url (str): URL of the work download file
        """
        parsed_path = urlparse(download_url)
        filename = os.path.basename(parsed_path.path)
        ext = Path(filename).suffix
        self._client._debug_log(f"Downloading {ext} for work: {work_id}")
        content = self._client._download_file(download_url)
        self._client._save_downloaded_file(filename, content)

        self._client._debug_log("Downloaded work:", work_id)
