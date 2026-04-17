# Day 12 - Production Ready AI Agent

Final lab implementation combining all concepts:

- API key authentication
- Rate limiting: 10 requests / 60 seconds / user
- Cost guard: 10 USD monthly budget / user (with global budget guard)
- Health and readiness probes
- Graceful shutdown (SIGTERM/SIGINT)
- Stateless session history in Redis
- Structured JSON logging
- Multi-stage Docker build
- Nginx + agent + Redis full stack

## Project Structure

```
06-lab-complete/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── auth.py
│   ├── rate_limiter.py
│   └── cost_guard.py
├── utils/
│   └── mock_llm.py
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── requirements.txt
├── .env.example
├── .dockerignore
├── railway.toml
└── render.yaml
```

## Local Run with Docker Compose

1. Copy environment file:

```bash
cp .env.example .env
```

2. Start stack:

```bash
docker compose up --build
```

3. Optional scaling test:

```bash
docker compose up --build --scale agent=3
```

4. Test endpoints:

```bash
# Liveness
curl http://localhost/health

# Readiness
curl http://localhost/ready

# Ask API (replace API key)
curl -X POST http://localhost/ask \
  -H "X-API-Key: replace-with-strong-secret" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"student1","question":"What is Docker?","session_id":"s1"}'
```

## Local Run without Docker

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start Redis locally.

3. Export environment variables (or use .env loader in your shell), then run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Security and Reliability Notes

- No hardcoded production secrets in source code.
- In production, AGENT_API_KEY must be set.
- Readiness returns 503 while shutting down or when Redis is unavailable.
- Session state is saved in Redis using key prefix session:<session_id>:history.
- Shutdown waits for in-flight requests up to SHUTDOWN_GRACE_SECONDS.

## Deployment

### Railway

- Uses Dockerfile build and start command from railway.toml.
- Set variables at minimum:
  - PORT
  - REDIS_URL
  - AGENT_API_KEY
  - RATE_LIMIT_PER_MINUTE
  - MONTHLY_BUDGET_USD

### Render

- Uses render.yaml blueprint.
- Add secret values for:
  - OPENAI_API_KEY (optional in mock mode)
  - AGENT_API_KEY

## Validation Script

Run the built-in checker:

```bash
python check_production_ready.py
```

This verifies required files, endpoint presence, security checks, and Docker best practices.
