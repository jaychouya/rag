import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("law_finder.perf")


@contextmanager
def timed_stage(stage: str, **extra: Any) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        if extra:
            logger.info("stage=%s ms=%.1f %s", stage, ms, extra)
        else:
            logger.info("stage=%s ms=%.1f", stage, ms)
