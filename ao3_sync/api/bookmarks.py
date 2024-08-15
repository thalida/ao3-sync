import warnings
from typing import Literal

import parsel
from tqdm import TqdmExperimentalWarning
from tqdm.rich import tqdm
from yaspin import yaspin

import ao3_sync.exceptions
from ao3_sync.api import AO3Api
from ao3_sync.enums import DownloadFormat, ItemType
from ao3_sync.models import Bookmark, Series, Work
from ao3_sync.utils import debug_error, debug_log, log

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


class BookmarksApi:
    URL_PATH: str = "/bookmarks"

    def __init__(self, client: AO3Api):
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
            log(f"Downloading {num_pages_to_download} pages, from page {start_page} to {end_page}")
        else:
            log(f"Downloading page {start_page} of {num_pages}")

        bookmark_list = []
        for page_num in tqdm(range(start_page, end_page + 1), desc="Bookmarks Pages", unit="pg"):
            local_query_params = {**query_params, "page": page_num}
            bookmarks = self.fetch_page(query_params=local_query_params)
            bookmark_list.extend(bookmarks)

        return bookmark_list

    def fetch_page(self, query_params=None):
        """
        Gets a page of bookmarks for the user.

        Args:
            query_params (dict): Query parameters for bookmarks

        Returns:
            bookmarks (Bookmark): List of bookmarks. Ordered from newest to oldest.
        """

        default_params = {
            "sort_column": "created_at",
            "user_id": self._client.auth.username,
            "page": 1,
        }
        if query_params is None:
            query_params = default_params
        else:
            query_params = {**default_params, **query_params}

        if query_params["page"] < 1:
            raise ao3_sync.exceptions.FailedRequest("Page number must be greater than 0")

        stats = self._client.get_stats()
        last_tracked_bookmark = stats.get("last_tracked_bookmark") if stats else None

        bookmarks_page = self._client.get_or_fetch(
            self.URL_PATH,
            query_params=query_params,
        )

        bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")
        bookmark_list = []
        for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
            bookmark_id = bookmark_el.css("::attr(id)").get()
            if not bookmark_id:
                debug_error(f"Skipping bookmark {idx} as it has no ID")
                continue

            if not self._client.FORCE_UPDATE and bookmark_id == last_tracked_bookmark:
                debug_log(f"Stopping at bookmark {idx} as it is already cached")
                break

            title_raw = bookmark_el.css("h4.heading a:not(rel)")
            item_title = title_raw.css("::text").get()
            item_href = title_raw.css("::attr(href)").get()

            if not item_href:
                debug_error(f"Skipping bookmark {idx} as it has no item_href")
                continue

            _, item_type, item_id = item_href.split("/")

            match f"/{item_type}":
                case self._client.works.URL_PATH:
                    item = Work(
                        id=item_id,
                        title=item_title,
                    )
                case self._client.series.URL_PATH:
                    item = Series(
                        id=item_id,
                        title=item_title,
                    )
                case _:
                    debug_error(f"Skipping bookmark {idx} as it has an unknown item_type: {item_type}")
                    continue

            bookmark = Bookmark(
                id=bookmark_id,
                item=item,
            )
            bookmark_list.append(bookmark)

        return bookmark_list

    def fetch_page_count(self):
        """
        Gets the number of bookmark pages for the user.

        Returns:
            num_pages (int): Number of bookmark pages
        """
        first_page = self._client.get_or_fetch(
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
            log("No bookmarks to download")
            return

        log(f"Downloading {len(bookmarks)} bookmarks")
        progress_bar = tqdm(total=len(bookmarks), desc="Works", unit="work")
        for bookmark in bookmarks:
            if bookmark.item.item_type == ItemType.SERIES:
                debug_log("Skipping series bookmark", bookmark.item.title)
                self._client.update_stats({"last_tracked_bookmark": bookmark.id})
                progress_bar.update(1)
                continue

            self._client.works.sync(bookmark.item, formats=formats)
            self._client.update_stats({"last_tracked_bookmark": bookmark.id})
            progress_bar.update(1)

        progress_bar.close()
