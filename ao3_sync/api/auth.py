import parsel
from pydantic import SecretStr
from pydantic_settings import BaseSettings

import ao3_sync.exceptions
from ao3_sync.api import AO3Api


class AuthApi(BaseSettings):
    _is_authenticated: bool = False

    def __init__(self, client: AO3Api, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = client

    @property
    def is_authenticated(self):
        return self._is_authenticated

    @property
    def username(self):
        return self._client.username

    @property
    def password(self):
        return self._client.password

    def set_account(self, username: str | None, password: str | None):
        """
        Set the username and password for the AO3Session

        Args:
            username (str): AO3 username
            password (str): AO3 password
        """
        self._client.debug_log(f"Updating AO3Session with username: {username} and password: {password}")
        self._client.username = username
        self._client.password = SecretStr(password) if password else None
        self._is_authenticated = False

    def login(self, username: str | None = None, password: str | None = None):
        """
        Log into AO3 using the set username and password

        Raises:
            ao3_sync.exceptions.LoginError: If the login fails

        """

        if username is not None or password is not None:
            self.set_account(username, password)

        if self._is_authenticated:
            return

        if not self.username or not self.password:
            raise ao3_sync.exceptions.LoginError("Username and password must be set")

        login_page = self._client._http_client.get("/users/login")
        authenticity_token = (
            parsel.Selector(login_page.text).css("input[name='authenticity_token']::attr(value)").get()
        )
        payload = {
            "user[login]": self.username,
            "user[password]": self.password.get_secret_value(),
            "authenticity_token": authenticity_token,
        }
        # The session in this instance is now logged in
        login_res = self._client._http_client.post(
            "/users/login",
            params=payload,
            allow_redirects=False,
        )

        if "auth_error" in login_res.text:
            raise ao3_sync.exceptions.LoginError(
                f"Error logging into AO3 with username {self.username} and password {self.password}"
            )

        self._is_authenticated = True
        self._client.debug_log("Successfully logged in")
