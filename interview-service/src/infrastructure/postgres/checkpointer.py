from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


async def create_checkpointer(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return checkpointer
