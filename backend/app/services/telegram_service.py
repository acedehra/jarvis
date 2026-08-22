import asyncio
import logging
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from langchain_core.messages import HumanMessage, AIMessage
from app.core.config import settings

logger = logging.getLogger("telegram_service")


def is_valid_chat_id(chat_id: Optional[str]) -> bool:
    """
    Validate that a chat ID is non-empty, not a default placeholder,
    and represents a valid numeric integer (positive or negative).
    """
    if not chat_id:
        return False
    val = str(chat_id).strip()
    if not val or val.startswith("your_") or val == "your_telegram_chat_id_here":
        return False
    try:
        int(val)
        return True
    except ValueError:
        return False


class TelegramBotService:
    """
    Service managing two-way Telegram Bot communication with the LangGraph Jarvis agent.
    """

    def __init__(self):
        self.application: Optional[Application] = None
        self._is_running: bool = False
        self.last_error: Optional[str] = None
        self.voice_sessions: set[int] = set()

    def is_authorized(self, chat_id: int) -> bool:
        """
        Check if the incoming chat ID matches TELEGRAM_CHAT_ID.
        Strictly denies access if TELEGRAM_CHAT_ID is missing, invalid, or does not match.
        """
        configured_id = settings.TELEGRAM_CHAT_ID
        if not is_valid_chat_id(configured_id):
            return False
        return str(chat_id).strip() == str(configured_id).strip()

    async def start(self):
        """
        Initializes and starts the Telegram Bot polling in the background.
        Fails gracefully without halting application startup if credentials are missing or invalid.
        Requires both a valid TELEGRAM_BOT_TOKEN and a valid TELEGRAM_CHAT_ID to start polling.
        """
        self.last_error = None
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token.strip().startswith("your_"):
            self.last_error = "TELEGRAM_BOT_TOKEN is not configured."
            logger.info("ℹ️ Telegram Bot: No valid TELEGRAM_BOT_TOKEN configured. Telegram bot listener is DISABLED.")
            return

        chat_id = settings.TELEGRAM_CHAT_ID
        if not is_valid_chat_id(chat_id):
            self.last_error = (
                f"TELEGRAM_CHAT_ID is missing or invalid ({chat_id!r}). "
                "Telegram bot polling is DISABLED for security. Please set a valid numeric TELEGRAM_CHAT_ID in .env."
            )
            logger.error(f"❌ Telegram Bot: {self.last_error}")
            return

        try:
            logger.info("Initializing Telegram Bot...")
            self.application = Application.builder().token(token.strip()).build()
            await self.application.initialize()

            # Verify connection with Telegram API
            me = await self.application.bot.get_me()
            logger.info(f"✅ Telegram Bot connected successfully as @{me.username} (ID: {me.id}).")
            logger.info(f"🔒 Telegram Bot is restricted to Chat ID: {chat_id}")

            # Register Command & Message Handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("reset", self._handle_reset))
            self.application.add_handler(CommandHandler("status", self._handle_status))
            self.application.add_handler(CommandHandler("voice", self._handle_voice_toggle))
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            self.application.add_handler(
                MessageHandler(filters.VOICE, self._handle_incoming_voice)
            )

            # Start Polling
            await self.application.updater.start_polling(drop_pending_updates=True)
            await self.application.start()
            self._is_running = True
            logger.info(f"🚀 Telegram Bot is ACTIVE and listening for incoming messages as @{me.username}.")

        except Exception as e:
            self.last_error = str(e)
            logger.warning(
                f"⚠️ Telegram Bot failed to start: {e}. "
                f"The Jarvis backend will continue running normally without Telegram integration."
            )
            if self.application:
                try:
                    await self.application.shutdown()
                except Exception:
                    pass
                self.application = None
            self._is_running = False

    async def stop(self):
        """
        Gracefully halts polling and shuts down the Telegram Bot.
        """
        if not self.application or not self._is_running:
            return

        logger.info("Shutting down Telegram Bot...")
        try:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            if self.application.running:
                await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram Bot shut down cleanly.")
        except Exception as e:
            logger.error(f"Error during Telegram Bot shutdown: {e}")
        finally:
            self._is_running = False
            self.application = None

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            await update.message.reply_text(
                f"⛔ Access Denied.\nThis Jarvis instance is private.\nYour Telegram Chat ID is: `{chat_id}`",
                parse_mode="Markdown"
            )
            return

        welcome_text = (
            "👋 *Hello! I am J.A.R.V.I.S., your AI Assistant.*\n\n"
            "You can talk to me directly here, and I will remember our context and manage your tracker database.\n\n"
            "💡 *Things you can do:*\n"
            "• *Log Fuel / Gas:* _'Filled 12 gal for $45 at Shell, odometer 54,200'_\n"
            "• *Log Expenses:* _'Spent $14.50 on lunch at Chipotle'_\n"
            "• *Run Calculations:* _'How much did I spend on gas / food this month?'_\n"
            "• *To-Do Lists:* _'Add finish documentation to my todo list'_\n"
            "• *Reminders:* _'Remind me tomorrow at 9am to check server logs'_\n"
            "• *Bookmarks:* _'Save this link: https://github.com/langchain-ai'_\n\n"
            f"🆔 *Your Chat ID:* `{chat_id}`\n"
            "Use /help for more commands."
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            return

        help_text = (
            "🛠 *Jarvis Telegram Bot Commands:*\n\n"
            "• `/start` - Introduction and Chat ID\n"
            "• `/help` - Show this guide\n"
            "• `/reset` - Clear current conversation thread memory\n"
            "• `/status` - Check assistant and tracking system status\n"
            "• `/voice` - Toggle audio voice note replies on/off\n\n"
            "📝 *Tracking & Math Examples:*\n"
            "• _'Filled up 11.5 gal of gas for $42 at Shell'_\n"
            "• _'How much did I spend on gas this month?'_\n"
            "• _'Spent $45 on groceries'_\n"
            "• _'Show my expenses this week'_\n"
            "• _'What is my total spending by category?'_\n"
            "• _'What pending tasks do I have?'_\n"
            "• _'Mark task #1 as completed'_"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def _handle_voice_toggle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            return

        if chat_id in self.voice_sessions:
            self.voice_sessions.remove(chat_id)
            await update.message.reply_text("🔇 *Voice replies disabled.* J.A.R.V.I.S. will reply with text messages.", parse_mode="Markdown")
        else:
            self.voice_sessions.add(chat_id)
            await update.message.reply_text(
                "🎙️ *Voice replies enabled.* J.A.R.V.I.S. will now transmit spoken audio notes with responses.\n"
                f"Using British voice: `{settings.TTS_VOICE}`.",
                parse_mode="Markdown"
            )

    async def _handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            return

        session_id = f"telegram_{chat_id}"
        try:
            from app.core.database import get_checkpointer
            saver = get_checkpointer()
            await saver.adelete_thread(session_id)
            await update.message.reply_text("🧹 Conversation memory for this Telegram chat has been reset.")
        except Exception as e:
            logger.error(f"Error resetting session '{session_id}': {e}")
            await update.message.reply_text("🧹 Conversation context reset.")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            return

        try:
            from app.services.tracker import get_collections_summary
            from app.services.tools import tools as builtin_tools, TOOL_METADATA
            from app.services.mcp import mcp_manager
            from app.services.tts_service import check_tts_health

            summary = await get_collections_summary()
            summary_lines = []
            for s in summary:
                summary_lines.append(f"• *{s['collection'].capitalize()}:* {s['count']} items")

            tool_lines = []
            for t in builtin_tools:
                meta = TOOL_METADATA.get(t.name, {"emoji": "🔧", "description": t.name})
                tool_lines.append(f"• {meta['emoji']} `{t.name}`")

            mcp_tools = mcp_manager.get_tools()
            for mt in mcp_tools:
                tool_lines.append(f"• 🔌 `{mt.name}`")

            tts_health = await check_tts_health()
            tts_status_label = "Online 🟢" if tts_health.get("status") == "connected" else f"Offline 🔴 ({tts_health.get('error', 'unreachable')})"
            voice_enabled_label = "Active 🎙️" if (chat_id in self.voice_sessions or settings.TELEGRAM_VOICE_REPLY) else "Off 🔇 (/voice to toggle)"

            status_text = (
                "🤖 *J.A.R.V.I.S. System Status*\n\n"
                "• *Status:* Online & Active 🟢\n"
                f"• *Default Provider:* `{settings.DEFAULT_PROVIDER}`\n"
                f"• *Kokoro TTS Service:* {tts_status_label}\n"
                f"• *Voice Replies:* {voice_enabled_label}\n"
                f"• *Available Tools ({len(builtin_tools) + len(mcp_tools)}):*\n" +
                ("\n".join(tool_lines) if tool_lines else "• _No tools registered._") +
                "\n\n📊 *Tracked Database Records:*\n" +
                ("\n".join(summary_lines) if summary_lines else "• _No records saved yet._")
            )
            await update.message.reply_text(status_text, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"Status: Online 🟢 (Failed to fetch details: {e})")

    async def _handle_incoming_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handles incoming voice messages by informing the user and encouraging text or voice mode.
        """
        if not update.message:
            return
        chat_id = update.effective_chat.id
        if not self.is_authorized(chat_id):
            return

        await update.message.reply_text(
            "🎙️ *Voice Note Received.* For optimal transcription accuracy with current tools, please send text instructions or enable voice replies via `/voice`.",
            parse_mode="Markdown"
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_text = update.message.text.strip()

        if not self.is_authorized(chat_id):
            await update.message.reply_text(
                f"⛔ Access Denied.\nYour Chat ID `{chat_id}` is not authorized.\n"
                f"Set `TELEGRAM_CHAT_ID={chat_id}` in your backend `.env` to enable access.",
                parse_mode="Markdown"
            )
            return

        session_id = f"telegram_{chat_id}"
        logger.info(f"Telegram message received from chat {chat_id}: '{user_text}'")

        # Indicate typing status in Telegram
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass

        try:
            from app.services.graph import graph
            from app.services.memory_reflection import extract_memories_async

            config = {"configurable": {"thread_id": session_id}}
            inputs = {
                "messages": [HumanMessage(content=user_text)],
                "provider": settings.DEFAULT_PROVIDER,
                "model": None,
            }

            # Invoke the LangGraph agent
            result = await graph.ainvoke(inputs, config=config)
            
            # Extract final AI response
            bot_reply = ""
            messages = result.get("messages", [])
            for m in reversed(messages):
                if isinstance(m, AIMessage) and m.content:
                    if isinstance(m.content, str):
                        bot_reply = m.content
                    elif isinstance(m.content, list):
                        parts = []
                        for p in m.content:
                            if isinstance(p, str):
                                parts.append(p)
                            elif isinstance(p, dict):
                                parts.append(p.get("text", ""))
                        bot_reply = "".join(parts)
                    break

            if not bot_reply:
                bot_reply = "I processed your request, but had no text output to display."

            # Send text reply to Telegram (try markdown first, fall back to plain text if markdown formatting errors)
            try:
                await update.message.reply_text(bot_reply, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(bot_reply)

            # Check if voice replies are enabled globally or for this chat session
            is_voice_enabled = settings.TELEGRAM_VOICE_REPLY or (chat_id in self.voice_sessions)
            if is_voice_enabled and bot_reply:
                try:
                    import io
                    from app.services.tts_service import generate_speech
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
                    audio_bytes = await generate_speech(bot_reply)
                    if audio_bytes:
                        audio_stream = io.BytesIO(audio_bytes)
                        audio_stream.name = "jarvis_voice.mp3"
                        await update.message.reply_voice(
                            voice=audio_stream,
                            caption="🎙️ J.A.R.V.I.S."
                        )
                except Exception as tts_err:
                    logger.warning(f"Failed to generate Telegram voice reply: {tts_err}")

            # Trigger long-term memory reflection asynchronously in the background
            asyncio.create_task(extract_memories_async(messages, user_id="default_user"))

        except Exception as e:
            logger.error(f"Error processing Telegram message: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Sorry, an error occurred while processing your request: {str(e)}")


telegram_bot = TelegramBotService()
