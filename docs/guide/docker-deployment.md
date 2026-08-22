# Docker & Production Deployment

This guide covers running J.A.R.V.I.S. in production environments using containerized multi-service topologies.

---

## 🐳 Production Docker Topology

J.A.R.V.I.S. includes a production-tuned configuration: `docker-compose.prod.yml`.

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-jarvis}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  tts:
    image: ghcr.io/remsky/kokoro-fastapi-cpu:latest
    restart: always
    ports:
      - "8880:8880"
    environment:
      - DEFAULT_VOICE=bm_george

  backend:
    image: ghcr.io/acedehra/jarvis-backend:${TAG:-latest}
    restart: always
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - tts

  frontend:
    image: ghcr.io/acedehra/jarvis-frontend:${TAG:-latest}
    restart: always
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
  backend_data:
```

---

## 🚀 Deploying to a VPS or Cloud Host

### 1. Provision Host
Ensure Docker and Docker Compose v2 are installed on your server (Ubuntu 22.04+ or Debian 12 recommended).

### 2. Clone Repository & Setup Secrets
```bash
git clone https://github.com/acedehra/jarvis.git
cd jarvis

# Create secure production environment
cp backend/.env.example backend/.env
nano backend/.env
```

### 3. Launch Containers
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. Reverse Proxy & SSL (Nginx / Caddy)

To serve the frontend and backend under your domain with SSL, configure Caddy:

```caddy
jarvis.yourdomain.com {
    reverse_proxy localhost:3000
}

api-jarvis.yourdomain.com {
    reverse_proxy localhost:8000
}
```

---

## 🩺 Healthchecks & Monitoring

- Backend Healthcheck: `GET /health`
- Swagger OpenAPI: `GET /docs`
- LangSmith Tracing: Configure `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` to stream live token usage, trace spans, and node latencies.
