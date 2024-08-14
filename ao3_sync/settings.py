from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent
ENV_PATH = ROOT_DIR / ".env"
ENV_PREFIX = "AO3_"


class Settings(BaseSettings):
    """
    Global settings for AO3 Sync

    All settings are loaded from the environment file and can be overridden by environment variables.

    Example `.env` file:
    ```
    AO3_DEBUG=true
    ```

    Attributes:
        ROOT_DIR (Path): Root directory of the project
        ENV_PATH (Path): Path to the environment file. Defaults to ROOT_DIR/.env
        ENV_PREFIX (str): Prefix for environment variables. Defaults to AO3_
        HOST (str): Host URL of the AO3 website. Defaults to https://archiveofourown.org
        DEBUG (bool): Enable debug mode
        FORCE_UPDATE (bool): Force update of existing data
    """

    model_config = SettingsConfigDict(env_file=ENV_PATH, env_prefix=ENV_PREFIX, extra="ignore")

    ROOT_DIR: Path = ROOT_DIR
    ENV_PATH: Path = ENV_PATH
    ENV_PREFIX: str = ENV_PREFIX

    DEBUG: bool = False
    FORCE_UPDATE: bool = False

    HOST: str = "https://archiveofourown.org"


settings = Settings()
