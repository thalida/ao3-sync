from loguru import logger
from ao3_sync import settings
from rich.console import Console

console = Console()
dryrun_console = Console(style="yellow")


def log(*args, **kwargs):
    console.print(*args, **kwargs)


def debug_log(*args, **kwargs):
    if not settings.DEBUG:
        return

    logger.opt(depth=1).debug(*args, **kwargs)


def debug_error(*args, **kwargs):
    if not settings.DEBUG:
        return

    logger.opt(depth=1).error(*args, **kwargs)


def debug_info(*args, **kwargs):
    if not settings.DEBUG:
        return

    logger.opt(depth=1).info(*args, **kwargs)


def dryrun_log(message, *args, **kwargs):
    if not settings.DRY_RUN:
        return

    message = f"[bold][DRY RUN][/bold] {message}"

    dryrun_console.print(message, *args, **kwargs)
