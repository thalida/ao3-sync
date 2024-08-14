import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import parsel
import requests
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests_ratelimiter import LimiterSession
from tqdm import TqdmExperimentalWarning
from tqdm.rich import tqdm
from yaspin import yaspin

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.models import Bookmark, DownloadFormat, ItemType, Series, Work
from ao3_sync.utils import debug_error, debug_log, log

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


class AO3LimiterSession(LimiterSession):
    def request(self, method, url, *args, **kwargs):
        ao3_url = urljoin(settings.HOST, url)
        return super().request(method, ao3_url, *args, **kwargs)


class AO3Api(BaseSettings):
    """
    AO3 API class to interact with the Archive of Our Own website.

    You can override the default settings by setting the following environment variables:
    ```
    AO3_USERNAME=your-username
    AO3_PASSWORD=your-password
    ```

    Attributes:
        username (str | None): AO3 username
        password (SecretStr | None): AO3 password
        is_authenticated (bool): Whether the session is authenticated. Defaults to False

        NUM_REQUESTS_PER_SECOND (float | int): Number of requests per second. Defaults to 0.2 (1 request every 5 seconds)

        OUTPUT_FOLDER (str): Output folder for the API. Defaults to "output"
        DOWNLOADS_FOLDER (str): Downloads folder for the API. Defaults to "downloads"
        STATS_FILE (str): Stats file for the API. Defaults to "stats.json"
        DEBUG_CACHE_FOLDER (str): [Debug Only] Cache folder for the API. Defaults to "debug_cache"
    """

    model_config = SettingsConfigDict(
        env_file=settings.ENV_PATH,
        env_prefix="AO3_",
        extra="ignore",
        env_ignore_empty=True,
    )

    username: str | None = None
    password: SecretStr | None = None
    _is_authenticated: bool = False

    class Routes:
        BOOKMARKS = "/bookmarks"
        WORKS = "/works"
        SERIES = "/series"
        DOWNLOADS = "/downloads"

    NUM_REQUESTS_PER_SECOND: float | int = 0.2

    OUTPUT_FOLDER: str = "output"
    DOWNLOADS_FOLDER: str = "downloads"
    STATS_FILE: str = "stats.json"
    DEBUG_CACHE_FOLDER: str = "debug_cache"

    _requests: LimiterSession

    def __init__(self):
        super().__init__()
        self._requests = AO3LimiterSession(per_second=self.NUM_REQUESTS_PER_SECOND)
        self._requests.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )

    @property
    def is_authenticated(self):
        return self._is_authenticated

    def set_auth(self, username: str, password: str):
        """
        Set the username and password for the AO3Session

        Args:
            username (str): AO3 username
            password (str): AO3 password
        """
        debug_log(f"Updating AO3Session with username: {username} and password: {password}")
        self.username = username
        self.password = SecretStr(password)
        self._is_authenticated = False

    def login(self):
        """
        Log into AO3 using the set username and password

        Raises:
            ao3_sync.exceptions.LoginError: If the login fails

        """
        if self._is_authenticated:
            return

        if not self.username or not self.password:
            raise ao3_sync.exceptions.LoginError("Username and password must be set")

        login_page = self._requests.get("/users/login")
        authenticity_token = (
            parsel.Selector(login_page.text).css("input[name='authenticity_token']::attr(value)").get()
        )
        payload = {
            "user[login]": self.username,
            "user[password]": self.password.get_secret_value(),
            "authenticity_token": authenticity_token,
        }
        # The session in this instance is now logged in
        login_res = self._requests.post(
            "/users/login",
            params=payload,
            allow_redirects=False,
        )

        if "auth_error" in login_res.text:
            raise ao3_sync.exceptions.LoginError(
                f"Error logging into AO3 with username {self.username} and password {self.password}"
            )

        self._is_authenticated = True
        debug_log("Successfully logged in")

    def sync_bookmarks(
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
        bookmarks = self.fetch_bookmark_pages(
            start_page=start_page,
            end_page=end_page,
            query_params=query_params,
        )
        bookmarks.reverse()
        self.download_bookmarks(bookmarks, formats=formats)

    def fetch_bookmark_pages(
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
                num_pages = self.fetch_num_bookmark_pages()
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
        for page_num in tqdm(range(start_page, end_page + 1), desc="Bookmarks Pages"):
            local_query_params = {**query_params, "page": page_num}
            bookmarks = self.fetch_bookmark_page(query_params=local_query_params)
            bookmark_list.extend(bookmarks)

        return bookmark_list

    def fetch_bookmark_page(self, query_params=None):
        """
        Gets a page of bookmarks for the user.

        Args:
            query_params (dict): Query parameters for bookmarks

        Returns:
            bookmarks (Bookmark): List of bookmarks. Ordered from newest to oldest.
        """

        default_params = {
            "sort_column": "created_at",
            "user_id": self.username,
            "page": 1,
        }
        if query_params is None:
            query_params = default_params
        else:
            query_params = {**default_params, **query_params}

        if query_params["page"] < 1:
            raise ao3_sync.exceptions.FailedDownload("Page number must be greater than 0")

        stats = self._get_stats()
        last_tracked_bookmark = stats.get("last_tracked_bookmark") if stats else None

        bookmarks_page = self.get_or_fetch(
            AO3Api.Routes.BOOKMARKS,
            query_params=query_params,
        )

        bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")
        bookmark_list = []
        for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
            bookmark_id = bookmark_el.css("::attr(id)").get()
            if not bookmark_id:
                debug_error(f"Skipping bookmark {idx} as it has no ID")
                continue

            if not settings.FORCE_UPDATE and bookmark_id == last_tracked_bookmark:
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
                case AO3Api.Routes.WORKS:
                    item = Work(
                        id=item_id,
                        title=item_title,
                    )
                case AO3Api.Routes.SERIES:
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

    def fetch_num_bookmark_pages(self):
        """
        Gets the number of bookmark pages for the user.

        Returns:
            num_pages (int): Number of bookmark pages
        """
        first_page = self.get_or_fetch(
            AO3Api.Routes.BOOKMARKS,
            query_params={"page": 1, "user_id": self.username, "sort_column": "created_at"},
        )
        pagination = parsel.Selector(first_page).css("ol.pagination li").getall()

        if len(pagination) < 3:
            return 0

        last_page_str = parsel.Selector(pagination[-2]).css("::text").get()
        return int(last_page_str) if last_page_str else 0

    def download_bookmarks(
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

        # bookmarks are already sorted from oldest to newest, so no need to reverse
        l_bar = "{desc}: {percentage:3.0f}%|"
        r_bar = "| {n:.1f}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        progress_bar_format = f"{l_bar}{{bar}}{r_bar}"
        progress_bar = tqdm(total=len(bookmarks), desc="Works", unit="work", bar_format=progress_bar_format)
        for bookmark in bookmarks:
            if bookmark.item.item_type == ItemType.SERIES:
                debug_log("Skipping series bookmark", bookmark.item.title)
                self._update_stats({"last_tracked_bookmark": bookmark.id})
                progress_bar.update(1)
                continue

            self.download_work(bookmark.item, formats=formats, progress_bar=progress_bar)
            self._update_stats({"last_tracked_bookmark": bookmark.id})

        progress_bar.close()

    def download_work(
        self,
        work: Work,
        formats: list[DownloadFormat] | Literal["all"] = "all",
        progress_bar: tqdm | None = None,
    ):
        """
        Downloads the work download files for the given work.

        Args:
            work (Work): Work to download
            formats (list[DownloadFormat] | Literal["all"]): Formats to download. Defaults to "all"
            progress_bar (tqdm | None): Progress bar to update
        """

        work_page = self.fetch_work(work)
        download_links = (
            parsel.Selector(work_page).css("#main ul.work.navigation li.download ul li a::attr(href)").getall()
        )
        num_links = len(download_links)
        for link_path in download_links:
            parsed_path = urlparse(link_path)
            filename = os.path.basename(parsed_path.path)
            ext = Path(filename).suffix

            if formats == "all" or "all" in formats or ext[1:] in formats:
                debug_log(f"Downloading {ext} for work: {work.title}")
                content = self._download_file(link_path)
                self._save_downloaded_file(filename, content)

            if progress_bar:
                progress_bar.update(1 / num_links)

        debug_log("Downloaded work:", work.title)

    def fetch(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Wrapper around requests.get that handles rate limiting and login

        Args:
            *args: Positional arguments to pass to requests
            **kwargs: Keyword arguments to pass to requests

        Returns:
            requests.Response: Response object

        Raises:
            ao3_sync.exceptions.RateLimitError: If the rate limit is exceeded
            ao3_sync.exceptions.FailedDownload: If the download fails
        """
        self.login()
        res = self._requests.get(*args, **kwargs)
        if res.status_code == 429 or res.status_code == 503 or res.status_code == 504:
            debug_log(f"Rate limit exceeded with status code: {res.status_code}")
            raise ao3_sync.exceptions.RateLimitError("Rate limit exceeded, wait a bit and try again")
        elif res.status_code != 200:
            debug_log(f"Failed to download page with status code: {res.status_code}")
            raise ao3_sync.exceptions.FailedDownload("Failed to download page")
        return res

    def get_or_fetch(
        self,
        url: str,
        query_params: dict | None = None,
        process_response=None,
        **kwargs: Any,
    ):
        contents = None

        cache_key = self._get_cache_key(url, query_params)

        if not settings.FORCE_UPDATE and settings.DEBUG:
            contents = self._get_cached_file(cache_key)

        if not contents:
            debug_log(f"Fetching {url} with params {query_params}")
            res = self.fetch(url, params=query_params, **kwargs)

            if process_response:
                contents = process_response(res)
            else:
                contents = res.text

            if settings.DEBUG:
                self._save_cached_file(cache_key, contents)

        if not contents:
            raise ao3_sync.exceptions.FailedFetch("Failed to fetch page")

        return contents

    def fetch_work(self, work: Work):
        """
        Fetches a work from AO3.

        Args:
            work (Work): Work to fetch

        Returns:
            html (str): HTML content of the work
        """
        work_url = f"{AO3Api.Routes.WORKS}/{work.id}"
        return self.get_or_fetch(work_url)

    def fetch_series(self, series: Series):
        """
        Fetches a series from AO3.

        Args:
            series (Series): Series to fetch

        Returns:
            html (str): HTML content of the series
        """
        series_url = f"{AO3Api.Routes.SERIES}/{series.id}"
        return self.get_or_fetch(series_url)

    def _get_output_folder(self):
        return Path(self.OUTPUT_FOLDER)

    def _get_downloads_folder(self):
        return self._get_output_folder() / self.DOWNLOADS_FOLDER

    def _download_file(self, relative_path):
        debug_log(f"Downloading file at {relative_path}")
        file_content = self.get_or_fetch(relative_path, process_response=lambda res: res.content, allow_redirects=True)

        if not file_content:
            raise ao3_sync.exceptions.FailedDownload("Failed to download")

        return file_content

    def _save_downloaded_file(self, filename, content):
        download_folder = self._get_downloads_folder()
        downloaded_filepath = download_folder / filename
        debug_log(f"Saving downloaded file: {downloaded_filepath}")
        os.makedirs(download_folder, exist_ok=True)
        with open(downloaded_filepath, "wb") as f:
            f.write(content)

    def _get_stats_filepath(self) -> Path:
        return self._get_output_folder() / self.STATS_FILE

    def _get_stats(
        self,
    ):
        filepath = self._get_stats_filepath()
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)

    def _update_stats(self, data=None):
        if data is None:
            data = {}

        curr_stats = self._get_stats()
        if curr_stats:
            data = {**curr_stats, **data}

        filepath = self._get_stats_filepath()
        with open(filepath, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def _get_cache_key(self, url: str, query_params: dict | None = None) -> str:
        query_string = json.dumps(query_params, sort_keys=True) if query_params else ""
        source_str = f"{url}{query_string}"
        return hashlib.sha1(source_str.encode()).hexdigest()

    def _get_cache_filepath(self, cache_key: str) -> Path:
        return self._get_output_folder() / self.DEBUG_CACHE_FOLDER / f"{cache_key}"

    def _get_cached_file(self, cache_key: str):
        filepath = self._get_cache_filepath(cache_key)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _save_cached_file(self, cache_key: str, data: str | bytes):
        filepath = self._get_cache_filepath(cache_key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(filepath, mode) as f:
            f.write(data)
