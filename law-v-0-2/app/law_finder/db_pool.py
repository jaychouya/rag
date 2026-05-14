import asyncio
import atexit
import logging
import os
from typing import Optional

from law_compat.pgsql import PostgreSQLHelper

logger = logging.getLogger(__name__)

_shared: Optional[PostgreSQLHelper] = None
_init_lock = asyncio.Lock()


def _build_helper() -> PostgreSQLHelper:
    return PostgreSQLHelper(
        host=os.getenv("PGDB_HOST", "192.168.3.191"),
        port=int(os.getenv("PGDB_PORT", "25432")),
        database=os.getenv("PGDB_NAME", "law_test"),
        username=os.getenv("PGDB_USER", "postgres"),
        password=os.getenv("PGDB_PASS", "123456"),
    )


async def get_shared_pg() -> PostgreSQLHelper:
    global _shared
    async with _init_lock:
        if _shared is None:
            _shared = _build_helper()
        await _shared.init_pool(
            min_size=int(os.getenv("PG_POOL_MIN", "1")),
            max_size=int(os.getenv("PG_POOL_MAX", "10")),
        )
    return _shared


def _close_pool_sync() -> None:
    global _shared
    if _shared is None:
        return
    try:
        asyncio.get_running_loop()
        return
    except RuntimeError:
        pass
    try:
        asyncio.run(_shared.close_pool())
    except Exception as e:
        logger.warning("law_finder pool close: %s", e)
    _shared = None


atexit.register(_close_pool_sync)
