from rich import print
from ao3_sync import settings


def debug_print(*args, **kwargs):
    if settings.DEBUG:
        print(*args, **kwargs)
