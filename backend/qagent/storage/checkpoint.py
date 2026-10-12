from typing import Any, Optional, Tuple

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from qagent.config import settings

CHECKPOINT_SCHEMA = "langgraph"


async def open_checkpointer() -> Tuple[BaseCheckpointSaver, Optional[Any]]:
    """
    Returns (saver, connection). With a Postgres direct URL this is AsyncPostgresSaver in its
    own `langgraph` schema (the pooler is unsuitable: it breaks session state such as
    search_path); otherwise an in-memory saver. Close the returned pool with `await conn.close()`.
    """
    url = settings.database_url_direct
    if not url or not url.startswith("postgresql"):
        return InMemorySaver(), None

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    async def configure(conn) -> None:
        await conn.execute(f"SET search_path TO {CHECKPOINT_SCHEMA}")

    # A pool, not one connection: Neon closes idle connections, and a single long-lived one then fails every run
    # with "the connection is closed". The pool checks a connection before handing it out and replaces dead ones.
    pool = AsyncConnectionPool(
        url.replace("postgresql+psycopg://", "postgresql://"),
        min_size=1, max_size=4, open=False, configure=configure, check=AsyncConnectionPool.check_connection,
        max_idle=240, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open(wait=True)
    async with pool.connection() as conn:
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {CHECKPOINT_SCHEMA}")
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver, pool
