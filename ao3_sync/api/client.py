import datetime
import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from loguru import logger
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests_ratelimiter import LimiterSession
from rich.console import Console
from tqdm import TqdmExperimentalWarning

import ao3_sync.api.exceptions
from ao3_sync.api.models import ApiHistory

if TYPE_CHECKING:
    from ao3_sync.api.resources.auth import AuthApi
    from ao3_sync.api.resources.bookmarks import BookmarksApi
    from ao3_sync.api.resources.series import SeriesApi
    from ao3_sync.api.resources.works import WorksApi


warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


console = Console()


class AO3LimiterSession(LimiterSession):
    def request(self, method, url, *args, **kwargs):
        ao3_url = urljoin("https://archiveofourown.org", url)
        return super().request(method, ao3_url, *args, **kwargs)


class AO3ApiClient(BaseSettings):
    """
    AO3 API

    Attributes:
        username (str): AO3 username
        password (SecretStr): AO3 password
        host (str): AO3 host
        requests_delay_seconds (float | int): Delay between requests
        output_dir (str): Output directory
        downloads_dir (str): Downloads directory
        use_history (bool): Use history
        history_filename (str): History filename
        debug (bool): Debug mode
        use_debug_cache (bool): Use debug cache
        debug_cache_dir (str): Debug cache directory

    """

    model_config = SettingsConfigDict(
        env_prefix="AO3_",
        extra="ignore",
        env_ignore_empty=True,
        case_sensitive=False,
    )

    username: str | None = None
    password: SecretStr | None = None

    output_dir: str = "output/"

    downloads_dir: str = "downloads/"
    requests_delay_seconds: float = 4.0

    use_history: bool = False
    history_filepath: str = "history.json"

    debug: bool = False
    use_debug_cache: bool = True
    debug_cache_dir: str = "debug_cache"

    _http_client: LimiterSession

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._http_client = AO3LimiterSession(burst=1, per_second=1 / self.requests_delay_seconds)
        self._http_client.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )

        # Resources
        self._auth: Optional["AuthApi"] = None
        self._bookmarks: Optional["BookmarksApi"] = None
        self._series: Optional["SeriesApi"] = None
        self._works: Optional["WorksApi"] = None

    @property
    def auth(self):
        """
        Auth Api Instance

        Returns:
            (AuthApi): AuthApi Instance
        """

        if self._auth is None:
            from ao3_sync.api.resources.auth import AuthApi

            self._auth = AuthApi(self)

        return self._auth

    @property
    def bookmarks(self):
        """
        Bookmarks Api Instance

        Returns:
            (BookmarksApi): BookmarksApi Instance
        """

        if self._bookmarks is None:
            from ao3_sync.api.resources.bookmarks import BookmarksApi

            self._bookmarks = BookmarksApi(self)

        return self._bookmarks

    @property
    def series(self):
        """
        Series Api Instance

        Returns:
            (SeriesApi): SeriesApi Instance
        """

        if self._series is None:
            from ao3_sync.api.resources.series import SeriesApi

            self._series = SeriesApi(self)

        return self._series

    @property
    def works(self):
        """
        Works Api Instance

        Returns:
            (WorksApi): WorksApi Instance
        """

        if self._works is None:
            from ao3_sync.api.resources.works import WorksApi

            self._works = WorksApi(self)

        return self._works

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
            (requests.Response): Response object

        Raises:
            ao3_sync.exceptions.RateLimitError: If the rate limit is exceeded
            ao3_sync.exceptions.FailedRequest: If the request fails
        """
        self.auth.login()
        res = self._http_client.get(*args, **kwargs)
        if res.status_code == 429 or res.status_code == 503 or res.status_code == 504:
            self._debug_log(f"Rate limit exceeded with status code: {res.status_code}")
            raise ao3_sync.api.exceptions.RateLimitError("Rate limit exceeded, wait a bit and try again")
        elif res.status_code != 200:
            self._debug_log(f"Failed to download page with status code: {res.status_code}")
            raise ao3_sync.api.exceptions.FailedRequest("Failed to fetch page")
        return res

    def get_or_fetch(
        self,
        url: str,
        query_params: dict | None = None,
        process_response=None,
        **kwargs: Any,
    ):
        """
        Fetches a page and caches it if debug mode is enabled and use_debug_cache is True

        Args:
            url (str): URL to fetch
            query_params (dict): Query parameters
            process_response (Callable): Function to process the response
            **kwargs: Keyword arguments to pass to requests

        Returns:
            (str | bytes): Page contents

        Raises:
            ao3_sync.exceptions.FailedRequest: If the request fails
        """

        contents = None

        cache_key = self._get_debug_cache_key(url, query_params)

        if self.debug and self.use_debug_cache:
            self._debug_log(f"Cache key for {url} is {cache_key}")
            contents = self._get_debug_cache_file(cache_key)

        if not contents:
            self._debug_log(f"Fetching {url} with params {query_params}")
            res = self.fetch(url, params=query_params, **kwargs)

            if process_response:
                contents = process_response(res)
            else:
                contents = res.text

            if self.debug:
                self._save_debug_cache_file(cache_key, contents)

        if not contents:
            raise ao3_sync.api.exceptions.FailedRequest("Failed to fetch page")

        return contents

    def get_output_dir(self):
        """
        Get the output folder

        Returns:
            (Path): Output folder
        """
        return Path(self.output_dir)

    def get_history_filepath(self) -> Path:
        """
        Get the stats file path

        Returns:
            (Path): Stats file path
        """

        return self.get_output_dir() / self.history_filepath

    def get_history(
        self,
    ):
        """
        Get the internal API stats

        Returns:
            (dict): Stats
        """

        filepath = self.get_history_filepath()
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                try:
                    history_json = json.load(f)
                    return ApiHistory(**history_json)
                except json.JSONDecodeError:
                    return ApiHistory()

        return ApiHistory()

    def update_history(self, history: ApiHistory):
        """
        Update the internal API stats

        Args:
            data (dict): Data to update
        """

        history.updated_at = datetime.datetime.now()

        filepath = self.get_history_filepath()
        with open(filepath, "w") as f:
            json.dump(
                history.model_dump(),
                f,
                ensure_ascii=False,
                indent=4,
                default=str,
                sort_keys=True,
            )

    def get_downloads_dir(self):
        """
        Get the downloads folder

        Returns:
            (Path): Downloads folder
        """
        return self.get_output_dir() / self.downloads_dir

    def download_file(self, relative_path):
        """
        Download a file from AO3

        Args:
            relative_path (str): Relative path to the file

        Returns:
            (str): File contents
        """

        parsed_path = urlparse(relative_path)
        filename = os.path.basename(parsed_path.path)
        file_content = self.fetch_file(relative_path)
        self.save_file(filename, file_content)

    def fetch_file(self, relative_path):
        self._debug_log(f"Downloading file at {relative_path}")
        file_content = self.get_or_fetch(relative_path, process_response=lambda res: res.content, allow_redirects=True)

        if not file_content:
            raise ao3_sync.api.exceptions.FailedDownload("Failed to download")

        return file_content

    def save_file(self, filename, data: str | bytes):
        filename_without_ext = os.path.splitext(filename)[0]
        download_folder = self.get_downloads_dir() / filename_without_ext
        downloaded_filepath = download_folder / filename
        self._debug_log(f"Saving downloaded file: {downloaded_filepath}")
        os.makedirs(download_folder, exist_ok=True)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(downloaded_filepath, mode) as f:
            f.write(data)

    def get_debug_cache_dir(self):
        """
        Get the debug cache folder

        Returns:
            (Path): Debug cache folder
        """
        return self.get_output_dir() / self.debug_cache_dir

    def _get_debug_cache_key(self, url: str, query_params: dict | None = None) -> str:
        query_string = json.dumps(query_params, sort_keys=True) if query_params else ""
        source_str = f"{url}{query_string}"
        return hashlib.sha1(source_str.encode()).hexdigest()

    def _get_debug_cache_filepath(self, cache_key: str) -> Path:
        return self.get_debug_cache_dir() / f"{cache_key}"

    def _get_debug_cache_file(self, cache_key: str):
        filepath = self._get_debug_cache_filepath(cache_key)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(filepath, "rb") as f:
                    return f.read()

    def _save_debug_cache_file(self, cache_key: str, data: str | bytes):
        filepath = self._get_debug_cache_filepath(cache_key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(filepath, mode) as f:
            f.write(data)

    def _log(self, *args, **kwargs):
        """
        Generic user-facing log function
        """
        console.print(*args, **kwargs)

    def _debug_log(self, *args, **kwargs):
        """
        Debug Mode Only: Basic log
        """

        if not self.debug:
            return

        logger.opt(depth=1).debug(*args, **kwargs)

    def _debug_error(self, *args, **kwargs):
        """
        Debug Mode Only: Error log
        """
        if not self.debug:
            return

        logger.opt(depth=1).error(*args, **kwargs)

    def _debug_info(self, *args, **kwargs):
        """
        Debug Mode Only: Info log
        """
        if not self.debug:
            return

        logger.opt(depth=1).info(*args, **kwargs)
