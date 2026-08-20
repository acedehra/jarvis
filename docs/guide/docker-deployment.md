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

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-jarvis}
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
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
