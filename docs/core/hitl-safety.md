# Human-in-the-Loop (HITL) Execution Safety

Allowing an AI agent to execute real-world side effects (sending messages, modifying sensitive records, executing financial transactions) requires robust safety boundaries. J.A.R.V.I.S. implements **Human-in-the-Loop (HITL)** approval workflows natively integrated with LangGraph.

---

## 🛡️ The HITL Architecture

```
                    ┌─────────────────────────┐
                    │       agent node        │
                    │  (Generates Tool Call)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     Sensitive Tool Detected?
                     (e.g., send_telegram_msg)
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
                 [NO]                        [YES]
                   │                           │
                   ▼                           ▼
            ┌─────────────┐       ┌─────────────────────────┐
            │ safe_tools  │       │     sensitive_tools     │
            │  (Executes) │       │   interrupt_before Gate │
            └─────────────┘       └────────────┬────────────┘
                                               │ (Halts Graph)
                                               ▼
                                  ┌─────────────────────────┐
                                  │   Next.js Approval UI   │
                                  │ • Approve               │
                                  │ • In-Place Edit Payload │
                                  │ • Reject Action         │
                                  └────────────┬────────────┘
                                               │ (Resume with Input)
                                               ▼
                                  ┌─────────────────────────┐
                                  │  Graph Execution Resumes│
                                  └─────────────────────────┘
```

---

## 🚦 Implementation Details

### 1. LangGraph Interruption Point
The state machine is compiled with an interruption barrier before entering `sensitive_tools`:

```python
# Graph compilation with interrupt
workflow = StateGraph(AgentState)
...
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["sensitive_tools"]
)
```

### 2. Real-Time WebSocket Approval Notification
When execution pauses at the interrupt point, FastAPI detects the pending tool call and emits an approval event over the active WebSocket:

```json
{
  "type": "hitl_approval_required",
  "data": {
    "tool_name": "send_telegram_message",
    "tool_args": {
      "message": "Hey team, server maintenance begins in 10 minutes."
    },
    "thread_id": "session-123"
  }
}
```

### 3. User Actions in Web Dashboard

The user is presented with three actions in the UI:
- **Approve**: Resumes execution with the original tool payload.
- **Modify & Approve**: The user edits the message text or arguments directly in the UI before dispatching.
- **Reject**: Cancels the tool execution and returns a rejection message to the LLM so it can formulate an alternative response.
