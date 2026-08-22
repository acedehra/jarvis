# Kokoro-82M TTS & J.A.R.V.I.S. Voice

J.A.R.V.I.S. features native **Neural Text-to-Speech (TTS)** powered by **Kokoro-82M**, emulating the authentic, refined British cadence of Paul Bettany's J.A.R.V.I.S. across both the **Next.js Web Dashboard** and **Telegram Gateway**.

---

## 🎙️ Overview & Architecture

Kokoro-82M is an ultra-lightweight, 82-million parameter neural speech synthesis model that runs entirely on standard CPUs without requiring a GPU or consuming heavy cloud API credits.

```
┌─────────────────────────────────┐
│     Next.js 16 Web Dashboard    │
│  (Auto-Speak Toggle & Listen)   │
└────────────────┬────────────────┘
                 │
                 ▼  (REST /api/tts/speak)
┌─────────────────────────────────┐       (OpenAI /v1/audio/speech)       ┌──────────────────────────────┐
│     FastAPI Backend Gateway     │ ────────────────────────────────────► │      Kokoro TTS Service      │
│     (Text Sanitization & Auth)  │ ◄──────────────────────────────────── │  (Port 8880 | ~350 MB RAM)   │
└────────────────┬────────────────┘             (Binary MP3)              └──────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│       Telegram Bot Service      │
│     (Spoken Voice Replies)      │
└─────────────────────────────────┘
```

### ⚡ Key Specifications
- **RAM Footprint**: **~350 MB** total RAM.
- **CPU Speed**: Generates speech at a **Real-Time Factor (RTF) of 0.15–0.30x** on 1–2 vCPU cores (a 5-second sentence generates in under 1 second).
- **Default British Voice**: `bm_george` (British Male — calm, poised, eloquent gentleman delivery).
- **Zero Cloud Costs**: 100% self-hosted and privacy-respecting.

---

## 🐳 Docker Deployment

The TTS service runs as a dedicated lightweight microservice container alongside the rest of the J.A.R.V.I.S. stack:

```yaml
  tts:
    image: ghcr.io/remsky/kokoro-fastapi-cpu:latest
    ports:
      - "8880:8880"
    environment:
      - DEFAULT_VOICE=bm_george
    restart: unless-stopped
```

To launch the full stack with TTS:
```bash
docker compose up -d
```

---

## ⚙️ Configuration (`.env`)

Configure the following variables in `backend/.env`:

| Variable | Type | Default | Description |
| :--- | :---: | :--- | :--- |
| `TTS_BASE_URL` | String | `http://localhost:8880` | URL of the Kokoro TTS service (`http://tts:8880` in Docker) |
| `TTS_VOICE` | String | `bm_george` | Default voice ID for speech synthesis |
| `TTS_SPEED` | Float | `1.0` | Playback speed multiplier (`0.5` to `2.0`) |
| `TELEGRAM_VOICE_REPLY` | Boolean | `false` | When `true`, automatically attaches spoken voice notes in Telegram |

---

## 🔊 Web Dashboard Features

### 1. Global Auto-Speak Toggle
Located in the top header navigation bar:
- **ON**: J.A.R.V.I.S. automatically synthesizes and reads every incoming assistant message aloud as soon as the response stream finishes.
- **OFF**: Silent mode.
- **State Persistence**: Your preference is saved locally in your browser (`localStorage.jarvis_auto_speak`).

### 2. Per-Message Speak Button
At the bottom of every assistant message card, a **Speak** button allows listening to any specific message on demand:
- 🔇 **Idle ("Speak")**: Click to generate and stream audio.
- ⏳ **Loading ("Synthesizing...")**: Audio is being synthesized.
- 🔊 **Active ("Speaking", Animated Pulse)**: Currently playing audio. Clicking again halts playback.

---

## 📱 Telegram Voice Notes & Replies

You can receive spoken voice notes directly in your Telegram chat with J.A.R.V.I.S.:

### 1. On-Demand Toggle with `/voice`
Send the `/voice` command to your bot:
- `🎙️ Voice replies enabled`: The bot will now send an audio voice note (`reply_voice`) alongside every text response.
- `🔇 Voice replies disabled`: Reverts to text-only replies.

### 2. Permanent Voice Mode
Set `TELEGRAM_VOICE_REPLY=true` in `backend/.env` to enable audio voice note replies permanently.

---

## 🧹 Intelligent Speech Sanitization

Before sending text to Kokoro TTS, the backend sanitizes the output via `clean_text_for_speech()`:
1. **Removes Unicode Emojis**: Strips symbols like `💰`, `🌤️`, `⛽`, `🤖`, `🟢` so the TTS engine does not awkwardly transliterate them as *"money bag"* or *"fuel pump"*.
2. **Replaces Code Blocks**: Converts multi-line code blocks into verbal cues (`"(code block omitted)"`) to prevent reading out hundreds of lines of code.
3. **Strips Markdown Formatting**: Removes headers (`#`), bold/italics (`**`, `*`), blockquotes (`>`), and tables (`|---|`) for clean, fluid reading.
4. **Cleans Raw URLs**: Replaces long HTTP links with the word `"link"`.

---

## 🎭 Supported Voice Catalog

Kokoro includes a variety of high-quality British and American voices:

| Voice ID | Name | Language | Gender | Character Style |
| :--- | :--- | :---: | :---: | :--- |
| `bm_george` ⭐ | **George (Default)** | British (`en-gb`) | Male | Calm, poised British gentleman — **Authentic J.A.R.V.I.S.** |
| `bm_daniel` | Daniel | British (`en-gb`) | Male | Formal, crisp British male |
| `bm_lewis` | Lewis | British (`en-gb`) | Male | Conversational, natural British male |
| `bm_fable` | Fable | British (`en-gb`) | Male | Warm narrative British male |
| `bf_alice` | Alice | British (`en-gb`) | Female | Clear, polite British female |
| `bf_emma` | Emma | British (`en-gb`) | Female | Friendly British female |
| `am_adam` | Adam | US (`en-us`) | Male | Deep American male |
| `af_bella` | Bella | US (`en-us`) | Female | Warm American female |

---

## 📡 REST API Reference

### 1. Synthesize Speech (`POST /api/tts/speak`)
- **Headers**: `X-API-Key: <key>`
- **Request Body**:
  ```json
  {
    "text": "Good evening, Sir. All perimeter defenses are operational.",
    "voice": "bm_george",
    "speed": 1.0,
    "response_format": "mp3"
  }
  ```
- **Response**: `200 OK` with binary `audio/mpeg` audio stream.

### 2. List Voices (`GET /api/tts/voices`)
- Returns the complete catalog of supported Kokoro voices, descriptions, and language codes.

### 3. Check TTS Health (`GET /api/tts/status`)
- Returns the live connectivity status and base URL of the Kokoro TTS service.
