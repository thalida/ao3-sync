import hashlib
import json
import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urljoin

import requests
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests_ratelimiter import LimiterSession
from tqdm import TqdmExperimentalWarning

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.utils import debug_log

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)

if TYPE_CHECKING:
    from ao3_sync.api.auth import AuthAPI
    from ao3_sync.api.bookmarks import BookmarksAPI
    from ao3_sync.api.series import SeriesAPI
    from ao3_sync.api.works import WorksAPI


class AO3LimiterSession(LimiterSession):
    def __init__(self, host, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = host

    def request(self, method, url, *args, **kwargs):
        ao3_url = urljoin(self.host, url)
        return super().request(method, ao3_url, *args, **kwargs)


class AO3Api(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=settings.ENV_PATH,
        env_prefix="AO3_",
        extra="ignore",
        env_ignore_empty=True,
    )

    username: str | None = None
    password: SecretStr | None = None

    _http_client: LimiterSession

    HOST: str = "https://archiveofourown.org"
    NUM_REQUESTS_PER_SECOND: float | int = 0.2

    OUTPUT_FOLDER: str = "output"
    DOWNLOADS_FOLDER: str = "downloads"
    STATS_FILE: str = "stats.json"
    DEBUG_CACHE_FOLDER: str = "debug_cache"

    FORCE_UPDATE: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http_client = AO3LimiterSession(self.HOST, per_second=self.NUM_REQUESTS_PER_SECOND)
        self._http_client.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )

        # Resources
        self._auth: Optional["AuthAPI"] = None
        self._bookmarks: Optional["BookmarksAPI"] = None
        self._series: Optional["SeriesAPI"] = None
        self._works: Optional["WorksAPI"] = None

    @property
    def auth(self):
        if self._auth is None:
            from ao3_sync.api.auth import AuthAPI

            self._auth = AuthAPI(self)

        return self._auth

    @property
    def bookmarks(self):
        if self._bookmarks is None:
            from ao3_sync.api.bookmarks import BookmarksAPI

            self._bookmarks = BookmarksAPI(self)

        return self._bookmarks

    @property
    def series(self):
        if self._series is None:
            from ao3_sync.api.series import SeriesAPI

            self._series = SeriesAPI(self)

        return self._series

    @property
    def works(self):
        if self._works is None:
            from ao3_sync.api.works import WorksAPI

            self._works = WorksAPI(self)

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
            requests.Response: Response object

        Raises:
            ao3_sync.exceptions.RateLimitError: If the rate limit is exceeded
            ao3_sync.exceptions.FailedRequest: If the request fails
        """
        self.auth.login()
        res = self._http_client.get(*args, **kwargs)
        if res.status_code == 429 or res.status_code == 503 or res.status_code == 504:
            debug_log(f"Rate limit exceeded with status code: {res.status_code}")
            raise ao3_sync.exceptions.RateLimitError("Rate limit exceeded, wait a bit and try again")
        elif res.status_code != 200:
            debug_log(f"Failed to download page with status code: {res.status_code}")
            raise ao3_sync.exceptions.FailedRequest("Failed to fetch page")
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

        if settings.DEBUG and settings.USE_DEBUG_CACHE:
            contents = self._get_cached_file(cache_key)

        if not contents:
            debug_log(f"Fetching {url} with params {query_params}")
            res = self.fetch(url, params=query_params, **kwargs)

            if process_response:
                contents = process_response(res)
            else:
                contents = res.text

            if settings.DEBUG and settings.USE_DEBUG_CACHE:
                self._save_cached_file(cache_key, contents)

        if not contents:
            raise ao3_sync.exceptions.FailedRequest("Failed to fetch page")

        return contents

    def get_output_folder(self):
        return Path(self.OUTPUT_FOLDER)

    def get_stats_filepath(self) -> Path:
        return self.get_output_folder() / self.STATS_FILE

    def get_stats(
        self,
    ):
        filepath = self.get_stats_filepath()
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)

    def update_stats(self, data=None):
        if data is None:
            data = {}

        curr_stats = self.get_stats()
        if curr_stats:
            data = {**curr_stats, **data}

        filepath = self.get_stats_filepath()
        with open(filepath, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def _get_downloads_folder(self):
        return self.get_output_folder() / self.DOWNLOADS_FOLDER

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

    def _get_cache_key(self, url: str, query_params: dict | None = None) -> str:
        query_string = json.dumps(query_params, sort_keys=True) if query_params else ""
        source_str = f"{url}{query_string}"
        return hashlib.sha1(source_str.encode()).hexdigest()

    def _get_cache_filepath(self, cache_key: str) -> Path:
        return self.get_output_folder() / self.DEBUG_CACHE_FOLDER / f"{cache_key}"

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
