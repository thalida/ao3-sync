from loguru import logger
from rich.console import Console

from ao3_sync import settings

console = Console()
dryrun_console = Console(style="yellow")


def log(*args, **kwargs):
    """
    Generic user-facing log function
    """
    console.print(*args, **kwargs)


def debug_log(*args, **kwargs):
    """
    Debug Mode Only: Basic log
    """

    if not settings.DEBUG:
        return

    logger.opt(depth=1).debug(*args, **kwargs)


def debug_error(*args, **kwargs):
    """
    Debug Mode Only: Error log
    """
    if not settings.DEBUG:
        return

    logger.opt(depth=1).error(*args, **kwargs)


def debug_info(*args, **kwargs):
    """
    Debug Mode Only: Info log
    """
    if not settings.DEBUG:
        return

    logger.opt(depth=1).info(*args, **kwargs)


def dryrun_log(message, *args, **kwargs):
    """
    Dry Run Mode Only: User-facing log
    """
    if not settings.DRY_RUN:
        return

    message = f"[bold][DRY RUN][/bold] {message}"

    dryrun_console.print(message, *args, **kwargs)
