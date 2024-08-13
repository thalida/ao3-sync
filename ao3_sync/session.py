from typing import Any
from urllib.parse import urljoin

import parsel
import requests
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests_ratelimiter import LimiterSession

import ao3_sync.exceptions
from ao3_sync import settings
from ao3_sync.utils import debug_log, dryrun_log


class AO3LimiterSession(LimiterSession):
    def request(self, method, url, *args, **kwargs):
        ao3_url = urljoin(settings.HOST, url)
        return super().request(method, ao3_url, *args, **kwargs)


class AO3Session(BaseSettings):
    """
    Session object for AO3

    This class is a wrapper around requests.Session that handles all requests to AO3.
    By default, it will rate limit requests to 1 request every 5 seconds.

    Attributes:
        username (str | None): AO3 username
        password (SecretStr | None): AO3 password
        is_logged_in (bool): Is the session logged in? Defaults to False
        NUM_REQUESTS_PER_SECOND (float | int): Number of requests per second. Defaults to 0.2
    """

    model_config = SettingsConfigDict(
        env_file=settings.ENV_PATH,
        env_prefix="AO3_",
        extra="ignore",
        env_ignore_empty=True,
    )

    username: str | None = None
    password: SecretStr | None = None
    is_logged_in: bool = False

    NUM_REQUESTS_PER_SECOND: float | int = 0.2
    _requests: LimiterSession

    def __init__(self):
        super().__init__()
        self._requests = AO3LimiterSession(per_second=self.NUM_REQUESTS_PER_SECOND)
        self._requests.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )

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
        self.is_logged_in = False

    def get(
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

    def login(self):
        """
        Log into AO3 using the set username and password

        Raises:
            ao3_sync.exceptions.LoginError: If the login fails

        """
        if self.is_logged_in:
            return

        if not self.username or not self.password:
            raise ao3_sync.exceptions.LoginError("Username and password must be set")

        if settings.DRY_RUN:
            dryrun_log("Faking successful login")
            self.is_logged_in = True
            return

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

        self.is_logged_in = True
        debug_log("Successfully logged in")
