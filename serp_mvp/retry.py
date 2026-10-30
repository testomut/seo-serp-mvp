import logging
import time

log = logging.getLogger(__name__)


def with_retries(func, attempts=3, first_pause=2):
    """Call func(); on error wait 2s, 4s, ... and try again. Re-raise after the last attempt."""
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as error:
            if attempt == attempts:
                raise
            pause = first_pause * 2 ** (attempt - 1)
            log.warning("Attempt %d failed (%s), retrying in %ss", attempt, error, pause)
            time.sleep(pause)
