from typing import Any, Optional, Tuple

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from qagent.config import settings

CHECKPOINT_SCHEMA = "langgraph"


async def open_checkpointer() -> Tuple[BaseCheckpointSaver, Optional[Any]]:
    """
    Returns (saver, connection). With a Postgres direct URL this is AsyncPostgresSaver in its
    own `langgraph` schema (the pooler is unsuitable: it breaks session state such as
    search_path); otherwise an in-memory saver. Close the connection with `await conn.close()`.
    """
    url = settings.database_url_direct
    if not url or not url.startswith("postgresql"):
        return InMemorySaver(), None

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    conn = await AsyncConnection.connect(
        url.replace("postgresql+psycopg://", "postgresql://"),
        autocommit=True, prepare_threshold=0, row_factory=dict_row,
    )
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {CHECKPOINT_SCHEMA}")
    await conn.execute(f"SET search_path TO {CHECKPOINT_SCHEMA}")
    saver = AsyncPostgresSaver(conn)
    await saver.setup()
    return saver, conn
