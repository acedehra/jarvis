import logging
import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.core.config import settings
from app.core.auth import init_api_key, APIKeyAuthMiddleware, verify_ws_auth, get_api_key, get_active_api_key
from app.services.graph import graph
from app.core.database import init_db, get_store, check_database_health
from app.services.memory_reflection import extract_memories_async

logging.basicConfig(level=logging.INFO)
# Suppress noisy HTTP request polling logs from Telegram bot / httpx / httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("main")

async def reminder_worker():
    """
    Background worker that runs every 30 seconds to check for due reminders
    and dispatches Telegram notifications to the user.
    """
    from app.services.tracker import get_due_reminders, mark_reminder_dispatched
    from app.services.tools import send_telegram_message
    
    logger.info("⏰ Reminder background worker started (interval: 30s).")
    while True:
        try:
            await asyncio.sleep(30)
            due = await get_due_reminders()
            for item in due:
                title = item.get("title", "Reminder")
                data = item.get("data", {})
                notes = data.get("notes") or data.get("description", "")
                msg_body = f"⏰ REMINDER: {title}"
                if notes:
                    msg_body += f"\nDetails: {notes}"
                
                logger.info(f"⏰ Dispatching reminder '{title}' (ID: {item['id']})...")
                try:
                    await send_telegram_message.ainvoke({"message": msg_body})
                    await mark_reminder_dispatched(item["id"])
                    logger.info(f"✅ Reminder '{item['id']}' marked as dispatched.")
                except Exception as e:
                    logger.error(f"❌ Failed to dispatch reminder {item['id']}: {e}")
        except asyncio.CancelledError:
            logger.info("🛑 Reminder background worker cancelled.")
            break
        except Exception as e:
            logger.error(f"❌ Error in reminder worker loop: {e}")

async def expiry_worker():
    """
    Background worker that periodically scans the pantry for items near their expiry date
    and pushes a Telegram alert so food doesn't go to waste. Runs on the same cadence as
    the reminder worker and deduplicates via data.expiry_alerted so an item alerts once.
    """
    from app.services.pantry import get_expiring_items, mark_expiry_alerted
    from app.services.tools import send_telegram_message

    within_days = getattr(settings, "PANTRY_EXPIRY_ALERT_DAYS", 2)
    logger.info(f"🥫 Expiry background worker started (interval: 30s, alerts within {within_days}d).")
    while True:
        try:
            await asyncio.sleep(30)
            expiring = await get_expiring_items(within_days=within_days, include_expired=True)
            stale = [e for e in expiring if not e["alerted"]]
            if not stale:
                continue
            lines = ["🥫 PANTRY EXPIRY ALERT — please use these up:"]
            for item in stale:
                days = item["days_to_expiry"]
                when = f"expired {abs(days)}d ago" if days < 0 else (f"expires in {days}d" if days == 0 else f"expires in {days} day(s)")
                lines.append(
                    f"• {item['name']}: {item['quantity']} {item['unit']} ({when}, {item.get('expiry')})"
                )
            msg = "\n".join(lines)
            try:
                await send_telegram_message.ainvoke({"message": msg})
                for item in stale:
                    await mark_expiry_alerted(item["id"])
                logger.info(f"🥫 Dispatched expiry alert for {len(stale)} item(s).")
            except Exception as e:
                logger.error(f"❌ Failed to dispatch expiry alert: {e}")
        except asyncio.CancelledError:
            logger.info("🛑 Expiry background worker cancelled.")
            break
        except Exception as e:
            logger.error(f"❌ Error in expiry worker loop: {e}")

async def checkpoint_cleanup_worker():
    """
    Background worker that runs periodically to purge stale checkpoints, blobs,
    and writes older than settings.CHECKPOINT_RETENTION_HOURS.
    """
    from app.core.database import cleanup_expired_checkpoints

    if settings.CHECKPOINT_RETENTION_HOURS <= 0:
        logger.info("ℹ️ Checkpoint retention auto-cleanup is disabled (CHECKPOINT_RETENTION_HOURS <= 0).")
        return

    logger.info(
        f"🧹 Checkpoint cleanup worker started (retention: {settings.CHECKPOINT_RETENTION_HOURS}h, "
        f"interval: {settings.CHECKPOINT_CLEANUP_INTERVAL_HOURS}h)."
    )

    # Initial cleanup run 30 seconds after server startup
    await asyncio.sleep(30)

    while True:
        try:
            cleaned = await cleanup_expired_checkpoints(settings.CHECKPOINT_RETENTION_HOURS)
            if cleaned > 0:
                logger.info(f"🧹 Periodic checkpoint cleanup completed: {cleaned} stale thread(s) purged.")
            await asyncio.sleep(settings.CHECKPOINT_CLEANUP_INTERVAL_HOURS * 3600)
        except asyncio.CancelledError:
            logger.info("🛑 Checkpoint cleanup worker cancelled.")
            break
        except Exception as e:
            logger.error(f"❌ Error in checkpoint cleanup worker: {e}", exc_info=True)
            # Sleep 1 hour before retrying on error to avoid tight error loop
            await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.llm import get_default_model_name
    active_model = get_default_model_name()
    logger.info("==========================================================")
    logger.info("🤖 Starting J.A.R.V.I.S. AI Assistant Backend...")
    logger.info(f"⚙️  Default Provider: {settings.DEFAULT_PROVIDER} | Active Model: {active_model}")
    logger.info(f"🌐 User Timezone: {settings.USER_TIMEZONE}")
    logger.info("==========================================================")

    # 0. API Key Authentication Initialization
    init_api_key()

    # 1. Database Initialization
    logger.info("📦 Initializing database and memory storage...")
    try:
        await init_db()
        logger.info("✅ Database and storage layers initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Startup database initialization failed: {e}")
    
    # 2. Built-in Tools Loading & Logging
    from app.services.tools import log_builtin_tools, tools as builtin_tools
    log_builtin_tools(logger)

    # 3. MCP Servers & Dynamic Tools
    logger.info("🔌 Initializing Model Context Protocol (MCP) servers...")
    try:
        from app.services.mcp import mcp_manager
        await mcp_manager.start()
        mcp_tools = mcp_manager.get_tools()
        if mcp_tools:
            logger.info(f"✅ Loaded {len(mcp_tools)} dynamic MCP tool(s).")
        else:
            logger.info("ℹ️  No active MCP tools loaded.")
    except Exception as e:
        logger.error(f"❌ Failed to start MCP manager: {e}")

    # 4. Start Telegram Bot listener (fails gracefully if token is absent/invalid)
    try:
        from app.services.telegram_service import telegram_bot
        await telegram_bot.start()
    except Exception as e:
        logger.warning(f"⚠️ Telegram bot could not be started: {e}. Backend will continue running.")

    # 5. Kokoro Text-to-Speech (TTS) Service Probe & Logging
    logger.info(f"🎙️  Checking Kokoro TTS service ({settings.TTS_VOICE} @ {settings.TTS_BASE_URL})...")
    try:
        from app.services.tts_service import check_tts_health
        tts_status = await check_tts_health()
        if tts_status.get("status") == "connected":
            logger.info(f"✅ Kokoro TTS is ACTIVE and ready (Default Voice: '{settings.TTS_VOICE}', Speed: {settings.TTS_SPEED}x).")
        else:
            logger.info(
                f"ℹ️  Kokoro TTS is offline or unreachable at {settings.TTS_BASE_URL} ({tts_status.get('error', 'unreachable')}). "
                "Voice synthesis will activate once the 'tts' container or Kokoro service is running."
            )
    except Exception as e:
        logger.warning(f"⚠️  Kokoro TTS service check encountered an issue: {e}")

    # 6. Background Workers
    reminder_task = asyncio.create_task(reminder_worker())
    expiry_task = asyncio.create_task(expiry_worker())
    cleanup_task = asyncio.create_task(checkpoint_cleanup_worker())

    from app.services.mcp import mcp_manager
    total_tools = len(builtin_tools) + len(mcp_manager.get_tools())
    logger.info("==========================================================")
    logger.info(f"🚀 J.A.R.V.I.S. is ONLINE and ready! ({total_tools} total tools available | Voice: '{settings.TTS_VOICE}')")
    logger.info("==========================================================")

    yield

    logger.info("🛑 Shutting down Telegram Bot...")
    try:
        from app.services.telegram_service import telegram_bot
        await telegram_bot.stop()
    except Exception as e:
        logger.error(f"❌ Failed to stop Telegram Bot: {e}")

    logger.info("🛑 Shutting down background workers...")
    reminder_task.cancel()
    expiry_task.cancel()
    cleanup_task.cancel()
    for task in [reminder_task, expiry_task, cleanup_task]:
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("🛑 Shutting down MCP manager and database connections...")
    try:
        from app.services.mcp import mcp_manager
        await mcp_manager.stop()
    except Exception as e:
        logger.error(f"❌ Failed to shutdown MCP manager: {e}")

    try:
        from app.core.database import shutdown_db
        await shutdown_db()
    except Exception as e:
        logger.error(f"❌ Failed to shutdown database store: {e}")

    logger.info("👋 J.A.R.V.I.S. backend shutdown complete.")

app = FastAPI(
    title="Jarvis API",
    description="Production-ready FastAPI backend for the Jarvis AI Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure API Key Authentication Middleware (protects all /api/* routes)
app.add_middleware(APIKeyAuthMiddleware)

# Configure CORS Middleware
# Allows requests from configured origins (default: all origins "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.mcp_routes import router as mcp_router
app.include_router(mcp_router, prefix="/api/mcp", tags=["MCP"], dependencies=[Depends(get_api_key)])

from app.api.tracker_routes import router as tracker_router
app.include_router(tracker_router, prefix="/api/tracker", tags=["Tracker"], dependencies=[Depends(get_api_key)])

from app.api.telegram_routes import router as telegram_router
app.include_router(telegram_router, prefix="/api/telegram", tags=["Telegram"], dependencies=[Depends(get_api_key)])

from app.api.tts_routes import router as tts_router
app.include_router(tts_router, prefix="/api/tts", tags=["TTS"], dependencies=[Depends(get_api_key)])



@app.get("/api/health", tags=["Health"])
async def health_check(response: Response):
    """
    Public health check endpoint.
    Performs live database connectivity check (which determines overall service health).
    Provides informational status of Telegram bot, MCP servers, Authentication, and LLM providers.
    All keys and secret tokens are strictly masked / omitted.
    """
    # 1. Database Connectivity Probe (Critical - failure causes overall 503)
    db_health = await check_database_health()
    db_connected = db_health.get("status") == "connected"

    # 2. Telegram Status (Informational)
    from app.services.telegram_service import telegram_bot, is_valid_chat_id
    has_telegram_token = bool(settings.TELEGRAM_BOT_TOKEN and not settings.TELEGRAM_BOT_TOKEN.startswith("your_"))
    is_chat_id_valid = is_valid_chat_id(settings.TELEGRAM_CHAT_ID)
    telegram_bot_username = None
    if telegram_bot.application and telegram_bot.application.bot:
        try:
            telegram_bot_username = getattr(telegram_bot.application.bot, "username", None)
        except Exception:
            pass

    if not has_telegram_token:
        telegram_status_str = "not_configured"
    elif not is_chat_id_valid:
        telegram_status_str = "missing_chat_id"
    elif telegram_bot._is_running:
        telegram_status_str = "running"
    else:
        telegram_status_str = "stopped"

    telegram_info = {
        "status": telegram_status_str,
        "is_active": telegram_bot._is_running,
        "bot_username": telegram_bot_username,
        "token_configured": has_telegram_token,
        "chat_id_configured": bool(settings.TELEGRAM_CHAT_ID),
        "chat_id_valid": is_chat_id_valid,
        "error": telegram_bot.last_error,
    }

    # 3. MCP Servers & Tools Status (Informational)
    from app.services.mcp import mcp_manager
    try:
        servers_status = mcp_manager.get_servers_status()
        sanitized_servers = {}
        connected_count = 0
        for s_name, s_info in servers_status.items():
            is_conn = s_info.get("status") == "connected"
            if is_conn:
                connected_count += 1
            sanitized_servers[s_name] = {
                "status": s_info.get("status", "disconnected"),
                "error": s_info.get("error"),
                "tools_count": len(s_info.get("tools", [])),
            }

        if not sanitized_servers:
            mcp_status_str = "none"
        elif connected_count == len(sanitized_servers):
            mcp_status_str = "connected"
        elif connected_count > 0:
            mcp_status_str = "degraded"
        else:
            mcp_status_str = "disconnected"

        mcp_info = {
            "status": mcp_status_str,
            "total_servers": len(sanitized_servers),
            "connected_servers": connected_count,
            "total_tools": len(mcp_manager.get_tools()),
            "servers": sanitized_servers,
        }
    except Exception as e:
        mcp_info = {
            "status": "error",
            "total_servers": 0,
            "connected_servers": 0,
            "total_tools": 0,
            "error": str(e),
            "servers": {},
        }

    # 4. Authentication Status (Informational - never reveals active API key)
    auth_info = {
        "enabled": settings.API_KEY_AUTH_ENABLED,
        "auth_type": "api_key",
        "key_configured": bool(get_active_api_key()) if settings.API_KEY_AUTH_ENABLED else False,
    }

    # 5. LLM Providers Status (Informational - booleans only, no tokens)
    configured_providers = []
    if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("your_"):
        configured_providers.append("gemini")
    if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
        configured_providers.append("openai")
    if settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("your_"):
        configured_providers.append("anthropic")
    if settings.OPENROUTER_API_KEY and not settings.OPENROUTER_API_KEY.startswith("your_"):
        configured_providers.append("openrouter")
    if settings.TAVILY_API_KEY and not settings.TAVILY_API_KEY.startswith("your_"):
        configured_providers.append("tavily")

    llm_info = {
        "default_provider": settings.DEFAULT_PROVIDER,
        "configured_providers": configured_providers,
    }

    # 6. Kokoro TTS Service Status (Informational)
    from app.services.tts_service import check_tts_health
    tts_info = await check_tts_health()

    # 7. Set response status code based strictly on critical database probe
    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unhealthy"
    else:
        response.status_code = status.HTTP_200_OK
        overall_status = "healthy"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": db_health,
            "authentication": auth_info,
            "telegram": telegram_info,
            "tts": tts_info,
            "mcp": mcp_info,
            "llm_providers": llm_info,
        }
    }


@app.get("/api/auth/verify", tags=["Auth"], dependencies=[Depends(get_api_key)])
async def verify_auth():
    """
    Endpoint to verify API key validity for frontend sessions.
    Requires valid API key.
    """
    return {
        "status": "authenticated",
        "valid": True,
    }


@app.get("/api/models", tags=["LLM"], dependencies=[Depends(get_api_key)])
async def get_models():
    """
    Returns system default provider, system default model, and available providers/models
    with their configured API key status.
    """
    from app.services.llm import get_available_models_info
    return get_available_models_info()


@app.get("/api/memories", tags=["Memories"], dependencies=[Depends(get_api_key)])
async def get_memories(user_id: str = "default_user"):
    """
    Retrieve all long-term memory facts stored for the user.
    """
    try:
        store = get_store()
        items = await store.asearch(("memories", user_id))
        return [{"key": item.key, "fact": item.value.get("fact")} for item in items]
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        return []


@app.delete("/api/memories/{key}", tags=["Memories"], dependencies=[Depends(get_api_key)])
async def delete_memory(key: str, user_id: str = "default_user"):
    """
    Delete a specific long-term memory key for the user.
    """
    try:
        store = get_store()
        await store.adelete(("memories", user_id), key)
        return {"status": "success", "message": f"Memory '{key}' deleted."}
    except Exception as e:
        logger.error(f"Error deleting memory '{key}': {e}")
        return {"status": "error", "message": str(e)}


@app.delete("/api/chat/sessions/{session_id}", tags=["Chat"], dependencies=[Depends(get_api_key)])
async def delete_chat_session(session_id: str):
    """
    Delete the short-term memory (checkpoint) of a specific chat session.
    """
    try:
        from app.core.database import get_checkpointer
        saver = get_checkpointer()
        await saver.adelete_thread(session_id)
        return {"status": "success", "message": f"Session '{session_id}' memory deleted."}
    except Exception as e:
        logger.error(f"Error deleting session '{session_id}': {e}")
        return {"status": "error", "message": str(e)}

async def stream_graph_events(event_generator, websocket: WebSocket, total_tokens: dict = None):
    async for event in event_generator:
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            # Only stream tokens from the main "agent" node to prevent summary model text from streaming.
            node = event.get("metadata", {}).get("langgraph_node")
            if node != "agent":
                continue
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                content = chunk.content
                text_to_send = ""
                if isinstance(content, str):
                    text_to_send = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, str):
                            text_to_send += part
                        elif isinstance(part, dict):
                            text_to_send += part.get("text", "")
                elif isinstance(content, dict):
                    text_to_send = content.get("text", "")
                
                if text_to_send:
                    await websocket.send_json({
                        "type": "chunk",
                        "text": text_to_send
                    })
        elif kind == "on_chat_model_end":
            if total_tokens is not None:
                output = event["data"].get("output")
                if output and hasattr(output, "usage_metadata") and output.usage_metadata:
                    meta = output.usage_metadata
                    total_tokens["input_tokens"] += meta.get("input_tokens", 0)
                    total_tokens["output_tokens"] += meta.get("output_tokens", 0)
                    total_tokens["total_tokens"] += meta.get("total_tokens", 0)
        elif kind == "on_tool_start":
            tool_name = event.get("name")
            tool_input = event.get("data", {}).get("input")
            await websocket.send_json({
                "type": "tool_start",
                "name": tool_name,
                "input": tool_input
            })
        elif kind == "on_tool_end":
            tool_name = event.get("name")
            tool_output = event.get("data", {}).get("output")
            await websocket.send_json({
                "type": "tool_end",
                "name": tool_name,
                "output": str(tool_output)
            })


@app.websocket("/api/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """
    WebSocket endpoint for bidirectional agent chat streaming using Langgraph.
    """
    if not await verify_ws_auth(websocket, query_api_key=api_key):
        await websocket.close(code=1008, reason="Invalid or missing API key")
        return

    await websocket.accept()
    logger.info(f"WebSocket connection established. Query session_id: {session_id}")
    
    # Generate or reuse the session thread ID
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"No session_id provided, generated: {session_id}")
    else:
        logger.info(f"Using session thread ID: {session_id}")
    
    try:
        while True:
            # Receive message from client
            raw_data = await websocket.receive_text()
            logger.info(f"Received raw data from client: {raw_data}")
            
            # Default options
            message_text = raw_data
            provider = settings.DEFAULT_PROVIDER
            model = None
            
            # Try parsing as JSON to extract LLM provider and model options
            try:
                data = json.loads(raw_data)
                if isinstance(data, dict):
                    message_text = data.get("text", raw_data)
                    provider = data.get("provider") or settings.DEFAULT_PROVIDER
                    model = data.get("model") or None
            except json.JSONDecodeError:
                # Fall back to treating it as plain text message
                pass
                
            if not message_text.strip():
                continue
                
            logger.info(f"Processing message: '{message_text}' using {provider} ({model or 'default'})")
            
            config = {"configurable": {"thread_id": session_id}}
            inputs = {
                "messages": [HumanMessage(content=message_text)],
                "provider": provider,
                "model": model,
            }
            
            total_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            
            try:
                # 1. Run the initial step of the graph
                await stream_graph_events(
                    graph.astream_events(inputs, config=config, version="v2"),
                    websocket,
                    total_tokens
                )

                # 2. Check if we reached an interrupt
                state = await graph.aget_state(config)
                if state.next and state.next[0] == "sensitive_tools":
                    last_message = state.values["messages"][-1]
                    tool_calls = getattr(last_message, "tool_calls", [])
                    
                    # Notify client that confirmation is required
                    await websocket.send_json({
                        "type": "sensitive_tool_approval_required",
                        "tool_calls": tool_calls
                    })
                    
                    # Wait for user input/decision
                    raw_data = await websocket.receive_text()
                    try:
                        decision = json.loads(raw_data)
                    except json.JSONDecodeError:
                        decision = {"action": "reject"}  # Fallback
                    
                    action = decision.get("action")
                    
                    if action == "approve":
                        # Resume graph execution as-is
                        await stream_graph_events(
                            graph.astream_events(None, config=config, version="v2"),
                            websocket,
                            total_tokens
                        )
                    elif action == "reject":
                        # Resume with a tool message rejection
                        rejections = [
                            ToolMessage(
                                content="Tool execution rejected by user.",
                                tool_call_id=tc["id"],
                                name=tc["name"]
                            ) for tc in tool_calls
                        ]
                        await graph.aupdate_state(config, {"messages": rejections}, as_node="sensitive_tools")
                        await stream_graph_events(
                            graph.astream_events(None, config=config, version="v2"),
                            websocket,
                            total_tokens
                        )
                    elif action == "modify":
                        # Overwrite the message argument inside graph state
                        modified_args = decision.get("modified_args", {})
                        
                        new_tool_calls = []
                        for tc in tool_calls:
                            if tc["name"] == "send_telegram_message":
                                tc_copy = tc.copy()
                                tc_copy["args"] = {"message": modified_args.get("message", tc["args"].get("message"))}
                                new_tool_calls.append(tc_copy)
                            else:
                                new_tool_calls.append(tc)
                                
                        new_ai_msg = AIMessage(
                            content=last_message.content,
                            tool_calls=new_tool_calls,
                            id=last_message.id
                        )
                        
                        await graph.aupdate_state(config, {"messages": [new_ai_msg]}, as_node="agent")
                        await stream_graph_events(
                            graph.astream_events(None, config=config, version="v2"),
                            websocket,
                            total_tokens
                        )

                # Send total token usage count before completing
                logger.info(f"Total token usage for session {session_id}: {total_tokens}")
                await websocket.send_json({
                    "type": "tokens",
                    "input_tokens": total_tokens["input_tokens"],
                    "output_tokens": total_tokens["output_tokens"],
                    "total_tokens": total_tokens["total_tokens"]
                })
                
                await websocket.send_json({"type": "done"})
                
                # Retrieve full message history to run background memory reflection
                try:
                    state = await graph.aget_state(config)
                    messages = state.values.get("messages", [])
                    asyncio.create_task(extract_memories_async(messages, user_id="default_user"))
                except Exception as ex:
                    logger.error(f"Error launching memory reflection: {ex}")
                
            except Exception as e:
                logger.error(f"Error during Langgraph execution: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "text": f"Error: {str(e)}"
                })
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
