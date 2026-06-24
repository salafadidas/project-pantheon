from __future__ import annotations
"""
Factory for creating and configuring LangGraph agents.

S1-NS-1: memory namespace promoted from (user_id,) to (tenant_id, user_id).
Dual-read fallback to old (user_id,) namespace is enabled during the migration
window (Sprint 1-2) and will be removed after Sprint 3 verification.
"""

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

# Heavy runtime imports — guarded so unit tests can run without
# langgraph-checkpoint-postgres / langmem / psycopg installed in sandbox.
try:
    from langgraph.graph import StateGraph
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langmem import create_manage_memory_tool
    from langgraph.prebuilt import create_react_agent
    from db.postgres_utils import create_memory_store
except ImportError:  # pragma: no cover
    StateGraph = None  # type: ignore
    AsyncPostgresSaver = None  # type: ignore
    create_manage_memory_tool = None  # type: ignore
    create_react_agent = None  # type: ignore
    create_memory_store = None  # type: ignore

from agent.prompts import MEMORY_SYSTEM_PROMPT
from llm.provider import LLMProvider
from utils.message_utils import sanitize_messages

logger = logging.getLogger(__name__)

# Module-level singleton — initialized once, shared across all agent creation
_llm_provider: Optional[LLMProvider] = None


def get_llm_provider(default_model: str = "gpt-4o-mini") -> LLMProvider:
    """Get or create the shared LLMProvider singleton."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider(default_model=default_model)
    return _llm_provider


# --------------------------------------------------------------------------- #
# Namespace helpers                                                            #
# --------------------------------------------------------------------------- #

def new_namespace(tenant_id: str, user_id: str) -> Tuple[str, str]:
    """Return the promoted namespace tuple: (tenant_id, user_id)."""
    return (str(tenant_id), str(user_id))


def legacy_namespace(user_id: str) -> Tuple[str]:
    """Return the old namespace tuple: (user_id,) — used for dual-read fallback."""
    return (str(user_id),)


async def _search_with_dual_read(
    store,
    tenant_id: str,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list:
    """Search memories with dual-read: prefer new namespace, fall back to legacy.

    S1-NS-1 dual-read strategy (MEMORY_MIGRATION_PLAN.md §3):
    - Sprint 1-2: try new namespace first, fall back to (user_id,) if empty
    - Sprint 3+: remove fallback once backfill verification is complete

    TODO(sprint-3): remove legacy fallback block when migration window closes.
    """
    ns_new = new_namespace(tenant_id, user_id)
    memories = await store.asearch(ns_new, query=query, limit=limit)

    if not memories:
        # Dual-read fallback: try old (user_id,) namespace
        ns_legacy = legacy_namespace(user_id)
        memories = await store.asearch(ns_legacy, query=query, limit=limit)
        if memories:
            logger.debug(
                "dual-read fallback hit for user %s — legacy namespace returned %d items",
                user_id, len(memories),
            )

    return memories or []


class AgentFactory:
    """Factory for creating and configuring LangGraph agents."""

    @staticmethod
    async def create_agent(
        pg_connection: str,
        pool: AsyncConnectionPool,
        llm_model: str,
        vector_dims: int,
        embed_model: str,
        user_id: str,
        tenant_id: Optional[str] = None,
    ) -> Any:
        """Initialize LangGraph agent with memory and checkpoints.

        Args:
            pg_connection: PostgreSQL connection string
            pool: Connection pool for database operations
            llm_model: LLM model identifier
            vector_dims: Dimensions of the vector embeddings
            embed_model: Name of the embedding model
            user_id: User identifier (required)
            tenant_id: Tenant identifier for promoted namespace.
                       If None, synthesized as user_id (1-user-1-tenant default,
                       per MEMORY_MIGRATION_PLAN.md §2 mapping rule).

        Returns:
            The created agent
        """
        if not user_id:
            raise ValueError("user_id is required for agent creation")

        # S1-NS-1: synthesize tenant_id if not provided.
        # Mapping rule: 1 user = 1 tenant during Sprint 1 migration.
        # Replace with real tenant lookup once S1-AUTH-2 middleware is in place.
        effective_tenant_id = tenant_id if tenant_id else str(user_id)

        ns_new = new_namespace(effective_tenant_id, user_id)
        logger.info(
            "Creating agent — user=%s tenant=%s namespace=%s",
            user_id, effective_tenant_id, ns_new,
        )

        checkpointer = AsyncPostgresSaver(pool)
        store = await create_memory_store(pg_connection, pool, vector_dims, embed_model)

        # Capture for closure
        _tenant_id = effective_tenant_id
        _user_id = user_id
        _store = store

        async def user_specific_prompt(state: Dict[str, Any]) -> list:
            """Generate system prompt with memory context (dual-read aware)."""
            try:
                memories = await _search_with_dual_read(
                    _store, _tenant_id, _user_id,
                    query=state["messages"][-1].content,
                    limit=10,
                )
                logger.info(
                    "Memory search — user=%s tenant=%s found=%d",
                    _user_id, _tenant_id, len(memories),
                )
                memory_items = []
                for item in memories:
                    try:
                        if hasattr(item, "value") and isinstance(item.value, dict):
                            content = item.value.get("content", "")
                            if content:
                                memory_items.append(f"- {content}")
                    except Exception as exc:
                        logger.error("Error processing memory item: %s", exc)
                memory_content = "\n".join(memory_items)
            except Exception as exc:
                logger.error("Error retrieving memories for user %s: %s", _user_id, exc)
                memory_content = ""

            return [
                {"role": "system",
                 "content": MEMORY_SYSTEM_PROMPT.replace("{memory_content}", memory_content)},
                *sanitize_messages(state["messages"]),
            ]

        provider = get_llm_provider(default_model=llm_model)
        chat_model = provider.get_chat_model(llm_model)

        logger.info(
            "Creating agent with LiteLLM model: %s (key=%s)",
            provider.get_litellm_model_string(llm_model),
            llm_model,
        )

        return create_react_agent(
            chat_model,
            prompt=user_specific_prompt,
            # S1-NS-1: write tool uses new namespace only
            tools=[create_manage_memory_tool(namespace=ns_new)],
            checkpointer=checkpointer,
            store=store,
        )

    @staticmethod
    async def create_advanced_graph(
        pg_connection: str,
        pool: AsyncConnectionPool,
        vector_dims: int,
        embed_model: str,
    ) -> StateGraph:
        """Placeholder for advanced graph implementation."""
        graph = StateGraph(Any)
        store = await create_memory_store(pg_connection, pool, vector_dims, embed_model)
        return graph
