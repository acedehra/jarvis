import logging
from typing import Annotated, Sequence, TypedDict, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    RemoveMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.base import BaseStore
from app.core.config import settings
from app.core.database import get_store, get_checkpointer
from app.services.llm import get_llm_model
from app.services.tools import (
    tools,
    get_weather,
    web_search,
    send_telegram_message,
    save_record,
    query_records,
    aggregate_records,
    manage_record,
    add_pantry_item,
    consume_from_pantry,
    get_pantry_inventory,
    get_pantry_expiring,
    get_meal_plan,
    random_picker,
)
from app.services.mcp import mcp_manager


class AgentState(TypedDict):
    """
    State definition for the Langgraph agent.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    provider: str
    model: Optional[str]
    summary: Optional[str]


def sanitize_messages_for_llm(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """
    Sanitizes and normalizes conversation history before passing to LLM providers
    (specifically Google Gemini) to guarantee strict adherence to turn invariants:
    1. System messages are placed at the beginning.
    2. The conversational turns must start with a HumanMessage (user turn).
    3. Every AIMessage with tool_calls must immediately follow a user turn (HumanMessage)
       or a function response turn (ToolMessage).
    4. Every tool_call in an AIMessage must be followed by its matching ToolMessage.
       Unresponded/interrupted tool calls are cleaned up so dangling function calls do not crash future turns.
    5. Orphaned ToolMessages (without a preceding matching AIMessage) are discarded.
    """
    if not messages:
        return []

    system_msgs: list[BaseMessage] = []
    non_system_msgs: list[BaseMessage] = []

    for m in messages:
        if isinstance(m, SystemMessage):
            system_msgs.append(m)
        else:
            non_system_msgs.append(m)

    if not non_system_msgs:
        return system_msgs

    # Build a lookup of tool_call_id -> ToolMessage
    tool_message_map: dict[str, ToolMessage] = {}
    for m in non_system_msgs:
        if isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None):
            tool_message_map[str(m.tool_call_id)] = m

    sanitized_chat: list[BaseMessage] = []

    for m in non_system_msgs:
        if isinstance(m, HumanMessage):
            sanitized_chat.append(m)

        elif isinstance(m, AIMessage):
            if m.tool_calls:
                # Check preceding message: must be HumanMessage or ToolMessage
                if not sanitized_chat or isinstance(sanitized_chat[-1], AIMessage):
                    sanitized_chat.append(HumanMessage(content="[Continue]"))

                # Check which tool_calls actually have matching ToolMessages
                valid_tool_calls = [
                    tc for tc in m.tool_calls
                    if str(tc.get("id", "")) in tool_message_map
                ]

                if not valid_tool_calls:
                    # Unanswered tool call from previous interrupted turn -> convert to text message
                    fallback_text = m.content if m.content else "[Action completed or interrupted]"
                    sanitized_chat.append(AIMessage(content=fallback_text, id=m.id))
                else:
                    # Retain only answered tool calls
                    new_ai = AIMessage(
                        content=m.content,
                        tool_calls=valid_tool_calls,
                        id=m.id,
                        response_metadata=getattr(m, "response_metadata", {}),
                        additional_kwargs=getattr(m, "additional_kwargs", {})
                    )
                    sanitized_chat.append(new_ai)
            else:
                sanitized_chat.append(m)

        elif isinstance(m, ToolMessage):
            # Only keep ToolMessage if preceded by an AIMessage with matching tool_call_id
            # or preceded by another valid ToolMessage for the same parent turn
            if sanitized_chat:
                last = sanitized_chat[-1]
                if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                    matching_ids = {str(tc.get("id", "")) for tc in last.tool_calls}
                    if str(getattr(m, "tool_call_id", "")) in matching_ids:
                        sanitized_chat.append(m)
                elif isinstance(last, ToolMessage):
                    # Search backward for the parent AIMessage
                    for prev in reversed(sanitized_chat):
                        if isinstance(prev, AIMessage):
                            matching_ids = {str(tc.get("id", "")) for tc in (getattr(prev, "tool_calls", None) or [])}
                            if str(getattr(m, "tool_call_id", "")) in matching_ids:
                                sanitized_chat.append(m)
                            break

    # Ensure conversation starts with a HumanMessage
    while sanitized_chat and not isinstance(sanitized_chat[0], HumanMessage):
        sanitized_chat.insert(0, HumanMessage(content="Hello"))
        break

    if not sanitized_chat:
        sanitized_chat = [HumanMessage(content="Hello")]

    return system_msgs + sanitized_chat


async def call_model(state: AgentState, *, store: BaseStore):
    """
    Node that dynamically retrieves the requested LLM, binds tools, and invokes it.
    """
    messages = state["messages"]
    provider = state.get("provider", "gemini")
    model_name = state.get("model")

    # Dynamic model retrieval
    llm = get_llm_model(provider=provider, model_name=model_name)
    
    # Bind workspace tools and MCP tools to the LLM
    all_tools = list(tools) + mcp_manager.get_tools()
    llm_with_tools = llm.bind_tools(all_tools)
    
    # Retrieve memories for this user
    user_id = "default_user"
    memory_context = ""
    if store:
        try:
            memories = await store.asearch(("memories", user_id))
            if memories:
                facts = [f"- {m.key}: {m.value.get('fact')}" for m in memories]
                memory_context = "\nRemembered facts/preferences about the user:\n" + "\n".join(facts) + "\n"
        except Exception as e:
            # Safe fallback if store search fails (e.g. table not ready yet)
            logging.getLogger("graph").warning(f"Failed to load user memories: {e}")

    # Inject conversation summary context if present
    summary_context = ""
    summary = state.get("summary")
    if summary:
        summary_context = f"\nHere is a summary of the earlier conversation history:\n{summary}\n"

    # Formulate a system message with the current date, time, timezone, and user memories
    try:
        user_tz = ZoneInfo(settings.USER_TIMEZONE)
    except Exception:
        user_tz = timezone.utc

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(user_tz)
    
    local_time_str = now_local.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
    iso_local_str = now_local.isoformat()
    iso_utc_str = now_utc.isoformat()
    
    system_message = SystemMessage(
        content=(
            f"You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the sophisticated, highly capable AI assistant "
            f"and digital butler originally created for Tony Stark.\n\n"
            f"PERSONA, TONE & SPEECH CADENCE:\n"
            f"• Embody the classic J.A.R.V.I.S. demeanor: calm, poised, impeccably polite, and articulate with a refined British gentleman's cadence.\n"
            f"• Naturally address the user with dignified courtesy (such as 'Sir', or their name if known from memories) where fitting, without sounding overbearing.\n"
            f"• Exhibit subtle, dry British wit and understated humor when appropriate, while remaining steadfastly efficient, dependable, and sharp.\n"
            f"• Keep spoken delivery concise, crisp, and intellectually precise. Avoid robotic clichés and unnecessary conversational fluff.\n"
            f"• Naturally and expressively incorporate relevant emojis throughout responses (Telegram & Web UI) to make status reports and information visually clear:\n"
            f"  - 🌤️ / ☀️ / 🌧️ / ❄️ / 🌡️ / 💨 / ☔ for Weather & Forecasts\n"
            f"  - ⛽ / 🚗 / 🛣️ / 🏷️ for Gas, Fuel logs & Vehicles\n"
            f"  - 💰 / 💳 / 💸 / 📊 / 📈 for Expenses, Money & Analytics\n"
            f"  - ⏰ / 🔔 / 📅 for Reminders & Scheduling\n"
            f"  - ✅ / 📌 / 📝 for To-do lists & Tasks\n"
            f"  - 🔍 / 🌐 / 📰 for Web Search, News & Articles\n"
            f"  - 🤖 / 👋 / 💡 / 🚀 for Greetings, Status & General Assistance\n\n"
            f"CURRENT TIME & TEMPORAL CONTEXT:\n"
            f"• User Local Time: {local_time_str}\n"
            f"• User Timezone: {settings.USER_TIMEZONE} (ISO local: {iso_local_str})\n"
            f"• Current UTC Time: {iso_utc_str}\n"
            f"• When answering questions regarding the current time, date, day of week, or recent events, ALWAYS reference the user's local time ({settings.USER_TIMEZONE}).\n\n"
            f"USER MEMORIES & PREFERENCES:\n"
            f"A background memory service automatically injects everything you know about the user below. "
            f"If a personal fact (like user name, preferences, IDE) is not present in the list below, "
            f"DO NOT use workspace search tools or web search to find it. Instead, politely inform the user you don't "
            f"remember yet and ask them directly.\n\n"
            f"TRACKING & ANALYTICS CAPABILITIES:\n"
            f"You have access to a universal tracking database via specialized tools:\n"
            f"- 'save_record': Use this to save gas / fuel fill-ups (collection='gas' with amount, gallons, price_per_gallon, odometer, station, vehicle), "
            f"expenses (collection='expense' with amount, category, currency), todos (collection='todo' with status, priority), "
            f"bookmarks (collection='bookmark' with url, tags), reminders (collection='reminder' with event_date), workout notes, or any structured item.\n"
            f"  * IMPORTANT FOR GAS TRACKING: When the user mentions buying gas / filling up (e.g. 'Filled 12 gallons for $45 at Shell, odometer 54,200'), "
            f"use collection='gas', extract amount, gallons, price_per_gallon (or compute amount/gallons), odometer, station, and vehicle into data.\n"
            f"  * IMPORTANT FOR REMINDERS & SCHEDULED ITEMS: When the user asks to be reminded (e.g. 'in 15 minutes', 'tomorrow at 9am', 'at 4:30pm'), "
            f"calculate the exact target timestamp using the User Local Time provided above. Always format event_date as an ISO-8601 string with timezone offset (e.g. '{iso_local_str[:19]}{now_local.strftime('%z')[:3]}:{now_local.strftime('%z')[3:]}' or UTC 'Z').\n"
            f"- 'query_records': Use this to search, filter, or retrieve saved items from any collection (including 'gas' for past fill-ups).\n"
            f"- 'aggregate_records': ALWAYS use this tool when the user asks math questions, spending totals, fuel totals, counts, "
            f"averages, or category breakdowns (e.g. 'How much did I spend on gas?', 'How many gallons did I buy?'). Never calculate totals manually "
            f"in your head; let the database calculate it deterministically.\n"
            f"- 'manage_record': Use this to mark tasks as completed, update records, or delete them.\n\n"
            f"* IMPORTANT - PANTRY & GROCERY INVENTORY: You have dedicated pantry & meal-planning tools. "
            f"Use 'add_pantry_item' when the user logs groceries or stocks ingredients (auto-accumulates quantities and "
            f"normalizes names) — always ask for / store an expiry date when the user knows it. Use 'get_pantry_inventory' "
            f"or 'get_meal_plan' before any meal-planning / 'cook something with what I have' request to fetch the deterministic "
            f"list of ingredients on hand (get_meal_plan also flags which items are expiring soonest), then suggest plausible "
            f"dishes using ONLY the ingredients in stock (plus sensible staples like salt, oil, pepper), and prioritize using up "
            f"near-expiring items first. Use 'get_pantry_expiring' when asked what's about to go bad or what to eat first. "
            f"Use 'consume_from_pantry' to decrement ingredients when a meal is cooked. If the user wants a dish not fully covered "
            f"by the pantry, provide a shopping list of the missing ingredients.\n\n"
            f"REAL-TIME WEATHER & FORECASTS:\n"
            f"- 'get_weather': ALWAYS use this tool whenever the user asks about current weather, temperature, forecasts, precipitation, humidity, or wind for any city or location.\n"
            f"- When presenting weather results to the user, format the response cleanly with emojis for every key metric (condition, temperature in °C and °F, humidity, wind, and forecast highlights).\n\n"
            f"RANDOM SELECTIONS, GIVEAWAYS & DECISIONS:\n"
            f"- 'random_picker': ALWAYS use this tool whenever the user asks to pick a random winner, select from a list of options/entrants, roll dice, pick numbers in a range, shuffle a list, or make an unbiased random decision.\n"
            f"{memory_context}"
            f"{summary_context}"
        )
    )
    
    # Prepend the system message and sanitize turns for strict LLM turn order compliance
    full_messages = sanitize_messages_for_llm([system_message] + list(messages))
    
    # Invoke the model with tools (using async invoke as the node is async)
    response = await llm_with_tools.ainvoke(full_messages)
    return {"messages": [response]}


async def summarize_conversation(state: AgentState):
    """
    Node that summarizes the oldest messages when history grows too long,
    storing the summary in the state and removing the summarized messages.
    Uses turn-aware boundaries so that complete turns (user + tool calls + responses + AI)
    are summarized together without splitting tool call pairs.
    """
    messages = state["messages"]
    
    # We summarize if the conversation is long (exceeds 6 messages).
    if len(messages) <= 6:
        return {}

    # Find a clean turn boundary: the retained messages should start with a HumanMessage
    split_idx = -1
    for idx in range(len(messages) - 4, 0, -1):
        if isinstance(messages[idx], HumanMessage):
            split_idx = idx
            break

    if split_idx <= 0:
        return {}
        
    messages_to_summarize = messages[:split_idx]
    
    # Format the dialogue to summarize
    formatted_dialogue = []
    for m in messages_to_summarize:
        if isinstance(m, HumanMessage):
            role = "User"
        elif isinstance(m, AIMessage):
            role = "Assistant"
        else:
            continue
        if getattr(m, "content", None):
            formatted_dialogue.append(f"{role}: {m.content}")
        
    dialogue_str = "\n".join(formatted_dialogue)
    if not dialogue_str.strip():
        return {}
        
    # Get existing summary if any
    existing_summary = state.get("summary")
    
    # Construct summarization prompt
    if existing_summary:
        prompt = (
            f"Here is an existing summary of the earlier conversation:\n{existing_summary}\n\n"
            f"And here are the new messages that have occurred since then:\n{dialogue_str}\n\n"
            f"Please generate a new, consolidated summary that includes the key information from both the existing summary and the new messages. Keep it concise."
        )
    else:
        prompt = (
            f"Please generate a concise summary of the following conversation history:\n{dialogue_str}"
        )
        
    # Use the default model to summarize
    provider = state.get("provider", "gemini")
    model_name = state.get("model")
    llm = get_llm_model(provider=provider, model_name=model_name)
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    new_summary = response.content
    
    # Create RemoveMessage instructions for the summarized messages
    remove_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize if getattr(m, "id", None)]
    
    return {
        "summary": new_summary,
        "messages": remove_messages
    }


def should_continue(state: AgentState):
    """
    Determines whether to execute safe tools, sensitive tools, or to summarize the conversation.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has tool calls, determine where to route
    if getattr(last_message, "tool_calls", None):
        # Route to sensitive_tools if J.A.R.V.I.S. wants to send a Telegram message
        for tc in last_message.tool_calls:
            if tc["name"] == "send_telegram_message":
                return "sensitive_tools"
        return "safe_tools"
        
    # If the conversation is long, check if we should summarize
    if len(messages) > 6:
        return "summarize"
        
    return END


# Set up the Langgraph state machine with safe/sensitive tool separation
safe_tools = [
    get_weather,
    web_search,
    save_record,
    query_records,
    aggregate_records,
    manage_record,
    add_pantry_item,
    consume_from_pantry,
    get_pantry_inventory,
    get_pantry_expiring,
    get_meal_plan,
    random_picker,
]
sensitive_tools = [send_telegram_message]
async def execute_safe_tools(state: AgentState):
    """
    Dynamically executes requested safe tools (static safe tools + registered MCP tools).
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # Combine static safe tools and dynamic mcp tools
    all_safe_tools = {t.name: t for t in safe_tools}
    for t in mcp_manager.get_tools():
        all_safe_tools[t.name] = t
        
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        if tool_name in all_safe_tools:
            tool_obj = all_safe_tools[tool_name]
            try:
                result = await tool_obj.ainvoke(tool_call["args"])
                if isinstance(result, ToolMessage):
                    tool_messages.append(result)
                else:
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            name=tool_name,
                            tool_call_id=tool_call["id"]
                        )
                    )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool {tool_name}: {str(e)}",
                        name=tool_name,
                        tool_call_id=tool_call["id"],
                        status="error"
                    )
                )
        else:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool '{tool_name}' is not registered or is not available as a safe tool.",
                    name=tool_name,
                    tool_call_id=tool_call["id"],
                    status="error"
                )
            )
    return {"messages": tool_messages}

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("safe_tools", execute_safe_tools)
workflow.add_node("sensitive_tools", ToolNode(sensitive_tools))
workflow.add_node("summarize", summarize_conversation)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "safe_tools": "safe_tools",
        "sensitive_tools": "sensitive_tools",
        "summarize": "summarize",
        END: END
    }
)
workflow.add_edge("safe_tools", "agent")
workflow.add_edge("sensitive_tools", "agent")
workflow.add_edge("summarize", END)

# Postgres checkpointer persistence for conversation threads and postgres for long term store
memory = get_checkpointer()
store = get_store()

# Compile with interrupt_before sensitive_tools for Human-in-the-Loop approval
graph = workflow.compile(
    checkpointer=memory,
    store=store,
    interrupt_before=["sensitive_tools"]
)


