# Dual-Layer Memory Architecture

J.A.R.V.I.S. implements a **dual-layer memory architecture** designed to solve context window limits while preserving long-term user personalization.

---

## 🧬 Memory Architecture Overview

| Memory Tier | Scope | Storage Mechanism | Trigger |
| :--- | :--- | :--- | :--- |
| **Layer 1: Short-Term Dialogue Compaction** | Active Thread (`thread_id`) | LangGraph Checkpoints (`AsyncPostgresSaver`) | History > 6 turns |
| **Layer 2: Long-Term Preference Reflection** | Permanent User Profile | PostgreSQL Store (`AsyncPostgresStore`) | Asynchronous background task |

---

## ✂️ Layer 1: Context Compaction (`RemoveMessage`)

When conversation turns accumulate, token usage increases and model focus degrades.

1. **Threshold Detection**: After 6 messages, the `summarize_conversation` node triggers.
2. **Context Summarization**: An LLM synthesizes key topics, decisions, and outcomes into a concise summary string.
3. **Pruning**: Previous message objects are replaced with `RemoveMessage(id=msg.id)`, keeping only the latest 2 turns plus the synthesized summary.

```python
# Node execution pattern
summary_prompt = f"Summarize the conversation so far: {history}"
new_summary = await summarizer_llm.ainvoke(summary_prompt)

# Delete old messages from thread checkpoint
delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
return {"summary": new_summary.content, "messages": delete_messages}
```

---

## 🔍 Layer 2: Long-Term Background Reflection

After every user interaction completes, an asynchronous task analyzes the dialogue to detect user preferences, facts, and persistent habits.

### Structured Memory Extraction
Using Pydantic structured output models, the reflection model extracts discrete facts:

```python
class MemoryUpdate(BaseModel):
    key: str # e.g. "favorite_programming_language"
    value: str # e.g. "Python and TypeScript"
    action: Literal["upsert", "delete"]
```

### Fact Storage & Injection
1. Extracted facts are stored in PostgreSQL under the user's permanent memory namespace (`("memories", user_id)`).
2. During future conversations (across different days or sessions), active facts are automatically retrieved and prepended to the system prompt:

```
[System Context]
User Preferences & Facts:
- Name: Ace
- Timezone: America/New_York
- Preferred Language: TypeScript & Python
- Dietary Preferences: Vegetarian
```
