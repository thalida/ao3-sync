from loguru import logger
from ao3_sync import settings


def debug_log(*args, **kwargs):
    if not settings.DEBUG:
        return

    logger.debug(*args, **kwargs)
