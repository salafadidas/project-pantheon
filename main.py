"""
Main entry point for the Telegram bot + FastAPI application.
"""

import asyncio
import logging
from redis.asyncio import Redis

import uvicorn
from fastapi import FastAPI

from config.bot_config import BotConfig
from config.agent_config import AgentConfig
from db.postgres_utils import setup_database, create_memory_store
from agent.agent_factory import AgentFactory
from agent.agent_manager import AgentManager
from telegram_adapter.telegram_bot import TelegramBot
from core.exceptions import ConfigurationError
from api.v1.sessions import router as sessions_router
from api.v1.websocket import router as ws_router

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# FastAPI app                                                                  #
# --------------------------------------------------------------------------- #

app = FastAPI(title="Project Pantheon", version="1.0.0")
app.include_router(sessions_router)
app.include_router(ws_router)


# --------------------------------------------------------------------------- #
# Application entrypoint                                                       #
# --------------------------------------------------------------------------- #

async def main():
    """Main entry point: starts FastAPI (uvicorn) + Telegram bot concurrently."""
    try:
        # Load configuration
        bot_config = BotConfig()
        agent_config = AgentConfig()

        if not bot_config.telegram_token:
            raise ConfigurationError("Missing Telegram token")
        if not bot_config.pg_connection:
            raise ConfigurationError("Missing PostgreSQL connection string")

        # Setup database
        logger.info("Setting up database connection")
        pool = await setup_database(bot_config.pg_connection)

        # Create Redis connection
        logger.info(f"Connecting to Redis at {bot_config.redis_url}")
        redis = Redis.from_url(bot_config.redis_url, decode_responses=True)
        await redis.ping()

        # Store redis in FastAPI app state for API routes
        app.state.redis = redis

        # Create memory store
        logger.info("Creating memory store")
        store = await create_memory_store(
            pg_connection=agent_config.pg_connection,
            pool=pool,
            vector_dims=agent_config.vector_dims,
            embed_model=agent_config.embed_model
        )

        # Create agent factory + manager
        logger.info(f"Creating agent factory with model {agent_config.llm_model}")
        agent_factory = AgentFactory()

        logger.info("Creating agent manager")
        agent_manager = AgentManager(
            agent_factory=agent_factory,
            pg_connection=agent_config.pg_connection,
            pool=pool,
            llm_model=agent_config.llm_model,
            vector_dims=agent_config.vector_dims,
            embed_model=agent_config.embed_model,
            max_idle_time=1800,
            cleanup_interval=300
        )

        logger.info(f"Creating default agent with model {agent_config.llm_model}")
        default_agent = await agent_factory.create_agent(
            pg_connection=agent_config.pg_connection,
            pool=pool,
            llm_model=agent_config.llm_model,
            vector_dims=agent_config.vector_dims,
            embed_model=agent_config.embed_model,
            user_id="default_user"
        )

        # Create Telegram bot
        logger.info("Starting Telegram bot")
        telegram_bot = TelegramBot(redis, bot_config, default_agent, pool=pool, store=store)
        telegram_bot.message_processor.agent_manager = agent_manager
        telegram_bot.message_processor.config = agent_config
        telegram_bot.message_processor.pool = pool

        # Run FastAPI (uvicorn) and Telegram bot concurrently
        uvicorn_config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(uvicorn_config)

        await asyncio.gather(
            telegram_bot.run(),
            server.serve(),
        )

    except ConfigurationError as e:
        logger.critical(f"Configuration error: {str(e)}")
        raise
    except Exception as e:
        logger.critical(f"Application failed to start: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
        raise
