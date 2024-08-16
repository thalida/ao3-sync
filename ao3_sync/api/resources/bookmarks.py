import warnings
from typing import Any, Literal

import parsel
from tqdm import TqdmExperimentalWarning
from tqdm.rich import tqdm
from yaspin import yaspin

import ao3_sync.api.exceptions
from ao3_sync.api.client import AO3ApiClient
from ao3_sync.api.enums import DownloadFormat, ItemType
from ao3_sync.api.models import Bookmark

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


class BookmarksApi:
    """
    API for handling AO3 bookmarks

    Args:
        client (AO3ApiClient): AO3ApiClient instance

    Attributes:
        URL_PATH (str): URL path for bookmarks
    """

    URL_PATH: str = "/bookmarks"

    def __init__(self, client: AO3ApiClient):
        self._client = client

    def sync(
        self,
        start_page=1,
        end_page=None,
        query_params=None,
        formats: list[DownloadFormat] | Literal["all"] = "all",
    ):
        """
        Downloads the user's bookmarks from AO3.

        Args:
            start_page (int): Starting page of bookmarks to download. Defaults to 1
            end_page (int): Ending page of bookmarks to download. Defaults to None
            query_params (dict): Query parameters for bookmarks
            formats (list[DownloadFormat] | Literal["all"]): Formats to download. Defaults to "all"
        """
        bookmarks = self.fetch_pages(
            start_page=start_page,
            end_page=end_page,
            query_params=query_params,
        )
        bookmarks.reverse()
        self.download(bookmarks, formats=formats)

    def fetch_pages(
        self,
        start_page=1,
        end_page=None,
        query_params=None,
    ) -> list[Bookmark]:
        """
        Gets a list of bookmarks for the user.

        If `end_page` is not provided, it will download all bookmarks from `start_page` to the last page.

        Args:
            start_page (int): Starting page of bookmarks to download. Defaults to 1
            end_page (int): Ending page of bookmarks to download. Defaults to None
            query_params (dict): Query parameters for bookmarks

        Returns:
            bookmarks (Bookmark): List of bookmarks. Ordered from newest to oldest.
        """

        if query_params is None:
            query_params = {}

        with yaspin(text="Getting count of bookmark pages\r", color="yellow") as spinner:
            try:
                num_pages = self.fetch_page_count()
                spinner.color = "green"
                spinner.text = f"Found {num_pages} pages of bookmarks"
                spinner.ok("✔")
            except Exception:
                spinner.color = "red"
                spinner.fail("✘")
                raise

        if num_pages == 0 or start_page > num_pages:
            return []

        end_page = num_pages if end_page is None else end_page
        num_pages_to_download = end_page - start_page + 1

        if num_pages_to_download > 1:
            self._client._log(f"Downloading {num_pages_to_download} pages, from page {start_page} to {end_page}")
        else:
            self._client._log(f"Downloading page {start_page} of {num_pages}")

        bookmark_list = []
        for page_num in tqdm(range(start_page, end_page + 1), desc="Bookmarks Pages", unit="pg"):
            bookmarks = self.fetch_page(page_num, query_params=query_params)
            bookmark_list.extend(bookmarks)

        return bookmark_list

    def fetch_page(self, page: int, query_params=None):
        """
        Gets a page of bookmarks for the user.

        Args:
            query_params (dict): Query parameters for bookmarks

        Returns:
            bookmarks (Bookmark): List of bookmarks. Ordered from newest to oldest.
        """

        default_params = {
            "sort_column": "created_at",
        }
        if query_params is None:
            query_params = {}

        query_params = {**default_params, **query_params}
        query_params["page"] = page
        query_params["user_id"] = self._client.auth.username

        if query_params["page"] < 1:
            raise ao3_sync.api.exceptions.FailedRequest("Page number must be greater than 0")

        history = self._client.get_history()
        last_tracked_bookmark = history.get("last_tracked_bookmark") if history else None

        bookmarks_page: Any = self._client.get_or_fetch(
            self.URL_PATH,
            query_params=query_params,
        )

        bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")
        bookmark_list: list[Bookmark] = []
        for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
            bookmark_id = bookmark_el.css("::attr(id)").get()
            if not bookmark_id:
                self._client._debug_error(f"Skipping bookmark {idx} as it has no ID")
                continue

            if self._client.use_history and bookmark_id == last_tracked_bookmark:
                self._client._debug_log(f"Stopping at bookmark {idx} as it is already cached")
                break

            title_raw = bookmark_el.css("h4.heading a:not(rel)")
            item_href = title_raw.css("::attr(href)").get()

            if not item_href:
                self._client._debug_error(f"Skipping bookmark {idx} as it has no item_href")
                continue

            _, item_path, item_id = item_href.split("/")

            item_type = None
            match f"/{item_path}":
                case self._client.works.URL_PATH:
                    item_type = ItemType.WORK
                case self._client.series.URL_PATH:
                    item_type = ItemType.SERIES
                case _:
                    self._client._debug_error(f"Skipping bookmark {idx} as it has an unknown type: {item_path}")
                    continue

            bookmark = Bookmark(id=bookmark_id, item_type=item_type, item_id=item_id)
            bookmark_list.append(bookmark)

        return bookmark_list

    def fetch_page_count(self):
        """
        Gets the number of bookmark pages for the user.

        Returns:
            num_pages (int): Number of bookmark pages
        """
        first_page: Any = self._client.get_or_fetch(
            self.URL_PATH,
            query_params={"page": 1, "user_id": self._client.auth.username, "sort_column": "created_at"},
        )
        pagination = parsel.Selector(first_page).css("ol.pagination li").getall()

        if len(pagination) < 3:
            return 0

        last_page_str = parsel.Selector(pagination[-2]).css("::text").get()
        return int(last_page_str) if last_page_str else 0

    def download(
        self,
        bookmarks: list[Bookmark],
        formats: list[DownloadFormat] | Literal["all"] = "all",
    ):
        """
        Downloads the work download files for the given bookmarks.

        Args:
            bookmarks (list[Bookmark]): List of bookmarks to download
            formats (list[DownloadFormat] | Literal["all"]): Formats to download. Defaults to "all"

        """

        if not bookmarks or len(bookmarks) == 0:
            self._client._log("No bookmarks to download")
            return

        self._client._log(f"Downloading {len(bookmarks)} bookmarks")
        progress_bar = tqdm(total=len(bookmarks), desc="Works", unit="work")
        for bookmark in bookmarks:
            if bookmark.item_type == ItemType.WORK:
                self._client.works.sync(bookmark.item_id, formats=formats)
            elif bookmark.item_type == ItemType.SERIES:
                self._client.series.sync(bookmark.item_id, formats=formats)

            if self._client.use_history:
                self._client.update_history({"last_tracked_bookmark": bookmark.id})

            progress_bar.update(1)

        progress_bar.close()
