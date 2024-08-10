import os

from dotenv import load_dotenv
from rich import print

load_dotenv(override=True)

DEBUG = os.getenv("AO3_DEBUG", False)


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)
