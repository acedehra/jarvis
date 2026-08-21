# J.A.R.V.I.S. Backend

Production-grade asynchronous AI Agent service built with **FastAPI**, **LangGraph**, and **PostgreSQL**. Features multi-provider LLM routing, Model Context Protocol (MCP) dynamic runtime, dual-layer memory management, deterministic SQL analytics, and bidirectional Telegram integration.

---

## 🏗️ Architectural Highlights

```mermaid
flowchart TD
    Client(["WebSocket / REST Client"]) --> FastAPI["FastAPI Server"]
    Telegram["Telegram Bot Listener"] --> LangGraph["LangGraph State Machine"]
    FastAPI --> LangGraph

    subgraph Agent_Workflow ["LangGraph Agent Workflow"]
        AgentNode["agent (call_model)"] --> Router{"should_continue()"}
        Router -- "Safe Tools / MCP" --> SafeTools["safe_tools (Tavily, Tracker, MCP)"]
        SafeTools --> AgentNode
        
        Router -- "Sensitive Actions" --> HITLGate{{"HITL Approval Gate (interrupt_before)"}}
        HITLGate -- "Approved / Modified" --> SensitiveTools["sensitive_tools (Telegram)"]
        SensitiveTools --> AgentNode
        
        Router -- "History > 6 Msgs" --> Summarize["summarize_conversation (RemoveMessage)"]
        Summarize --> EndNode(["END"])
        Router -- "Complete" --> EndNode
    end

    subgraph State_Persistence ["State & Persistence"]
        LangGraph <--> Checkpointer[("PostgreSQL AsyncPostgresSaver")]
        LangGraph <--> MemoryStore[("PostgreSQL AsyncPostgresStore")]
        LangGraph --> BGTask["Async Memory Reflection Task"]
        BGTask --> MemoryStore
        SafeTools <--> PgPool[("PostgreSQL Connection Pool / Tracker")]
    end

    subgraph Dynamic_Extensibility ["Dynamic Extensibility (MCP)"]
        MCPManager["MCP Manager"] --> StdioProc["Stdio Subprocesses"]
        MCPManager --> SSERemote["Remote SSE Servers"]
        SafeTools <--> MCPManager
    end
```

1. **Stateful Graph Workflows**: Compiled with `langgraph` using typed state (`AgentState`), asynchronous nodes, and persistent thread checkpointing via `AsyncPostgresSaver`.
2. **Two-Tier Memory System**:
   - **Short-Term Compaction**: Sliding-window summarization node using `RemoveMessage` to prune checkpoint history while preserving context in system prompts.
   - **Long-Term Reflection**: Asynchronous background worker parsing conversations with Pydantic structured outputs (`MemoryUpdates`) to upsert/delete user facts in PostgreSQL `AsyncPostgresStore`.
3. **Model Context Protocol (MCP)**: Native client supporting both `stdio` subprocesses and `sse` streaming transports. Dynamically translates JSON Schema into runtime Pydantic models for LangChain tool binding.
4. **Deterministic Math Offloading**: Eliminates LLM arithmetic hallucination by routing numerical calculations and aggregations to PostgreSQL JSONB operators (`SUM`, `AVG`, `COUNT`, `MIN`, `MAX`).
5. **Human-in-the-Loop (HITL) Gate**: Interrupts execution before sensitive side effects (e.g. `send_telegram_message`), enabling real-time review, modification, or rejection over WebSockets.
6. **Observability**: Native tracing with LangSmith for token metrics, graph node latency, and tool diagnostics.

---

## 📁 Directory Structure

```
backend/
├── app/
│   ├── api/                      # REST API Endpoints
│   │   ├── mcp_routes.py         # MCP server registry and connection management
│   │   ├── telegram_routes.py    # Telegram bot health and test dispatch
│   │   └── tracker_routes.py     # Universal structured tracker CRUD & aggregations
│   ├── core/                     # Application Core
│   │   ├── auth.py               # Key authentication, first-run generation & security dependencies
│   │   ├── config.py             # Pydantic BaseSettings and env configuration
│   │   └── database.py           # AsyncConnectionPool, Checkpointer & Store proxies
│   ├── services/                 # Domain Services & AI Logic
│   │   ├── graph.py              # LangGraph state machine definition & compiler
│   │   ├── llm.py                # Multi-provider LLM factory (Gemini, OpenAI, Anthropic, OpenRouter)
│   │   ├── mcp.py                # Model Context Protocol (MCP) manager & schema builder
│   │   ├── memory_reflection.py  # Background memory extraction & reflection pipeline
│   │   ├── telegram_service.py   # python-telegram-bot async service
│   │   ├── tools.py              # Sandboxed workspace tools, Tavily web search, Telegram tool
│   │   └── tracker.py            # PostgreSQL tracker service with JSONB query builder
│   └── main.py                   # FastAPI application entrypoint, lifespan, WebSocket handler
├── .env.example                  # Environment variable template
├── Dockerfile                    # Container definition
├── pyproject.toml                # UV package definition and dependencies
└── uv.lock                       # Locked dependency tree
```

---

## ⚙️ Configuration (`.env`)

Create a `.env` file in `backend/` (or copy `.env.example`):

| Variable | Required | Description | Default |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | **Yes** | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/chatbot` |
| `GEMINI_API_KEY` | Conditional | Google Gemini API key (default provider) | `None` |
| `OPENAI_API_KEY` | Optional | OpenAI API key | `None` |
| `ANTHROPIC_API_KEY` | Optional | Anthropic Claude API key | `None` |
| `OPENROUTER_API_KEY` | Optional | OpenRouter API key | `None` |
| `TAVILY_API_KEY` | Optional | Tavily Search API key for web search | `None` |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram Bot token | `None` (Runs in simulation mode if omitted) |
| `TELEGRAM_CHAT_ID` | Optional | Target Telegram Chat ID | `None` |
| `USER_TIMEZONE` | Optional | User timezone for temporal awareness & reminders | `America/New_York` |
| `CHECKPOINT_RETENTION_HOURS` | Optional | Inactivity threshold in hours before auto-purging checkpoints | `24` |
| `CHECKPOINT_CLEANUP_INTERVAL_HOURS` | Optional | Frequency in hours to execute checkpoint cleanup worker | `1` |
| `CORS_ORIGINS` | Optional | Allowed CORS origins (JSON array or comma-separated) | `["*"]` |
| `LANGCHAIN_TRACING_V2` | Optional | Enable LangSmith tracing | `true` |
| `LANGCHAIN_API_KEY` | Optional | LangSmith API Key | `None` |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name | `jarvis-backend` |

---

## 🚀 Getting Started

### Prerequisites
- Python `>=3.13`
- [`uv`](https://docs.astral.sh/uv/) (Astral Python package manager)
- PostgreSQL `>=16` (with `pgvector` extension recommended)

### 1. Install Dependencies
```bash
uv sync
```

### 2. Start PostgreSQL
Using Docker:
```bash
docker run -d --name jarvis-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=chatbot \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### 3. Run Development Server
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔐 API Key Authentication

All endpoints under `/api/*` and WebSocket connections require API key authentication.

### Authentication Methods
Clients can supply the key via:
1. **HTTP Header**: `X-API-Key: <your_key>`
2. **Authorization Header**: `Authorization: Bearer <your_key>`
3. **Query Parameter**: `?api_key=<your_key>` (e.g. `/api/chat?session_id=...&api_key=...`)

### Key Lifecycle & Configuration
- **Pre-configured**: Set `API_KEY=your_secret_key` in `.env`.
- **First Run Auto-Generation**: If `API_KEY` is omitted, the backend generates a secure 256-bit key (`jarvis_sec_...`), persists it to `.api_key` (with `0600` permissions), and prints the key **once** on the console. Subsequent runs load `.api_key` silently.

---

## 📡 API & WebSocket Reference

### WebSocket Protocol (`/api/chat?session_id={uuid}&api_key={key}`)

The primary chat interface operates over WebSockets for bi-directional token streaming and interrupt handling.

#### Client Messages
- **Send Message**:
  ```json
  {
    "text": "How much did I spend on groceries this month?",
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  }
  ```
- **HITL Approval Decision**:
  ```json
  {
    "action": "approve" // Options: "approve", "reject", "modify"
  }
  ```

#### Server Events
- `{"type": "chunk", "text": "token"}`: Real-time token stream from the agent node.
- `{"type": "tool_start", "name": "aggregate_records", "input": {...}}`: Tool execution started.
- `{"type": "tool_end", "name": "aggregate_records", "output": "..."}`: Tool execution finished.
- `{"type": "sensitive_tool_approval_required", "tool_calls": [...]}`: Interrupt gate triggered; execution paused waiting for user decision.
- `{"type": "tokens", "input_tokens": 120, "output_tokens": 45, "total_tokens": 165}`: Token usage metrics.
- `{"type": "done"}`: Execution complete.

### REST Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status |
| `GET` | `/api/memories` | List long-term remembered facts |
| `DELETE` | `/api/memories/{key}` | Delete a specific memory fact |
| `DELETE` | `/api/chat/sessions/{session_id}` | Clear short-term thread checkpoints |
| `GET` | `/api/tracker/records` | Query tracked items with filters & full-text search |
| `POST` | `/api/tracker/records` | Create a new tracked record |
| `PUT` | `/api/tracker/records/{id}` | Update record or status |
| `DELETE` | `/api/tracker/records/{id}` | Delete a tracked record |
| `GET` | `/api/tracker/aggregate` | Run deterministic SQL calculations (`sum`, `avg`, `count`, etc.) |
| `GET` | `/api/tracker/collections` | Get collection statistics and counts |
| `GET` | `/api/mcp/servers` | List configured MCP servers, status, and tools |
| `POST` | `/api/mcp/servers` | Dynamically register and launch an MCP server |
| `PUT` | `/api/mcp/servers/{name}` | Update an existing MCP server configuration |
| `DELETE` | `/api/mcp/servers/{name}` | Disconnect and remove an MCP server |
| `GET` | `/api/telegram/status` | Telegram bot connection status |
| `POST` | `/api/telegram/test-message` | Send test Telegram notification |

---

## 🗄️ Database Schema

The backend uses PostgreSQL for state checkpointing and structured tracking.

### Tracker Items Table (`tracker_items`)
```sql
CREATE TABLE IF NOT EXISTS tracker_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    collection VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tracker_items_collection ON tracker_items(collection);
CREATE INDEX IF NOT EXISTS idx_tracker_items_user_coll ON tracker_items(user_id, collection);
CREATE INDEX IF NOT EXISTS idx_tracker_items_event_date ON tracker_items(event_date);
CREATE INDEX IF NOT EXISTS idx_tracker_items_data_gin ON tracker_items USING GIN (data);
```
