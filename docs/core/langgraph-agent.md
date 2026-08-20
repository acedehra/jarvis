# LangGraph State Machine

At the heart of J.A.R.V.I.S. is an asynchronous, typed state machine compiled using **LangGraph**. Unlike traditional rigid ReAct loops, LangGraph provides explicit cycle management, state checkpointing, and conditional routing.

---

## 🧩 The `AgentState` Definition

The conversation state is represented as a typed Python TypedDict containing the complete message sequence, summarized memory context, and active tool states:

```python
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str
    active_mcp_tools: list[str]
```

---

## 🔄 Graph Nodes and Transitions

The state machine consists of four primary nodes:

```
                  ┌─────────┐
                  │  START  │
                  └────┬────┘
                       │
                       ▼
              ┌─────────────────┐
              │ agent           │ ◄──────────────────┐
              │ (call_model)    │                    │
              └────────┬────────┘                    │
                       │                             │
                       ▼                             │
               should_continue()                     │
              /        │        \                    │
             /         │         \                   │
     "safe_tools" "sensitive"  "summarize"           │
           │           │           │                 │
           ▼           ▼           ▼                 │
     ┌───────────┐ ┌───────────┐ ┌─────────────────┐ │
     │safe_tools │ │sensitive_ │ │summarize_       │ │
     │           │ │tools (HITL│ │conversation     │ │
     │           │ │Gate)      │ │                 │ │
     └─────┬─────┘ └─────┬─────┘ └────────┬────────┘ │
           │             │                │          │
           └─────────────┴────────────────┴──────────┘
```

### 1. `agent` (Model Invocation)
- Formats the system prompt including user memory facts and compacted context.
- Binds all standard tools and dynamically registered MCP tools to the selected LLM.
- Executes model inference asynchronously.

### 2. `safe_tools`
- Executes non-destructive tool operations immediately:
  - `tavily_search` (Web search)
  - `query_records`, `save_record`, `delete_record` (Tracker storage)
  - Dynamically registered MCP tools

### 3. `sensitive_tools` (HITL Gate)
- Configured with `interrupt_before=["sensitive_tools"]`.
- Execution pauses before side effects (such as sending a Telegram message) execute, allowing user approval in the Web UI.

### 4. `summarize_conversation`
- Triggered when conversation history exceeds 6 dialogue turns.
- Compacts older turns using `RemoveMessage` while extracting a synthesized summary injected into future turns.
