# System Architecture

J.A.R.V.I.S. is built on a modern, decoupled asynchronous architecture designed for high resiliency, low latency, and deterministic state transitions.

---

## 🏛️ High-Level Component Topology

```
                      ┌─────────────────────────────────────────┐
                      │              INGRESS LAYER              │
                      │  • Next.js 16 Web Dashboard (WebSocket) │
                      │  • Telegram Bot Service (Long Polling)  │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │         FASTAPI GATEWAY & LIFESPAN      │
                      │  • Connection Managers & Async Pools    │
                      │  • REST Endpoints & Background Workers  │
                      └──────────┬───────────────────┬──────────┘
                                 │                   │
                                 │ (Speech /tts)     ▼
                                 │          ┌─────────────────────────────────┐
                                 │          │   LANGGRAPH AGENT STATE MACHINE │
                                 │          │  • Typed State: AgentState      │
                                 │          │  • Dynamic Routing & HITL Gates │
                                 │          └────┬────────────┬────────────┬──┘
                                 ▼               │            │            │
                      ┌──────────────────┐       │            │            │
                      │ KOKORO TTS (CPU) │       │            │            │
                      │ • ~350MB RAM     │       │            │            │
                      │ • British Voice  │       │            │            │
                      └──────────────────┘       │            │            │
                                                 │            │            │
             ┌───────────────────────────────────┘            │            └─────────────────┐
             ▼                                                ▼                              ▼
   ┌───────────────────┐                            ┌───────────────────┐          ┌───────────────────┐
   │   POSTGRESQL TIER │                            │   MCP RUNTIME     │          │  EXECUTION TOOLS  │
   │ • Checkpointers   │                            │ • Stdio Process   │          │ • Tavily Search   │
   │ • Long-Term Store │                            │ • Remote SSE Hub  │          │ • SQL JSONB Store │
   │ • Background Refl │                            │ • Schema Wrapper  │          │ • Sandboxed Files │
   └───────────────────┘                            └───────────────────┘          └───────────────────┘
```

---

## 🔄 Lifecycle of a Request

1. **Ingress**:
   - The user dispatches a prompt via the **Next.js Web UI** over a persistent WebSocket or via a **Telegram message**.
2. **State Machine Invocation**:
   - FastAPI initializes or resumes the conversation graph state via `AsyncPostgresSaver` using the unique `thread_id`.
3. **Reasoning & Tool Selection**:
   - The `agent` node sends the dialogue history and system prompt (including compacted summaries and memory facts) to the LLM.
4. **Conditional Routing (`should_continue`)**:
   - **Safe Tools**: Non-destructive operations (Tavily search, Tracker queries, dynamic MCP tools) execute immediately in `safe_tools`.
   - **Sensitive Tools**: Destructive actions (e.g. sending a Telegram broadcast) route to `sensitive_tools` where an `interrupt_before` gate pauses execution for Human-in-the-Loop approval.
   - **Dialogue Compaction**: If dialogue exceeds 6 turns, `summarize_conversation` automatically reduces token load via `RemoveMessage`.
5. **Memory Reflection**:
   - When the graph execution concludes, an asynchronous background task reflects on new dialogue turns, extracting structured user facts and persisting them to PostgreSQL.

---

## 🗄️ Persistence & Storage Layer

J.A.R.V.I.S. leverages PostgreSQL with the following core responsibilities:

| Table / Collection | Purpose | Storage Mechanism |
| :--- | :--- | :--- |
| **Checkpoints (`checkpoints`)** | Multi-turn LangGraph conversation state persistence | `AsyncPostgresSaver` |
| **Store (`checkpoint_blobs`)** | Permanent key-value memories and user profiles | `AsyncPostgresStore` |
| **Tracker Items (`tracker_items`)** | Dynamic structured data: expenses, todos, reminders, bookmarks | PostgreSQL `JSONB` indexed with GIN |

---

## 🌐 Dynamic Extensibility via MCP

The **Model Context Protocol (MCP)** integration enables connecting third-party tool servers on the fly:
- **`stdio` transport**: Spawns local binaries (e.g., SQLite, GitHub CLI, local file trees) inside isolated subprocesses.
- **`sse` transport**: Connects to remote streaming endpoints over HTTP Server-Sent Events.
- **Hot-Reloading**: Tools are registered as LangChain dynamic `BaseTool` models without requiring a backend restart.
