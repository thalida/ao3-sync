import os

import parsel
from dotenv import load_dotenv
from loguru import logger
from requests_ratelimiter import LimiterSession

import ao3_sync.exceptions
from ao3_sync.models import Bookmark, ObjectTypes, Series, Work
from ao3_sync.utils import debug_print

load_dotenv(override=True)

DEBUG = os.getenv("AO3_DEBUG", False)
if isinstance(DEBUG, str):
    DEBUG = DEBUG.lower() in ("true", "1")


class AO3:
    class SYNC_TYPES:
        BOOKMARKS = "bookmarks"

    DEFAULT_SYNC_TYPE = SYNC_TYPES.BOOKMARKS

    def __init__(self, username, password):
        self._session = LimiterSession(per_second=1)
        self._session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )
        self._username = username
        self._password = password
        self._logged_in = False
        self._download_urls = {
            AO3.SYNC_TYPES.BOOKMARKS: "https://archiveofourown.org/bookmarks",
        }

    @classmethod
    def get_sync_types_values(cls):
        return [
            cls.SYNC_TYPES.BOOKMARKS,
        ]

    @classmethod
    def get_default_sync_type(cls):
        return cls.DEFAULT_SYNC_TYPE

    def _get_download_url(self, sync_type):
        return self._download_urls[sync_type]

    def _get_cache_filepath(self, sync_type, page=None):
        return f"debug_files/{sync_type}{f"_{page}" if page else ""}.html"

    def _get_tracking_filepath(self, sync_type):
        return f"debug_files/{sync_type}_last_bookmark_id.txt"

    def _get_cached_file(self, sync_type, page=None):
        filepath = self._get_cache_filepath(sync_type, page=page)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _save_cached_file(self, sync_type, text, page=None):
        filepath = self._get_cache_filepath(sync_type, page=page)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(text)

    def _update_last_tracked(self, sync_type, bookmark_id):
        filepath = self._get_tracking_filepath(sync_type)
        with open(filepath, "w") as f:
            f.write(bookmark_id)

    def _get_last_tracked(self, sync_type):
        filepath = self._get_tracking_filepath(sync_type)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _download_page(self, sync_type, cache=False, req_params=None):
        downloaded_page = None
        page = req_params.get("page") if req_params else None

        if DEBUG or cache:
            print("Getting cached file...")
            downloaded_page = self._get_cached_file(sync_type, page=page)

        if not downloaded_page:
            url = self._get_download_url(sync_type)
            self._login()
            logger.debug(f"Downloading page {url} with params {req_params}")
            res = self._session.get(url, params=req_params)
            downloaded_page = res.text

            if DEBUG or cache:
                print("Saving file to cache...")
                self._save_cached_file(sync_type, downloaded_page, page=page)

        if not downloaded_page:
            raise ao3_sync.exceptions.FailedDownload("Failed to download page")

        return downloaded_page

    def _login(self):
        if self._logged_in:
            return

        logger.debug(f"Logging into AO3 with username: {self._username}")
        login_page = self._session.get("https://archiveofourown.org/users/login")
        authenticity_token = (
            parsel.Selector(login_page.text).css("input[name='authenticity_token']::attr(value)").get()
        )
        payload = {
            "user[login]": self._username,
            "user[password]": self._password,
            "authenticity_token": authenticity_token,
        }
        # The session in this instance is now logged in
        login_res = self._session.post(
            "https://archiveofourown.org/users/login",
            params=payload,
            allow_redirects=False,
        )
        if "auth_error" in login_res.text:
            raise ao3_sync.exceptions.LoginError("Error logging into AO3")

        self._logged_in = True

    def sync_bookmarks(self, paginate=True, req_params=None, cache=False):
        """
        Sync bookmarks from AO3
        using the cache file, find out what bookmarks are missing and download them
        """
        bookmarks = self.get_bookmarks(paginate=paginate, custom_req_params=req_params, cache=cache)
        for bookmark in bookmarks:
            debug_print(bookmark)

        debug_print("Count of bookmarks:", len(bookmarks))

    def get_bookmarks(
        self,
        paginate=True,
        custom_req_params=None,
        cache=False,
    ) -> list[Bookmark]:
        # Always start at the first page of bookmarks
        req_params = {
            "sort_column": "created_at",
            "user_id": self._username,
            "page": 1,
        }
        if custom_req_params:
            req_params.update(custom_req_params)

        last_tracked_bookmark = self._get_last_tracked(AO3.SYNC_TYPES.BOOKMARKS)

        bookmark_list = []
        get_next_page = True
        while get_next_page is True:
            bookmarks_page = self._download_page(AO3.SYNC_TYPES.BOOKMARKS, cache=cache, req_params=req_params)
            bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")

            for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
                bookmark_id = bookmark_el.css("::attr(id)").get()
                if not bookmark_id:
                    logger.error(f"Skipping bookmark {idx} as it has no ID")
                    continue

                if bookmark_id == last_tracked_bookmark:
                    get_next_page = False
                    debug_print(f"Skipping bookmark {idx} as it is cached")
                    break

                title_raw = bookmark_el.css("h4.heading a:not(rel)")
                object_title = title_raw.css("::text").get()
                object_href = title_raw.css("::attr(href)").get()

                if not object_href:
                    logger.error(f"Skipping bookmark {idx} as it has no object_href")
                    continue

                _, object_type, object_id = object_href.split("/")

                if object_type == ObjectTypes.WORK:
                    obj = Work(
                        id=object_id,
                        title=object_title,
                    )
                elif object_type == ObjectTypes.SERIES:
                    obj = Series(
                        id=object_id,
                        title=object_title,
                    )
                else:
                    logger.error(f"Skipping bookmark {idx} as it has an unknown object_type: {object_type}")
                    continue

                bookmark = Bookmark(
                    id=bookmark_id,
                    object=obj,
                )
                bookmark_list.append(bookmark)
                # debug_print(
                #     f"Bookmark Item: {bookmark.id} {bookmark.object.title} {bookmark.object.type}  {bookmark.object.url}"
                # )

            if paginate is False:
                get_next_page = False
            elif get_next_page:
                has_next_page = parsel.Selector(bookmarks_page).css("li[title=next] a").get()
                if not has_next_page:
                    get_next_page = False
                    break
                req_params["page"] += 1

        return bookmark_list
