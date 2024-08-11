from loguru import logger
import parsel
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests_ratelimiter import LimiterSession
from ao3_sync import settings
import ao3_sync.exceptions
from urllib.parse import urljoin


class AO3LimiterSession(LimiterSession):
    def request(self, method, url, *args, **kwargs):
        ao3_url = urljoin(settings.HOST, url)
        return super().request(method, ao3_url, *args, **kwargs)


class AO3Session(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=settings.ENV_PATH,
        env_prefix="AO3_",
        extra="ignore",
        env_ignore_empty=True,
    )
    username: str | None = None
    password: SecretStr | None = None

    is_logged_in: bool = False

    _requests: LimiterSession

    def __init__(self):
        super().__init__()
        self._requests = AO3LimiterSession(per_second=1)
        self._requests.headers.update(
            {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0"}
        )

    def set_auth(self, username: str, password: str):
        self.username = username
        self.password = SecretStr(password)
        self.is_logged_in = False

    def get(
        self,
        *args,
        **kwargs,
    ):
        self.login()
        return self._requests.get(*args, **kwargs)

    def login(self):
        if self.is_logged_in:
            return

        if not self.username or not self.password:
            raise ao3_sync.exceptions.LoginError("Username and password must be set")

        logger.debug(f"Logging into AO3 with username: {self.username}")
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
            raise ao3_sync.exceptions.LoginError("Error logging into AO3")

        self.is_logged_in = True
