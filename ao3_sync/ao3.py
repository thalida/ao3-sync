import os

import parsel
import requests
from dotenv import load_dotenv

import ao3_sync.choices
import ao3_sync.exceptions

load_dotenv(override=True)

DEBUG = os.getenv("AO3_DEBUG", False)


class AO3:
    def __init__(self, username, password):
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )
        self._username = username
        self._password = password

        self._urls = {
            ao3_sync.choices.SYNC_TYPES.BOOKMARKS: f"https://archiveofourown.org/users/{self._username}/bookmarks",
        }

    def _get_url(self, sync_type):
        return self._urls[sync_type]

    def _get_cache_filepath(self, sync_type):
        return f"debug_files/{sync_type}.html"

    def _get_cached_file(self, sync_type):
        filepath = self._get_cache_filepath(sync_type)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return f.read()

    def _save_cached_file(self, sync_type, text):
        filepath = self._get_cache_filepath(sync_type)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(text)

    def _download_page(self, sync_type, cache=False):
        page = None

        if DEBUG or cache:
            page = self._get_cached_file(sync_type)

        if not page:
            print("Downloading page...")
            self._login()
            res = self._session.get(self._get_url(sync_type))
            page = res.text

            if DEBUG or cache:
                self._save_cached_file(sync_type, page)

        if not page:
            raise ao3_sync.exceptions.FailedDownload("Failed to download page")

        return page

    def _login(self):
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

    def get_bookmarks(self, cache=False):
        bookmarks_page = self._download_page(ao3_sync.choices.SYNC_TYPES.BOOKMARKS, cache=cache)

        bookmarks = parsel.Selector(bookmarks_page).css("ol.bookmark > li")

        for idx, bookmark in enumerate(bookmarks):
            print(f"{idx + 1}: {bookmark.css("h4.heading").xpath("string()").get().replace('\n', '').strip()}")
