# Getting Started

Welcome to **J.A.R.V.I.S.** (Just A Rather Very Intelligent System), an enterprise-grade autonomous personal AI assistant and agentic operating system.

---

## ⚡ Quickstart with Docker Compose

The fastest and most reliable way to spin up the complete J.A.R.V.I.S. stack (Frontend, Backend, and PostgreSQL with pgvector) is using Docker Compose:

### 1. Clone the Repository
```bash
git clone https://github.com/acedehra/jarvis.git
cd jarvis
```

### 2. Configure Environment Variables
Copy the sample environment file and add your AI provider API key:
```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in your editor and set your primary LLM key:
```ini
# Google Gemini (Default)
GEMINI_API_KEY=your_gemini_api_key_here

# Or OpenAI / Anthropic
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 3. Launch the Stack
```bash
docker compose up --build
```

### 4. Access the Applications
Once the containers finish building and initialize:
- 🌐 **Web Dashboard UI**: [http://localhost:3000](http://localhost:3000)
- ⚙️ **FastAPI Backend & Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🗄️ **PostgreSQL Database**: `localhost:5432`

---

## 🛠️ Local Development (Native)

If you prefer to run services natively on your host machine for rapid development:

### System Prerequisites
- **Python**: `>= 3.13` (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js / Bun**: [`bun`](https://bun.sh/) `>= 1.0` (or Node.js `>= 20`)
- **PostgreSQL**: `>= 16` with `pgvector` extension

### 1. Backend Setup

```bash
cd backend

# Copy environment variables
cp .env.example .env

# Install Python dependencies via uv
uv sync

# Run FastAPI server with auto-reload
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
bun install

# Start Next.js 16 development server
bun run dev
```

The Next.js dashboard will be available at [http://localhost:3000](http://localhost:3000).

---

## 🧭 Next Steps

- Explore the [System Architecture](/guide/architecture) to understand how requests flow through the state machine.
- Configure [Environment Variables](/guide/configuration) for Telegram, Tavily web search, and MCP tools.
- Learn about [Dual-Layer Memory](/core/dual-layer-memory) and [HITL Safety Gates](/core/hitl-safety).
