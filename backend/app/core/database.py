import logging
from typing import Optional, Annotated, Sequence, TypedDict, Any, Iterator, AsyncIterator, Mapping, Collection
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langchain_core.runnables import RunnableConfig
from app.core.config import settings

logger = logging.getLogger("database")

# Global reference to the active AsyncPostgresStore instance
store_instance: Optional[AsyncPostgresStore] = None
# Reference to the active context manager
_store_context_manager = None

# Global reference to the active AsyncPostgresSaver instance
saver_instance: Optional[AsyncPostgresSaver] = None
# Reference to the active context manager
_saver_context_manager = None

# Global reference to the active AsyncConnectionPool
pool_instance: Optional[Any] = None

class AsyncPostgresStoreProxy:
    """
    A Proxy class that delegates all calls to the active global store_instance.
    This resolves the import-time dependency issue where graph.py compiles
    before the database context is entered during application startup.
    """
    def __getattr__(self, name):
        global store_instance
        if store_instance is None:
            raise RuntimeError(
                "AsyncPostgresStore is not initialized. Ensure init_db() is called on startup."
            )
        return getattr(store_instance, name)

# Global store proxy that can be imported and compiled in the LangGraph workflow
store = AsyncPostgresStoreProxy()

def get_store() -> AsyncPostgresStoreProxy:
    """
    Returns the global store proxy.
    """
    return store


class AsyncPostgresSaverProxy(BaseCheckpointSaver):
    """
    A Proxy class that delegates all calls to the active global saver_instance.
    This resolves the import-time dependency issue where graph.py compiles
    before the database context is entered during application startup.
    """
    def __init__(self):
        super().__init__()

    @property
    def saver(self) -> BaseCheckpointSaver:
        global saver_instance
        if saver_instance is None:
            raise RuntimeError(
                "AsyncPostgresSaver is not initialized. Ensure init_db() is called on startup."
            )
        return saver_instance

    def __getattr__(self, name):
        return getattr(self.saver, name)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.saver.get_tuple(config)

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> RunnableConfig:
        return self.saver.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str) -> None:
        return self.saver.put_writes(config, writes, task_id)

    def list(self, config: Optional[RunnableConfig], *, filter: Optional[dict] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        return self.saver.list(config, filter=filter, before=before, limit=limit)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await self.saver.aget_tuple(config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> RunnableConfig:
        return await self.saver.aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str) -> None:
        return await self.saver.aput_writes(config, writes, task_id)

    async def alist(self, config: Optional[RunnableConfig], *, filter: Optional[dict] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        async for x in self.saver.alist(config, filter=filter, before=before, limit=limit):
            yield x

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        return await self.saver.adelete_for_runs(run_ids)

    async def adelete_thread(self, thread_id: str) -> None:
        return await self.saver.adelete_thread(thread_id)

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        return await self.saver.acopy_thread(source_thread_id, target_thread_id)

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        return await self.saver.aprune(thread_ids, strategy=strategy)

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        return self.saver.delete_for_runs(run_ids)

    def delete_thread(self, thread_id: str) -> None:
        return self.saver.delete_thread(thread_id)

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        return self.saver.copy_thread(source_thread_id, target_thread_id)

    def prune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        return self.saver.prune(thread_ids, strategy=strategy)

    def get_delta_channel_history(self, *, config: RunnableConfig, channels: Sequence[str]) -> Mapping[str, Any]:
        return self.saver.get_delta_channel_history(config=config, channels=channels)

    async def aget_delta_channel_history(self, *, config: RunnableConfig, channels: Sequence[str]) -> Mapping[str, Any]:
        return await self.saver.aget_delta_channel_history(config=config, channels=channels)

    def get_next_version(self, current: Any, channel: Any) -> Any:
        return self.saver.get_next_version(current, channel)

# Global saver proxy that can be imported and compiled in the LangGraph workflow
checkpoint = AsyncPostgresSaverProxy()

def get_checkpointer() -> AsyncPostgresSaverProxy:
    """
    Returns the global checkpointer proxy.
    """
    return checkpoint

def get_db_pool():
    """
    Returns the active AsyncConnectionPool for direct PostgreSQL queries.
    """
    global pool_instance
    if pool_instance is None:
        raise RuntimeError("AsyncConnectionPool is not initialized. Ensure init_db() is called on startup.")
    return pool_instance

async def init_db():
    """
    Initializes the database connection, enters the context manager, and runs setup.
    Call this on FastAPI application startup lifespan.
    """
    global store_instance, _store_context_manager, saver_instance, _saver_context_manager, pool_instance
    
    # 1. Initialize AsyncConnectionPool for raw SQL & Tracker queries
    if pool_instance is None:
        try:
            from psycopg_pool import AsyncConnectionPool
            logger.info("📦 Initializing PostgreSQL connection pool...")
            pool_instance = AsyncConnectionPool(
                conninfo=settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                open=False
            )
            await pool_instance.open()
            logger.info("🗄️  PostgreSQL connection pool connected successfully (min=2, max=10).")
            
            # Setup tracker_items table and indices
            async with pool_instance.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        CREATE TABLE IF NOT EXISTS tracker_items (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
                            collection VARCHAR(50) NOT NULL,
                            title TEXT NOT NULL,
                            data JSONB NOT NULL DEFAULT '{}'::jsonb,
                            event_date TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );

                        CREATE INDEX IF NOT EXISTS idx_tracker_items_collection ON tracker_items(collection);
                        CREATE INDEX IF NOT EXISTS idx_tracker_items_user_coll ON tracker_items(user_id, collection);
                        CREATE INDEX IF NOT EXISTS idx_tracker_items_event_date ON tracker_items(event_date);
                        CREATE INDEX IF NOT EXISTS idx_tracker_items_data_gin ON tracker_items USING GIN (data);
                    """)
                    await conn.commit()
            logger.info("📋 Tracker database schema & indices verified (tracker_items).")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AsyncConnectionPool or tracker tables: {e}", exc_info=True)
            if pool_instance is not None:
                try:
                    await pool_instance.close()
                except Exception:
                    pass
                pool_instance = None
            raise e

    # 2. Initialize LangGraph store
    if store_instance is None:
        try:
            logger.info("🧠 Initializing LangGraph long-term memory store (AsyncPostgresStore)...")
            _store_context_manager = AsyncPostgresStore.from_conn_string(settings.DATABASE_URL)
            
            store_instance = await _store_context_manager.__aenter__()
            await store_instance.setup()
            logger.info("✅ LangGraph long-term memory store setup successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Postgres memory store: {e}", exc_info=True)
            if _store_context_manager is not None:
                try:
                    await _store_context_manager.__aexit__(None, None, None)
                except Exception:
                    pass
                _store_context_manager = None
            store_instance = None
            raise e

    # 3. Initialize LangGraph saver
    if saver_instance is None:
        try:
            logger.info("💾 Initializing LangGraph checkpoint saver (AsyncPostgresSaver)...")
            _saver_context_manager = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
            
            saver_instance = await _saver_context_manager.__aenter__()
            await saver_instance.setup()
            logger.info("✅ LangGraph checkpoint saver setup successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Postgres checkpoint saver: {e}", exc_info=True)
            if _saver_context_manager is not None:
                try:
                    await _saver_context_manager.__aexit__(None, None, None)
                except Exception:
                    pass
                _saver_context_manager = None
            saver_instance = None
            raise e

async def shutdown_db():
    """
    Exits the database context manager and releases connection pools.
    Call this on FastAPI application shutdown lifespan.
    """
    global store_instance, _store_context_manager, saver_instance, _saver_context_manager, pool_instance
    if pool_instance is not None:
        logger.info("🛑 Closing PostgreSQL connection pool...")
        try:
            await pool_instance.close()
            logger.info("🛑 PostgreSQL connection pool closed cleanly.")
        except Exception as e:
            logger.error(f"❌ Error during connection pool shutdown: {e}", exc_info=True)
        finally:
            pool_instance = None

    if _saver_context_manager is not None:
        logger.info("🛑 Exiting LangGraph AsyncPostgresSaver context manager...")
        try:
            await _saver_context_manager.__aexit__(None, None, None)
            logger.info("🛑 Database saver exited cleanly.")
        except Exception as e:
            logger.error(f"❌ Error during database saver shutdown: {e}", exc_info=True)
        finally:
            saver_instance = None
            _saver_context_manager = None

    if _store_context_manager is not None:
        logger.info("🛑 Exiting LangGraph AsyncPostgresStore context manager...")
        try:
            await _store_context_manager.__aexit__(None, None, None)
            logger.info("🛑 Database store exited cleanly.")
        except Exception as e:
            logger.error(f"❌ Error during database store shutdown: {e}", exc_info=True)
        finally:
            store_instance = None
            _store_context_manager = None


async def cleanup_expired_checkpoints(retention_hours: int = 24) -> int:
    """
    Purges checkpoints, blobs, and intermediate writes for conversation threads
    whose latest activity is older than retention_hours.
    
    Returns the number of threads purged.
    """
    if retention_hours <= 0:
        logger.info("Checkpoint auto-cleanup is disabled (retention_hours <= 0).")
        return 0

    pool = get_db_pool()
    find_expired_query = """
        SELECT thread_id
        FROM checkpoints
        GROUP BY thread_id
        HAVING MAX(
            CASE 
                WHEN checkpoint ? 'ts' THEN (checkpoint->>'ts')::timestamptz 
                ELSE NULL 
            END
        ) < NOW() - make_interval(hours => %s);
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(find_expired_query, (retention_hours,))
                rows = await cur.fetchall()
                expired_thread_ids = [row[0] for row in rows]

                if not expired_thread_ids:
                    logger.info(f"Checkpoint cleanup: No threads older than {retention_hours} hour(s) found.")
                    return 0

                logger.info(
                    f"Checkpoint cleanup: Purging {len(expired_thread_ids)} stale thread(s) inactive for >{retention_hours} hour(s)..."
                )
                await cur.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ANY(%s);",
                    (expired_thread_ids,)
                )
                await cur.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = ANY(%s);",
                    (expired_thread_ids,)
                )
                await cur.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = ANY(%s);",
                    (expired_thread_ids,)
                )
                await conn.commit()
                logger.info(
                    f"Checkpoint cleanup: Successfully purged {len(expired_thread_ids)} stale thread(s)."
                )
                return len(expired_thread_ids)
    except Exception as e:
        logger.error(f"Failed to execute checkpoint cleanup: {e}", exc_info=True)
        raise e



