import requests
import parsel
from ao3_sync.choices import DEFAULT_SYNC_TYPE


class AO3:
    def __init__(self, username, password, sync_type=DEFAULT_SYNC_TYPE):
        self._session = requests.Session()
        self._username = username
        self._password = password
        self._sync_type = sync_type
        self._bookmarks_url = f"https://archiveofourown.org/users/{self._username}/bookmarks"

    def run(self):
        self._login(self._username, self._password)

    def _login(self, username, password):
        login_page = self._session.get("https://archiveofourown.org/users/login")
        authenticity_token = (
            parsel.Selector(login_page.text).css("input[name='authenticity_token']::attr(value)").get()
        )
        payload = {"user[login]": username, "user[password]": password, "authenticity_token": authenticity_token}
        # The session in this instance is now logged in
        login_post = self._session.post(
            "https://archiveofourown.org/users/login", params=payload, allow_redirects=False
        )
        print(login_post)
        # TODO: deal with a failed login

    def get_bookmarks(self):
        bookmarks_page = self._session.get(self._bookmarks_url)
        bookmarks = parsel.Selector(bookmarks_page.text).css("ol.bookmark li")

        for idx, bookmark in enumerate(bookmarks):
            print(f"{idx + 1}: {bookmark.css("h4.heading a::text").get()}")
