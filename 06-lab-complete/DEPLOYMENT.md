# Deployment Information

## Public URL
https://day12-production-ec4c.up.railway.app

## Platform
Railway

## Service Summary
- App Service: day12
- Database Service: Redis
- Environment: production
- Last verified: 2026-04-17

## Test Commands And Live Results

### 1) Health Check
Command:
```bash
curl https://day12-production-ec4c.up.railway.app/health
```
Observed result:
```json
{
  "status": "ok",
  "uptime_seconds": 165.46,
  "instance_id": "fb941d097acb-3",
  "redis_connected": true,
  "in_flight_requests": 1,
  "timestamp": "2026-04-17T10:53:17.445475+00:00"
}
```

### 2) Authentication Required (No API Key)
Command:
```bash
curl -X POST https://day12-production-ec4c.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```
Observed result:
```text
HTTP_STATUS=401
```

### 3) Authenticated API Test (Valid API Key)
Command:
```bash
curl -X POST https://day12-production-ec4c.up.railway.app/ask \
  -H "X-API-Key: day12-secret-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"What is Docker?","session_id":"s1"}'
```
Observed result:
```json
{
  "question": "What is Docker?",
  "answer": "Container is a portable package for app + dependencies: build once, run anywhere.",
  "session_id": "s1",
  "usage": {
    "input_tokens": 4,
    "output_tokens": 19,
    "request_cost_usd": 0.000012,
    "budget_remaining_usd": 9.999988,
    "requests_remaining": 9
  },
  "instance_id": "fb941d097acb-4",
  "timestamp": "2026-04-17T10:54:06.127249+00:00"
}
```

### 4) Rate Limiting Test (Burst Requests)
Command:
```bash
# send 12 requests quickly with same user_id
```
Observed result:
```text
request_1=200
request_2=200
request_3=200
request_4=200
request_5=200
request_6=200
request_7=200
request_8=200
request_9=200
request_10=200
request_11=429
request_12=429
```

## Environment Variables Set (Railway)
- PORT=8000
- ENVIRONMENT=production
- REDIS_URL=${{Redis.REDIS_URL}}
- AGENT_API_KEY=day12-secret-key-2026
- RATE_LIMIT_PER_MINUTE=10
- RATE_LIMIT_WINDOW_SECONDS=60
- MONTHLY_BUDGET_USD=10
- GLOBAL_MONTHLY_BUDGET_USD=500

## Screenshots To Include
Add these files before final submission:
- screenshots/dashboard.png
- screenshots/running.png
- screenshots/test.png

## Notes
- Deployment build and Railway healthcheck succeeded.
- Redis connectivity is confirmed by `redis_connected: true` in `/health`.
- Service is publicly reachable and passed auth/rate-limit tests.
