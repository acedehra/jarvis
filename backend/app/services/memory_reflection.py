import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_store
from app.services.llm import get_llm_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger("memory_reflection")

class MemoryUpdate(BaseModel):
    key: str = Field(
        description="The unique key for the fact/preference in snake_case (e.g. 'user_name', 'tech_stack', 'editor_preference')."
    )
    fact: str = Field(
        description="The extracted fact or preference. Leave blank if action is 'delete'."
    )
    action: str = Field(
        description="Action to perform. Must be 'upsert' (to add or modify a preference) or 'delete' (if the user explicitly retracted or changed a previously remembered fact)."
    )
    reasoning: Optional[str] = Field(
        description="Brief reasoning for why this fact is being updated or deleted."
    )

class MemoryUpdates(BaseModel):
    updates: List[MemoryUpdate] = Field(
        description="List of memory updates extracted from the recent conversation."
    )

async def extract_memories_async(messages: list, user_id: str = "default_user"):
    """
    Asynchronously parses conversation messages, extracts user preferences,
    and updates the long-term Postgres memory store.
    """
    logger.info(f"Starting async memory reflection for user: {user_id}")
    try:
        store = get_store()
        
        # 1. Fetch existing memories to present to the model
        existing_items = await store.asearch(("memories", user_id))
        existing_memories_str = ""
        if existing_items:
            existing_memories_str = "\n".join(
                [f"- {item.key}: {item.value.get('fact')}" for item in existing_items]
            )
        else:
            existing_memories_str = "No existing memories found."

        # 2. Format conversation history (limit to last 10 messages for context brevity)
        recent_messages = messages[-10:]
        formatted_dialogue = []
        for m in recent_messages:
            if hasattr(m, "content") and m.content:
                role = "User" if isinstance(m, HumanMessage) else "Assistant"
                formatted_dialogue.append(f"{role}: {m.content}")
        
        dialogue_str = "\n".join(formatted_dialogue)
        if not dialogue_str.strip():
            logger.info("No recent conversation history to extract memories from.")
            return

        # 3. Construct the prompt
        system_prompt = (
            "You are the memory reflection service for J.A.R.V.I.S., a personalized developer assistant.\n"
            "Your task is to analyze the recent conversation history and update the database of user facts and preferences.\n\n"
            "Here are the existing memories stored about the user:\n"
            f"{existing_memories_str}\n\n"
            "RULES:\n"
            "1. Only extract information that represents permanent user preferences, workflows, technical stacks, environment details, or name (e.g., 'user_name': 'Ace', 'tech_stack': 'Next.js, FastAPI', 'ide': 'Cursor').\n"
            "2. DO NOT store transient details such as specific debugging sessions, generic questions, or temporary error messages.\n"
            "3. If the conversation updates or contradicts an existing memory, emit an 'upsert' action with the same key to overwrite it.\n"
            "4. If the user explicitly retracts a fact or says they no longer use/like a preference, emit a 'delete' action for that key.\n"
            "5. Keep the keys concise (snake_case) and the facts clear, helpful, and direct."
        )

        user_prompt = (
            "Here is the dialogue to analyze:\n"
            f"\"\"\"\n{dialogue_str}\n\"\"\"\n"
        )

        # 4. Initialize model (defaulting to Gemini 3.1 Flash Lite for cost efficiency)
        # Use gemini provider and default gemini model
        llm = get_llm_model(provider="gemini", model_name=settings.DEFAULT_GEMINI_MODEL)
        
        # Bind structured output
        structured_llm = llm.with_structured_output(MemoryUpdates)
        
        # Run inference
        logger.info("Invoking LLM for structured fact extraction...")
        extraction_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        result: MemoryUpdates = await structured_llm.ainvoke(extraction_messages)
        
        # 5. Apply updates to PostgresStore
        if not result or not result.updates:
            logger.info("No memory updates extracted from this interaction.")
            return

        for update in result.updates:
            key = update.key.strip().lower()
            action = update.action.strip().lower()
            fact = update.fact.strip()
            
            if action == "upsert" and key and fact:
                logger.info(f"Upserting memory: {key} -> '{fact}' (Reason: {update.reasoning})")
                await store.aput(("memories", user_id), key, {"fact": fact})
            elif action == "delete" and key:
                logger.info(f"Deleting memory: {key} (Reason: {update.reasoning})")
                await store.adelete(("memories", user_id), key)
                
        logger.info("Async memory reflection task completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during async memory reflection: {e}", exc_info=True)
