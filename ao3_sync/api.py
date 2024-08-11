import os
from urllib.parse import urlparse

import parsel

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.models import Bookmark, ObjectTypes, Series, Work
from ao3_sync.session import AO3Session
from ao3_sync.utils import debug_error, debug_log, dryrun_log


class AO3Api:
    class CACHE_CATEGORIES:
        BOOKMARKS = "bookmarks"
        WORKS = "works"
        SERIES = "series"
        DOWNLOADS = "downloads"

    class SYNC_TYPES:
        BOOKMARKS = "bookmarks"

    DEFAULT_SYNC_TYPE = SYNC_TYPES.BOOKMARKS

    DOWNLOAD_PATHS = {
        SYNC_TYPES.BOOKMARKS: "/bookmarks",
    }

    session: AO3Session

    def __init__(self, session: AO3Session):
        self.session = session

    @classmethod
    def get_sync_types_values(cls):
        return [
            cls.SYNC_TYPES.BOOKMARKS,
        ]

    @classmethod
    def get_default_sync_type(cls):
        return cls.DEFAULT_SYNC_TYPE

    def _get_download_path(self, sync_type):
        return self.DOWNLOAD_PATHS[sync_type]

    def _get_tracking_filepath(self, sync_type):
        return f"debug_files/{sync_type}_last_id.txt"

    def _get_cache_filepath(self, cache_category, cache_id=None):
        return f"debug_files/{cache_category}{f"_{cache_id}" if cache_id else ""}.html"

    def _get_cached_file(self, cache_category, cache_id=None):
        filepath = self._get_cache_filepath(cache_category, cache_id=cache_id)
        debug_log(f"Getting cached file: {filepath}")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _save_cached_file(self, cache_category, text, cache_id=None):
        filepath = self._get_cache_filepath(cache_category, cache_id=cache_id)
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

    def _download_page(
        self,
        url,
        query_params=None,
        cache_category=None,
        cache_id=None,
    ):
        downloaded_page = None

        if settings.DEBUG:
            downloaded_page = self._get_cached_file(cache_category, cache_id=cache_id)

        if not downloaded_page:
            debug_log(f"Downloading page {url} with params {query_params}")
            res = self.session.get(url, params=query_params)
            downloaded_page = res.text

            if settings.DEBUG:
                debug_log("Saving file to cache...")
                self._save_cached_file(cache_category, downloaded_page, cache_id=cache_id)

        if not downloaded_page:
            raise ao3_sync.exceptions.FailedDownload("Failed to download page")

        return downloaded_page

    def _download_work(self, relative_path):
        parsed_path = urlparse(relative_path)
        filename = os.path.basename(parsed_path.path)
        r = self.session.get(relative_path, allow_redirects=True)
        os.makedirs(os.path.dirname(f"downloads/{filename}"), exist_ok=True)
        with open(f"downloads/{filename}", "wb") as f:
            f.write(r.content)

    def sync_bookmarks(self, query_params=None, paginate=True):
        """
        Sync bookmarks from AO3
        using the cache file, find out what bookmarks are missing and download them
        """
        bookmarks = self.get_bookmarks(paginate=paginate, query_params=query_params)
        debug_log(f"Found {len(bookmarks)} bookmarks to download")

        # bookmarks are already sorted from oldest to newest, so no need to reverse
        for bookmark in bookmarks:
            if bookmark.object.type == ObjectTypes.SERIES:
                debug_log("Skipping series bookmark", bookmark.object.title)
                self._update_last_tracked(AO3Api.SYNC_TYPES.BOOKMARKS, bookmark.id)
                continue

            work = bookmark.object
            work_page = self._download_page(
                work.url,
                cache_category=AO3Api.CACHE_CATEGORIES.WORKS,
                cache_id=work.id,
            )
            download_links = (
                parsel.Selector(work_page).css("#main ul.work.navigation li.download ul li a::attr(href)").getall()
            )
            for link_path in download_links:
                self._download_work(link_path)

            self._update_last_tracked(AO3Api.SYNC_TYPES.BOOKMARKS, bookmark.id)
            debug_log("Downloaded work:", work.title)

    def get_bookmarks(
        self,
        paginate=True,
        query_params=None,
    ) -> list[Bookmark]:
        # Always start at the first page of bookmarks
        default_params = {
            "sort_column": "created_at",
            "user_id": self.session.username,
            "page": 1,
        }
        if query_params is None:
            query_params = default_params
        else:
            query_params = {**default_params, **query_params}

        last_tracked_bookmark = (
            self._get_last_tracked(AO3Api.SYNC_TYPES.BOOKMARKS) if not settings.FORCE_UPDATE else None
        )

        if settings.DRY_RUN:
            dryrun_log(
                f"Getting bookmarks with params: {query_params} stopping at from bookmark: {last_tracked_bookmark}"
            )
            return []

        bookmark_list = []
        get_next_page = True
        while get_next_page is True:
            bookmarks_url = self._get_download_path(AO3Api.SYNC_TYPES.BOOKMARKS)
            bookmarks_page = self._download_page(
                bookmarks_url,
                query_params=query_params,
                cache_category=AO3Api.CACHE_CATEGORIES.BOOKMARKS,
                cache_id=query_params["page"],
            )
            bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")

            for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
                bookmark_id = bookmark_el.css("::attr(id)").get()
                if not bookmark_id:
                    debug_error(f"Skipping bookmark {idx} as it has no ID")
                    continue

                if bookmark_id == last_tracked_bookmark:
                    get_next_page = False
                    debug_log(f"Stopping at bookmark {idx} as it is already cached")
                    break

                title_raw = bookmark_el.css("h4.heading a:not(rel)")
                object_title = title_raw.css("::text").get()
                object_href = title_raw.css("::attr(href)").get()

                if not object_href:
                    debug_error(f"Skipping bookmark {idx} as it has no object_href")
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
                    debug_error(f"Skipping bookmark {idx} as it has an unknown object_type: {object_type}")
                    continue

                bookmark = Bookmark(
                    id=bookmark_id,
                    object=obj,
                )
                bookmark_list.insert(0, bookmark)

            if paginate is False:
                get_next_page = False
            elif get_next_page:
                has_next_page = parsel.Selector(bookmarks_page).css("li[title=next] a").get()
                if not has_next_page:
                    get_next_page = False
                    break
                query_params["page"] += 1

        return bookmark_list
