import os
import warnings
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import parsel
from pydantic import BaseModel
from tqdm import TqdmExperimentalWarning

from ao3_sync.api import AO3Api
from ao3_sync.enums import DownloadFormat, ItemType
from ao3_sync.utils import debug_log

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


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


class WorksAPI:
    URL_PATH: str = "/works"

    def __init__(self, client: AO3Api):
        self._client = client

    def sync(self, work: Work, formats: list[DownloadFormat] | Literal["all"] = "all"):
        """
        Syncs a work from AO3.

        Args:
            work (Work): Work to sync
        """

        download_links = self.fetch_download_links(work, formats)
        for link_path in download_links:
            self.download(work, link_path)

    def fetch_download_links(self, work: Work, formats: list[DownloadFormat] | Literal["all"] = "all"):
        """
        Fetches the download links for the given work.

        Args:
            work (Work): Work to fetch download links for

        Returns:
            download_links (list[str]): List of download links
        """
        work_url = f"{self.URL_PATH}/{work.id}"
        work_page = self._client.get_or_fetch(work_url)

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
        work: Work,
        download_url: str,
    ):
        """
        Downloads the work download files for the given work.

        Args:
            work (Work): Work to download
            formats (list[DownloadFormat] | Literal["all"]): Formats to download. Defaults to "all"
            progress_bar (tqdm | None): Progress bar to update
        """
        parsed_path = urlparse(download_url)
        filename = os.path.basename(parsed_path.path)
        ext = Path(filename).suffix
        debug_log(f"Downloading {ext} for work: {work.title}")
        content = self._client._download_file(download_url)
        self._client._save_downloaded_file(filename, content)

        debug_log("Downloaded work:", work.title)
