# Configuration Reference

All settings for J.A.R.V.I.S. are defined via environment variables loaded in `backend/app/core/config.py` using Pydantic Settings.

---

## ⚙️ Environment Variables

### 1. AI & LLM Providers

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `string` | `""` | Google Gemini API key (recommended default: `gemini-2.5-flash`) |
| `OPENAI_API_KEY` | `string` | `""` | OpenAI API key for GPT-4o / GPT-4o-mini |
| `ANTHROPIC_API_KEY` | `string` | `""` | Anthropic Claude API key |
| `DEFAULT_MODEL` | `string` | `gemini-2.5-flash` | Default LLM model identifier |
| `TAVILY_API_KEY` | `string` | `""` | Tavily API key for real-time web search tools |

---

### 2. Database & Persistence

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `string` | `postgresql+asyncpg://postgres:postgres@localhost:5432/jarvis` | Async PostgreSQL connection string |
| `POSTGRES_DB` | `string` | `jarvis` | Database name |
| `POSTGRES_USER` | `string` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `string` | `postgres` | Database password |

---

### 3. Telegram Integration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | `string` | `""` | Bot token obtained from Telegram `@BotFather` |
| `TELEGRAM_CHAT_ID` | `string` | `""` | Your verified Telegram User/Chat ID for security whitelisting |
| `TELEGRAM_VOICE_REPLY` | `boolean` | `false` | When `true`, automatically attaches spoken voice notes in Telegram |

---

### 4. Text-to-Speech (TTS) & Voice

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `TTS_BASE_URL` | `string` | `http://localhost:8880` | URL of the Kokoro TTS service (`http://tts:8880` in Docker) |
| `TTS_VOICE` | `string` | `bm_george` | Default Kokoro voice ID (`bm_george` for J.A.R.V.I.S.) |
| `TTS_SPEED` | `float` | `1.0` | Playback speed multiplier (`0.5` - `2.0`) |

---

### 5. Server & Security

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `string` | `development` | `development`, `staging`, or `production` |
| `PORT` | `int` | `8000` | FastAPI server listen port |
| `CORS_ORIGINS` | `list` | `["http://localhost:3000"]` | Allowed CORS origins for browser WebSockets/REST |
| `USER_TIMEZONE` | `string` | `UTC` | Timezone used for scheduled reminders and briefings (e.g. `America/New_York`) |

---

## 🔒 Security Best Practices

::: tip Sandboxing File Tools
Inspection tools (`read_workspace_file`, `search_workspace_content`, `list_workspace_files`) are strictly confined to authorized project paths and are forbidden from reading `.env` files, SSH keys, or certificates.
:::

::: warning Telegram Access Whitelisting & Polling Protection
Always configure `TELEGRAM_CHAT_ID` alongside `TELEGRAM_BOT_TOKEN`. If `TELEGRAM_CHAT_ID` is missing or invalid, Telegram polling is automatically disabled to prevent unauthorized access by other Telegram users.
:::
