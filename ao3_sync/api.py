import json
import os
import warnings
from pathlib import Path
from urllib.parse import urlparse

import parsel
from tqdm import TqdmExperimentalWarning
from tqdm.rich import tqdm
from yaspin import yaspin

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.models import Bookmark, ObjectTypes, Series, Work
from ao3_sync.session import AO3Session
from ao3_sync.utils import debug_error, debug_log, dryrun_log, log

warnings.simplefilter("ignore", category=TqdmExperimentalWarning)


class AO3Api:
    class CACHE_TYPES:
        BOOKMARKS = "bookmarks"
        WORKS = "works"

    OUTPUT_FOLDER = "output"
    CACHE_FOLDER = "debug_cache"
    DOWNLOADS_FOLDER = "downloads"
    STATS_FILE = "stats.json"

    BOOKMARKS_URL_PATH = "/bookmarks"

    session: AO3Session

    def __init__(self, session: AO3Session):
        self.session = session

    def _get_output_folder(self):
        return Path(self.OUTPUT_FOLDER)

    def _get_downloads_folder(self):
        return self._get_output_folder() / self.DOWNLOADS_FOLDER

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

    def _get_cache_filepath(self, cache_type: str, cache_filename: str) -> Path:
        return self._get_output_folder() / self.CACHE_FOLDER / cache_type / f"{cache_filename}.html"

    def _get_cached_file(self, cache_type: str, cache_filename: str):
        filepath = self._get_cache_filepath(cache_type, cache_filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _save_cached_file(self, cache_type: str, cache_filename: str, data: str):
        filepath = self._get_cache_filepath(cache_type, cache_filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(data)

    def _download_html_page(
        self,
        url: str,
        query_params: dict | None = None,
        cache_type: str | None = None,
        cache_filename: str | None = None,
    ):
        downloaded_page = None

        if not settings.FORCE_UPDATE and settings.DEBUG and cache_type and cache_filename:
            downloaded_page = self._get_cached_file(cache_type, cache_filename)

        if not downloaded_page:
            debug_log(f"Downloading page {url} with params {query_params}")
            res = self.session.get(url, params=query_params)
            downloaded_page = res.text

            if settings.DEBUG and cache_type and cache_filename:
                self._save_cached_file(cache_type, cache_filename, downloaded_page)

        if not downloaded_page:
            raise ao3_sync.exceptions.FailedDownload("Failed to download page")

        return downloaded_page

    def _download_work(self, relative_path):
        debug_log(f"Downloading work from {relative_path}")
        r = self.session.get(relative_path, allow_redirects=True)

        downloaded_work = r.content

        if not downloaded_work:
            raise ao3_sync.exceptions.FailedDownload("Failed to download work")

        parsed_path = urlparse(relative_path)
        filename = os.path.basename(parsed_path.path)
        self._save_downloaded_file(filename, r.content)

    def sync_bookmarks(self, query_params=None, paginate=True):
        """
        Sync bookmarks from AO3
        using the cache file, find out what bookmarks are missing and download them
        """
        bookmarks = self.get_bookmarks(paginate=paginate, query_params=query_params)
        log(f"Found {len(bookmarks)} bookmarks to download")

        if not bookmarks or len(bookmarks) == 0:
            log("No bookmarks to download")
            return

        # bookmarks are already sorted from oldest to newest, so no need to reverse
        l_bar = "{desc}: {percentage:3.0f}%|"
        r_bar = "| {n:.1f}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        progress_bar_format = f"{l_bar}{{bar}}{r_bar}"
        progress_bar = tqdm(total=len(bookmarks), desc="Works", unit="work", bar_format=progress_bar_format)
        for bookmark in bookmarks:
            if bookmark.object.type == ObjectTypes.SERIES:
                debug_log("Skipping series bookmark", bookmark.object.title)
                self._update_stats({"last_tracked_bookmark": bookmark.id})
                progress_bar.update(1)
                continue

            work = bookmark.object
            work_page = self._download_html_page(
                work.url,
                cache_type=AO3Api.CACHE_TYPES.WORKS,
                cache_filename=work.id,
            )
            download_links = (
                parsel.Selector(work_page).css("#main ul.work.navigation li.download ul li a::attr(href)").getall()
            )
            num_links = len(download_links)
            for link_path in download_links:
                self._download_work(link_path)
                progress_bar.update(1 / num_links)

            self._update_stats({"last_tracked_bookmark": bookmark.id})
            debug_log("Downloaded work:", work.title)

        progress_bar.close()

    def get_num_bookmark_pages(self):
        first_page = self._download_html_page(
            self.BOOKMARKS_URL_PATH,
            query_params={"page": 1, "user_id": self.session.username, "sort_column": "created_at"},
            cache_type=AO3Api.CACHE_TYPES.BOOKMARKS,
            cache_filename="page_1",
        )
        pagination = parsel.Selector(first_page).css("ol.pagination li").getall()

        if len(pagination) < 3:
            return 0

        last_page_str = parsel.Selector(pagination[-2]).css("::text").get()
        return int(last_page_str) if last_page_str else 0

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

        if query_params["page"] < 1:
            raise ao3_sync.exceptions.FailedDownload("Page number must be greater than 0")

        stats = self._get_stats()
        last_tracked_bookmark = stats.get("last_tracked_bookmark") if stats else None

        if settings.DRY_RUN:
            dryrun_log(f"Would get bookmarks with params: {query_params}")
            if settings.FORCE_UPDATE:
                dryrun_log("Would have force updated of all bookmarks")
            dryrun_log(f"Would {'' if paginate else 'not '}have automatically paginated through bookmarks")
            dryrun_log("Faking return with empty list of bookmarks")
            return []

        bookmark_list = []

        with yaspin(text="Getting count of bookmark pages\r", color="yellow") as spinner:
            try:
                num_pages = self.get_num_bookmark_pages()
                spinner.color = "green"
                spinner.text = f"Found {num_pages} pages of bookmarks"
                spinner.ok("✔")
            except Exception:
                spinner.color = "red"
                spinner.fail("✘")
                raise

        if num_pages == 0 or query_params["page"] > num_pages:
            return bookmark_list

        end_page = num_pages if paginate else query_params["page"]
        num_pages_to_download = end_page - query_params["page"] + 1

        if num_pages_to_download > 1:
            log(f"Downloading {num_pages_to_download} pages, from page {query_params['page']} to {end_page}")
        else:
            log(f"Downloading page {query_params['page']} of {num_pages}")

        for page_num in tqdm(range(query_params["page"], end_page + 1), desc="Bookmarks Pages"):
            local_query_params = {**query_params, "page": page_num}
            bookmarks_page = self._download_html_page(
                self.BOOKMARKS_URL_PATH,
                query_params=local_query_params,
                cache_type=AO3Api.CACHE_TYPES.BOOKMARKS,
                cache_filename=f"page_{local_query_params['page']}",
            )
            bookmark_element_list = parsel.Selector(bookmarks_page).css("ol.bookmark > li")

            for idx, bookmark_el in enumerate(bookmark_element_list, start=1):
                bookmark_id = bookmark_el.css("::attr(id)").get()
                if not bookmark_id:
                    debug_error(f"Skipping bookmark {idx} as it has no ID")
                    continue

                if not settings.FORCE_UPDATE and bookmark_id == last_tracked_bookmark:
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

        return bookmark_list
