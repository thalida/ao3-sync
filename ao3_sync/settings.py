from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).parent.parent
ENV_PATH = ROOT_DIR / ".env"
ENV_PREFIX = "AO3_"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_PATH, env_prefix=ENV_PREFIX, extra="ignore")

    ROOT_DIR: Path = ROOT_DIR
    ENV_PATH: Path = ENV_PATH
    ENV_PREFIX: str = ENV_PREFIX

    DEBUG: bool = False
    HOST: str = "https://archiveofourown.org"


settings = Settings()
