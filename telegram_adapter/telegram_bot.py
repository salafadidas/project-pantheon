"""
Telegram-specific bot implementation.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Any, Dict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from core.exceptions import RedisConnectionError
from core.message_handler import MessageProcessor, TypingIndicator
from core.utils import log_error
from config.bot_config import BotConfig
from db.user_data import clear_user_data
from api.v1.sessions import _run_session, SESSION_TTL, _session_key, _events_channel

logger = logging.getLogger(__name__)

class TelegramTypingIndicator(TypingIndicator):
    """Telegram-specific typing indicator implementation"""

    @staticmethod
    async def send_periodically(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
        """Send typing action every 5 seconds until cancelled"""
        while True:
            try:
                await context.bot.send_chat_action(
                    chat_id=chat_id,
                    action="typing"
                )
                await asyncio.sleep(5)  # Telegram requires action every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Typing indicator error: {str(e)}")
                break

    class ContextManager:
        """Context manager for continuous typing indicator"""
        def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
            self.context = context
            self.chat_id = chat_id
            self.task = None

        async def __aenter__(self):
            self.task = asyncio.create_task(
                TelegramTypingIndicator.send_periodically(self.context, self.chat_id)
            )
            return self

        async def __aexit__(self, exc_type, exc, tb):
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass

class TelegramMessageProcessor(MessageProcessor):
    """Telegram-specific message processor implementation"""

    def __init__(self, redis, agent, config: BotConfig):
        super().__init__(
            redis=redis,
            debounce_time=config.debounce_time,
            llm_calls_per_minute=config.llm_calls_per_minute
        )
        self.agent = agent
        # Store updates and contexts for each user
        self.updates: Dict[str, Update] = {}
        self.contexts: Dict[str, ContextTypes.DEFAULT_TYPE] = {}
        # Store typing indicator tasks
        self.typing_tasks: Dict[str, asyncio.Task] = {}

    async def handle_message(self, user_id: str, message_text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages
        
        Args:
            user_id: User identifier
            message_text: The message content
            update: Telegram update
            context: Telegram context
        """
        # Store update and context for this user
        self.updates[user_id] = update
        self.contexts[user_id] = context

        # Call the parent method with response and typing indicator callbacks
        await super().handle_message(
            user_id,
            message_text,
            response_callback=self.send_response,
            typing_indicator_callback=self.manage_typing_indicator
        )

    async def manage_typing_indicator(self, user_id: str, active: bool) -> None:
        """Manage typing indicator status
        
        Args:
            user_id: User identifier
            active: Whether to activate or deactivate the typing indicator
        """
        update = self.updates.get(user_id)
        context = self.contexts.get(user_id)

        if not update or not context:
            logger.warning(f"Cannot manage typing indicator: missing update or context for user {user_id}")
            return

        if active:
            # Start typing indicator if not already active
            if user_id not in self.typing_tasks or self.typing_tasks[user_id].done():
                logger.info(f"Starting typing indicator for user {user_id}")
                self.typing_tasks[user_id] = asyncio.create_task(
                    TelegramTypingIndicator.send_periodically(context, update.effective_chat.id)
                )
        else:
            # Stop typing indicator if active
            if task := self.typing_tasks.pop(user_id, None):
                logger.info(f"Stopping typing indicator for user {user_id}")
                task.cancel()
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    pass

    async def send_response(self, user_id: str, response: str) -> None:
        """Send response back to the user
        
        Args:
            user_id: User identifier
            response: Response message to send
        """
        update = self.updates.get(user_id)
        context = self.contexts.get(user_id)

        if update and context:
            try:
                # No need for typing indicator here as it's already managed by the process_messages_after_delay method
                await update.message.reply_text(response)
                logger.info(f"Response sent to user {user_id}")
            except Exception as e:
                log_error(e, {"user_id": user_id, "operation": "send_response"})
                logger.error(f"Failed to send response to user {user_id}: {str(e)}")
        else:
            logger.error(f"Cannot send response: missing update or context for user {user_id}")

    async def process_messages(self, user_id: str, messages: List[str]) -> Any:
        """Process the aggregated messages and generate a response
        
        Args:
            user_id: User identifier
            messages: List of messages to process
            
        Returns:
            The agent's response
        """
        combined = "\n".join(messages)
        try:
            # Get the agent manager from the application
            agent_manager = getattr(self, 'agent_manager', None)

            if agent_manager:
                # Get or create a user-specific agent from the manager
                user_agent = await agent_manager.get_agent(user_id)

                # Use the user-specific agent
                response = await user_agent.ainvoke(
                    {"messages": [{"role": "user", "content": combined}]},
                    config={"configurable": {"user_id": user_id, "thread_id": user_id}},
                )
            else:
                # Fall back to the shared agent if agent_manager is not available
                logger.warning(f"No agent_manager available, using shared agent for user {user_id}")
                response = await self.agent.ainvoke(
                    {"messages": [{"role": "user", "content": combined}]},
                    config={"configurable": {"user_id": user_id, "thread_id": user_id}},
                )

            return response["messages"][-1].content
        except Exception as e:
            log_error(e, {"user_id": user_id, "operation": "agent_invoke"})
            raise

class TelegramBot:
    """Telegram-specific bot implementation"""

    def __init__(self, redis, config: BotConfig, agent, pool=None, store=None):
        self.redis = redis
        self.config = config
        self.agent = agent
        self.pool = pool  # Database connection pool
        self.store = store  # Vector store
        self.message_processor = TelegramMessageProcessor(redis, agent, config)

    def create_application(self) -> Application:
        """Configure and return Telegram application"""
        if not self.config.telegram_token:
            raise ValueError("Telegram token is required")

        app = Application.builder().token(self.config.telegram_token).build()

        # Register handlers
        app.add_handlers([
            CommandHandler("start", self.handle_start),
            CommandHandler("help", self.handle_help),
            CommandHandler("reset", self.handle_reset),
            CommandHandler("submit", self.handle_submit),
            CommandHandler("status", self.handle_status),
            CommandHandler("report", self.handle_report),
            CommandHandler("cancel", self.handle_cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        ])
        app.add_error_handler(self.handle_error)

        # Setup lifecycle hooks
        app.post_init = self.setup
        app.post_shutdown = self.shutdown

        return app

    async def run(self) -> None:
        """Run the Telegram bot"""
        app = self.create_application()
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        logger.info("Telegram bot started")

        # Keep the application running
        try:
            await asyncio.Event().wait()
        finally:
            await app.stop()
            await app.shutdown()
            logger.info("Telegram bot stopped")

    async def setup(self, application: Application) -> None:
        """Initialize application dependencies"""
        application.bot_data.update({
            "agent": self.agent,
            "redis": self.redis,
            "pool": self.pool,
            "store": self.store,
            "message_processor": self.message_processor,
            "rate_limit": {
                "llm_calls_per_minute": self.config.llm_calls_per_minute,
                "window_seconds": 60
            },
            "debounce_time": self.config.debounce_time
        })

        logger.info(f"Telegram bot initialized with debounce_time={self.config.debounce_time}s, "
                    f"llm_calls_per_minute={self.config.llm_calls_per_minute}")

    async def shutdown(self, application: Application) -> None:
        """Cleanup resources on shutdown"""
        logger.info("Telegram bot shutting down")

        # Shutdown agent manager if it exists
        agent_manager = getattr(self.message_processor, 'agent_manager', None)
        if agent_manager:
            await agent_manager.shutdown()
            logger.info("Agent manager shut down")

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        await update.message.reply_text('Hello! I am your LangGraph bot. How can I help you today?')

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = (
            'Send me a message and I will respond using LangGraph and LangMem!\n\n'
            'If you send multiple messages in quick succession, I will wait and '
            'respond to all of them together. This helps me understand your complete '
            'thoughts before responding.\n\n'
            'Use /reset to clear your data and start fresh.'
        )
        await update.message.reply_text(help_text)

    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command to clear user data"""
        user_id = str(update.effective_user.id)

        # Show typing indicator while processing
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        # Get required components
        redis = self.redis
        pool = self.pool or context.bot_data.get("pool")
        store = self.store or context.bot_data.get("store")

        if not redis or not pool:
            await update.message.reply_text("Sorry, I can't reset your data right now. Please try again later.")
            return

        try:
            # Clear user data
            await clear_user_data(user_id, redis, pool, store)

            # Also remove the agent from the agent manager if it exists
            agent_manager = getattr(self.message_processor, 'agent_manager', None)
            if agent_manager:
                await agent_manager.remove_agent(user_id)
                logger.info(f"Removed agent for user {user_id} from agent manager")

            # Confirm to user
            await update.message.reply_text("Your data has been cleared. We can start fresh! 🔄")
            logger.info(f"User {user_id} reset their data")
        except Exception as e:
            log_error(e, {"user_id": user_id, "operation": "reset_data"})
            await update.message.reply_text("Sorry, I encountered an error while trying to reset your data. Please try again later.")

    # ------------------------------------------------------------------ Pantheon commands

    async def handle_submit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/submit <task> — Start a new Pantheon session."""
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /submit <your task>")
            return

        task = " ".join(args)
        user_id = str(update.effective_user.id)
        chat_id = update.effective_chat.id

        if not self.redis:
            await update.message.reply_text("Redis not available.")
            return

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.redis.hset(
            _session_key(session_id),
            mapping={
                "session_id": session_id,
                "status": "running",
                "phase": "routing",
                "task": task,
                "user_id": user_id,
                "final_report": "",
                "cost_summary": "{}",
                "created_at": now,
            },
        )
        await self.redis.expire(_session_key(session_id), SESSION_TTL)

        await update.message.reply_text(
            f"Session started!\nID: `{session_id}`\nTask: {task}\n\nUse /status {session_id} to check progress.",
            parse_mode="Markdown",
        )

        # Launch graph execution + phase watcher concurrently
        asyncio.create_task(_run_session(session_id, task, user_id, self.redis))
        asyncio.create_task(
            self._watch_session(session_id, chat_id, context.application.bot)
        )

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/status <session_id> — Check current phase."""
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /status <session_id>")
            return

        session_id = args[0]
        if not self.redis:
            await update.message.reply_text("Redis not available.")
            return

        session = await self.redis.hgetall(_session_key(session_id))
        if not session:
            await update.message.reply_text("Session not found.")
            return

        status = session.get("status", "unknown")
        phase = session.get("phase") or "—"
        await update.message.reply_text(f"Session `{session_id}`\nStatus: {status}\nPhase: {phase}", parse_mode="Markdown")

    async def handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/report <session_id> — Get the final report."""
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /report <session_id>")
            return

        session_id = args[0]
        if not self.redis:
            await update.message.reply_text("Redis not available.")
            return

        session = await self.redis.hgetall(_session_key(session_id))
        if not session:
            await update.message.reply_text("Session not found.")
            return

        if session.get("status") != "complete":
            await update.message.reply_text(f"Report not ready yet. Status: {session.get('status', 'unknown')}")
            return

        report = session.get("final_report", "")
        # Telegram messages max 4096 chars
        if len(report) > 4000:
            report = report[:4000] + "\n\n_(truncated)_"
        await update.message.reply_text(report, parse_mode="Markdown")

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/cancel <session_id> — Cancel a running session."""
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /cancel <session_id>")
            return

        session_id = args[0]
        if not self.redis:
            await update.message.reply_text("Redis not available.")
            return

        session = await self.redis.hgetall(_session_key(session_id))
        if not session:
            await update.message.reply_text("Session not found.")
            return

        from api.v1.sessions import _session_tasks
        task = _session_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

        await self.redis.hset(_session_key(session_id), "status", "cancelled")
        await self.redis.publish(
            _events_channel(session_id),
            json.dumps({"event": "session_cancelled", "timestamp": datetime.now(timezone.utc).isoformat()}),
        )
        await update.message.reply_text(f"Session `{session_id}` cancelled.", parse_mode="Markdown")

    async def _watch_session(self, session_id: str, chat_id: int, bot) -> None:
        """Subscribe to session events and forward phase updates to Telegram."""
        channel = _events_channel(session_id)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        _PHASE_LABELS = {
            "routing": "PM Router",
            "research": "Researcher",
            "debate": "Debater",
            "voting": "Voter",
            "synthesis": "Synthesizer",
        }
        _TERMINAL = {"session_complete", "session_cancelled", "session_error"}

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                raw = message["data"]
                text = raw if isinstance(raw, str) else raw.decode()
                try:
                    event = json.loads(text)
                except Exception:
                    continue

                event_type = event.get("event", "")

                if event_type == "phase_complete":
                    phase = event.get("phase", "")
                    label = _PHASE_LABELS.get(phase, phase.title())
                    await bot.send_message(chat_id=chat_id, text=f"✅ Phase complete: *{label}*", parse_mode="Markdown")

                elif event_type == "session_complete":
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"🎉 Session `{session_id}` complete!\nUse /report {session_id} to get the full report.",
                        parse_mode="Markdown",
                    )
                    break

                elif event_type == "session_error":
                    err = event.get("error", "unknown error")
                    await bot.send_message(chat_id=chat_id, text=f"❌ Session error: {err}")
                    break

                elif event_type == "session_cancelled":
                    break

                if event_type in _TERMINAL:
                    break
        except Exception as exc:
            logger.error("Session watcher error for %s: %s", session_id, exc)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors"""
        logger.error(f"Update {update} caused error {context.error}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages"""
        user_id = str(update.effective_user.id)
        message_text = update.message.text

        if not self.redis:
            logger.error("Redis connection not available")
            await update.message.reply_text(
                "I'm having trouble connecting to my memory. Please try again in a moment."
            )
            return

        try:
            # Pass update and context to the message processor
            await self.message_processor.handle_message(user_id, message_text, update, context)
        except RedisConnectionError:
            await update.message.reply_text(
                "I'm having trouble remembering your message. Please try again in a moment."
            )
        except Exception as e:
            log_error(e, {"user_id": user_id, "operation": "handle_message"})
            await update.message.reply_text(
                "I encountered an unexpected issue. Please try again in a moment."
            )
