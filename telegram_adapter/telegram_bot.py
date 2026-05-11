"""
Telegram-specific bot implementation.

NOTE on parse_mode:
We use ``parse_mode="HTML"`` (not legacy ``"Markdown"``) for any reply that
embeds user-controlled or external content (URLs, task text, model output).
Legacy Markdown treats ``_``, ``*``, ``[``, and backtick as syntactic, so a pasted URL like
``PLAN_v4_Master_2026-04-23.md`` triggers ``Can't parse entities: can't find
end of the entity`` and the bot replies with a literal ``?``.  HTML mode only
needs ``< > &`` escaped via :func:`html.escape`, which we apply to every
interpolated value.
"""

import asyncio
import base64
import html
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Any, Dict

import litellm
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
            CommandHandler("ping", self.handle_ping),
            CommandHandler("reset", self.handle_reset),
            CommandHandler("submit", self.handle_submit),
            CommandHandler("status", self.handle_status),
            CommandHandler("report", self.handle_report),
            CommandHandler("cancel", self.handle_cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message),
            MessageHandler(filters.PHOTO, self.handle_photo),
            # Documents/files with a /submit caption start a Pantheon session.
            # CommandHandler doesn't fire for document messages, so we need this.
            MessageHandler(filters.Document.ALL, self.handle_document),
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

    async def handle_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/ping — Check bot + Redis health."""
        redis_ok = False
        try:
            if self.redis:
                await self.redis.ping()
                redis_ok = True
        except Exception:
            pass
        redis_status = "✅ 正常" if redis_ok else "❌ 離線"
        await update.message.reply_text(
            f"🤖 Bot: ✅ 運行中\n🗄️ Redis: {redis_status}"
        )

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
        try:
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
        except Exception as exc:
            logger.error("handle_submit: Redis error for session %s: %s", session_id, exc)
            await update.message.reply_text(
                "❌ 無法建立工作階段（Redis 連線失敗），請稍後再試。"
            )
            return

        # HTML mode + html.escape() so URLs/underscores/etc. in `task` don't
        # break the parser (legacy Markdown treats _ as italic → entity error).
        await update.message.reply_text(
            (
                f"Session started!\n"
                f"ID: <code>{html.escape(session_id)}</code>\n"
                f"Task: {html.escape(task)}\n\n"
                f"Use /status {html.escape(session_id)} to check progress."
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        # Launch graph execution + phase watcher concurrently.
        # selected_models=[] → graph falls back to PHASE_MODEL_ROLES defaults.
        asyncio.create_task(_run_session(session_id, task, user_id, self.redis, []))
        asyncio.create_task(
            self._watch_session(session_id, chat_id, context.application.bot)
        )

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/status <session_id> — Check current phase."""
        args = context.args
        if not args:
            await update.message.reply_text("用法：/status <session_id>")
            return

        session_id = args[0]
        if not self.redis:
            await update.message.reply_text("Redis 無法連線。")
            return

        session = await self.redis.hgetall(_session_key(session_id))
        if not session:
            await update.message.reply_text(
                f"找不到工作階段 <code>{html.escape(session_id)}</code>，可能已過期或不存在。",
                parse_mode="HTML",
            )
            return

        status = session.get("status", "unknown")
        phase = session.get("phase") or "—"
        created_at = session.get("created_at", "")
        completed_at = session.get("completed_at", "")
        source = session.get("source", "text")
        task = session.get("task", "")
        error = session.get("error", "")

        status_emoji = {"running": "⏳", "complete": "✅", "cancelled": "🚫", "failed": "❌", "pending": "🕐"}.get(status, "❓")
        phase_emoji = {"routing": "🗺️", "research": "🔬", "debate": "💬", "voting": "🗳️", "synthesis": "📝", "complete": "✅", "cancelled": "🚫"}.get(phase, "▶️")
        source_label = "📸 圖片" if source == "photo" else "💬 文字"

        elapsed_text = ""
        if created_at:
            try:
                start = datetime.fromisoformat(created_at)
                end = datetime.fromisoformat(completed_at) if completed_at else datetime.now(timezone.utc)
                elapsed = int((end - start).total_seconds())
                mins, secs = divmod(elapsed, 60)
                elapsed_text = f"\n⏱️ 耗時：{mins}分{secs}秒" if mins else f"\n⏱️ 耗時：{secs}秒"
            except Exception:
                pass

        task_preview = (task[:120] + "...") if len(task) > 120 else task

        lines = [
            f"📋 工作階段 <code>{html.escape(session_id[:8])}...</code>",
            "",
            f"{status_emoji} 狀態：{html.escape(str(status))}",
            f"{phase_emoji} 階段：{html.escape(str(phase))}",
            f"{source_label}{elapsed_text}",
            "",
            f"📌 任務：{html.escape(task_preview)}",
            "",
            f"🕐 建立時間：{html.escape(created_at[:19] if created_at else '—')}",
        ]
        if completed_at:
            lines.append(f"🏁 完成時間：{html.escape(completed_at[:19])}")
        if error:
            lines.append(f"⚠️ 錯誤：{html.escape(str(error))}")
        if status == "complete":
            lines.append(f"\n使用 /report {html.escape(session_id)} 取得完整報告。")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="HTML", disable_web_page_preview=True
        )

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
            report = report[:4000] + "\n\n(truncated)"
        # LLM reports contain free-form Markdown that often has unbalanced
        # ``*`` / ``_`` / ``[`` — render as plain text to avoid parser errors.
        # The user gets the same content; only the styling is dropped.
        await update.message.reply_text(report, disable_web_page_preview=True)

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
        await update.message.reply_text(
            f"Session <code>{html.escape(session_id)}</code> cancelled.",
            parse_mode="HTML",
        )

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
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ Phase complete: <b>{html.escape(label)}</b>",
                        parse_mode="HTML",
                    )

                elif event_type == "session_complete":
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"🎉 Session <code>{html.escape(session_id)}</code> complete!\n"
                            f"Use /report {html.escape(session_id)} to get the full report."
                        ),
                        parse_mode="HTML",
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

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """處理用戶傳送的圖片，使用 GPT-4o Vision 分析後啟動 Pantheon 工作流程。"""
        user_id = str(update.effective_user.id)
        chat_id = update.effective_chat.id

        await update.message.reply_text("📸 收到圖片，正在分析中，請稍候...")

        try:
            photo = update.message.photo[-1]
            tg_file = await context.bot.get_file(photo.file_id)
            image_bytes: bytearray = await tg_file.download_as_bytearray()
            image_b64 = base64.b64encode(bytes(image_bytes)).decode("utf-8")

            caption = (update.message.caption or "").strip()
            if caption:
                vision_prompt = f"請詳細描述這張圖片的內容，然後針對以下問題提供分析：\n{caption}"
            else:
                vision_prompt = (
                    "請詳細描述這張圖片的所有重要內容，包括：圖片類型、主要元素、"
                    "文字（如有）、數據或圖表（如有），以及任何值得注意的細節。"
                )

            vision_response = await litellm.acompletion(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}},
                        {"type": "text", "text": vision_prompt},
                    ],
                }],
                max_tokens=1000,
            )
            image_description: str = vision_response.choices[0].message.content.strip()

            task = (
                f"【圖片分析任務】\n\n用戶問題：{caption}\n\n圖片內容分析：\n{image_description}"
                if caption else
                f"【圖片分析任務】\n\n圖片內容分析：\n{image_description}"
            )

            await update.message.reply_text(
                f"🔍 圖片分析完成！正在啟動多 AI 協作分析...\n\n"
                f"📋 分析摘要：{image_description[:200]}{'...' if len(image_description) > 200 else ''}"
            )

        except Exception as exc:
            logger.exception("圖片分析失敗：%s", exc)
            await update.message.reply_text(f"❌ 圖片分析失敗：{exc}\n請重試或使用 /submit 直接輸入文字任務。")
            return

        if not self.redis:
            await update.message.reply_text("Redis 無法連線，無法建立工作階段。")
            return

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            await self.redis.hset(_session_key(session_id), mapping={
                "session_id": session_id,
                "user_id": user_id,
                "chat_id": str(chat_id),
                "task": task,
                "status": "running",
                "phase": "routing",
                "created_at": now,
                "source": "photo",
            })
            await self.redis.expire(_session_key(session_id), SESSION_TTL)
        except Exception as exc:
            logger.error("handle_photo: Redis error for session %s: %s", session_id, exc)
            await update.message.reply_text(
                "❌ 無法建立工作階段（Redis 連線失敗），請稍後再試。"
            )
            return

        asyncio.create_task(_run_session(session_id, task, user_id, self.redis, []))
        asyncio.create_task(self._watch_session(session_id, chat_id, context.application.bot))

        await update.message.reply_text(
            f"✅ 工作階段已建立！\nID：<code>{html.escape(session_id)}</code>\n\n"
            f"使用 /status {html.escape(session_id)} 查詢進度。\n"
            f"使用 /cancel {html.escape(session_id)} 取消工作階段。",
            parse_mode="HTML",
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle file/document uploads.

        If the caption starts with /submit, download the file (text-based files
        up to 500 KB are appended to the task text) and start a Pantheon session.
        Otherwise, fall through to the general text handler.
        """
        caption = (update.message.caption or "").strip()

        # Only handle /submit captions; ignore everything else
        if not caption.lower().startswith("/submit"):
            await update.message.reply_text(
                "請使用 /submit <任務描述> 作為說明文字來提交任務。\n"
                "例如：傳送文件時，在說明欄填入 /submit 分析這份文件"
            )
            return

        # Task text = everything after "/submit"
        task_text = caption[len("/submit"):].strip()

        user_id = str(update.effective_user.id)
        chat_id = update.effective_chat.id

        if not self.redis:
            await update.message.reply_text("Redis 無法連線，無法建立工作階段。")
            return

        # Download file if it's a readable text format (≤ 500 KB)
        doc = update.message.document
        file_content: str = ""
        text_mimetypes = {
            "text/plain", "text/markdown", "text/x-markdown",
            "application/json", "text/csv", "text/html",
        }
        text_extensions = {".md", ".txt", ".json", ".csv", ".html", ".rst", ".yaml", ".yml"}
        file_name = doc.file_name or ""
        file_ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        is_text = (
            (doc.mime_type in text_mimetypes) or (file_ext in text_extensions)
        ) and (doc.file_size or 0) <= 512_000  # 500 KB cap

        await update.message.reply_text("📄 收到檔案，準備啟動 Pantheon 分析...")

        if is_text:
            try:
                tg_file = await context.bot.get_file(doc.file_id)
                raw: bytearray = await tg_file.download_as_bytearray()
                file_content = raw.decode("utf-8", errors="replace")
                logger.info("Document downloaded: %s (%d bytes)", file_name, len(raw))
            except Exception as exc:
                logger.warning("Failed to download document %s: %s", file_name, exc)

        # Build the full task — combine caption task text + file content
        if task_text and file_content:
            task = f"{task_text}\n\n--- 附件：{file_name} ---\n{file_content}"
        elif file_content:
            task = f"--- 附件：{file_name} ---\n{file_content}"
        elif task_text:
            task = task_text
        else:
            await update.message.reply_text("請在說明欄填入任務描述。")
            return

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
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
                    "source": "document",
                },
            )
            await self.redis.expire(_session_key(session_id), SESSION_TTL)
        except Exception as exc:
            logger.error("handle_document: Redis error for session %s: %s", session_id, exc)
            await update.message.reply_text(
                "❌ 無法建立工作階段（Redis 連線失敗），請稍後再試。"
            )
            return

        asyncio.create_task(_run_session(session_id, task, user_id, self.redis, []))
        asyncio.create_task(self._watch_session(session_id, chat_id, context.application.bot))

        file_note = f"（已讀取 {len(file_content):,} 字元）" if file_content else "（僅使用說明文字）"
        await update.message.reply_text(
            f"✅ 工作階段已建立！{file_note}\n"
            f"ID：<code>{html.escape(session_id)}</code>\n\n"
            f"使用 /status {html.escape(session_id)} 查詢進度。\n"
            f"使用 /cancel {html.escape(session_id)} 取消工作階段。",
            parse_mode="HTML",
        )

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
