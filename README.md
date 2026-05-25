# API Gateway with Billing

[![CI](https://github.com/your-org/api-gateway-key-management/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/api-gateway-key-management/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-grade API Gateway built with FastAPI. Handles key provisioning, per-tier rate limiting via Redis, and automatic billing tier updates through Stripe webhooks.

---

## Architecture

```
                        ┌──────────────────────────────────────────┐
                        │              API Gateway                  │
                        │                                          │
  Client ──X-API-Key──► │  ApiKeyMiddleware                        │
                        │    │  1. hash(key) → DB lookup           │
                        │    │  2. Redis INCR → rate limit check   │
                        │    │  3. inject request.state            │
                        │    ▼                                      │
                        │  Router                                  │
                        │    ├── POST /gateway/keys       (public) │
                        │    ├── GET  /gateway/keys/{id}/usage     │
                        │    ├── POST /api/v1/chat ──► Groq LLM   │
                        │    └── POST /webhooks/stripe   (public)  │
                        └───────────────┬──────────────────────────┘
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                     ▼
             PostgreSQL 16          Redis 7.4           Stripe Webhook
           (api_keys table)     (rate_limit:id:date)  (tier upgrades /
                                                        downgrades)
```

---

## Tech Stack

| Component | Version | Role |
|-----------|---------|------|
| Python | 3.14 | Runtime |
| FastAPI | 0.115 | HTTP framework |
| SQLAlchemy | 2.0 | Async ORM |
| asyncpg | 0.30 | PostgreSQL async driver |
| aiosqlite | 0.20 | SQLite driver (tests) |
| Redis (redis-py) | 5.2 | Rate limit counters |
| Stripe SDK | 10.x | Webhook signature verification |
| Groq SDK | 0.9 | LLM inference (llama-3.3-70b-versatile) |
| Pydantic | 2.10 | Schema validation |
| pytest-asyncio | 0.24 | Async test runner |
| PostgreSQL | 16 | Primary datastore |
| Redis | 7.4 | In-memory counter store |
| Docker Compose | 3.9 | Local orchestration |

---

## Quick Start (3 commands)

```bash
# 1. Copy env and fill in your secrets
cp .env.example .env

# 2. Start Postgres + Redis + API
docker compose up --build

# 3. Verify
curl http://localhost:8000/health
```

The API is now live at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

> **Railway deploy:** `https://api-gateway.up.railway.app` *(replace with your URL)*

---

## Rate Limiting

| Tier | Requests / day | Redis key |
|------|---------------|-----------|
| `free` | 100 | `rate_limit:{id}:{date}` |
| `pro` | 10 000 | `rate_limit:{id}:{date}` |
| `enterprise` | unlimited | — (Redis not queried) |

Counters use `INCR` + `EXPIRE 86400`. A new key is created each UTC day.

---

## Endpoints

### Create API Key (public)

```bash
curl -X POST http://localhost:8000/gateway/keys \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "tier": "free"}'
```

```json
{
  "id": 1,
  "user_id": "alice",
  "tier": "free",
  "key": "gw_a3f1b2c4d5e6...",
  "created_at": "2026-05-25T10:00:00Z"
}
```

> The raw key is shown **once**. Only the SHA-256 hash is stored.

---

### Get Usage Statistics (protected)

```bash
curl http://localhost:8000/gateway/keys/1/usage \
  -H "X-API-Key: gw_a3f1b2c4d5e6..."
```

```json
{
  "id": 1,
  "user_id": "alice",
  "tier": "free",
  "calls_today": 42,
  "calls_this_month": 312,
  "rate_limit_today": 100
}
```

---

### Chat via Groq LLM (protected, rate-limited)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: gw_a3f1b2c4d5e6..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain rate limiting in one sentence."}'
```

```json
{
  "response": "Rate limiting controls how many requests a client can make...",
  "model": "llama-3.3-70b-versatile",
  "tier": "free"
}
```

---

### Stripe Webhook (public, signature-verified)

```bash
# Simulated via Stripe CLI
stripe trigger checkout.session.completed \
  --override checkout_session:client_reference_id=alice \
  --override checkout_session:metadata.tier=pro
```

Events handled:
- `checkout.session.completed` → upgrades `user_id` to the tier in `metadata.tier`
- `customer.subscription.deleted` → downgrades `user_id` to `free`

---

## Data Model

```sql
CREATE TABLE api_keys (
  id               SERIAL PRIMARY KEY,
  key_hash         VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 of the raw key
  user_id          VARCHAR(255) NOT NULL,
  tier             VARCHAR(20)  NOT NULL DEFAULT 'free',
  calls_today      INTEGER      NOT NULL DEFAULT 0,
  calls_this_month INTEGER      NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ          DEFAULT now(),
  updated_at       TIMESTAMPTZ
);
```

---

## Running Tests

Tests use **SQLite in-memory** + **mocked Redis** — no Docker required.

```bash
pip install -r requirements-dev.txt
pytest -v
```

Expected output:

```
tests/test_keys.py::test_create_api_key_free         PASSED
tests/test_keys.py::test_get_usage_pro               PASSED
tests/test_middleware.py::test_valid_api_key_injects_state PASSED
tests/test_middleware.py::test_rate_limit_exceeded_returns_429 PASSED
tests/test_rate_limiter.py::test_enterprise_never_hits_redis PASSED
tests/test_webhooks.py::test_checkout_completed_upgrades_tier PASSED
...
```

---

## Architecture Decisions

### Why Redis for rate limiting instead of PostgreSQL counters?

PostgreSQL `UPDATE ... SET calls_today = calls_today + 1` under concurrent load creates row-level lock contention and requires a round-trip per request. Redis `INCR` is atomic, O(1), and designed for exactly this pattern. At 10 000 req/day per pro user, PostgreSQL would survive — but Redis lets the gateway stay sub-millisecond even at 10 000 req/minute for enterprise.

### Why middleware instead of a FastAPI dependency?

A `Depends()` runs **after** routing. Middleware intercepts the request before any handler runs, making it impossible to bypass auth by hitting an undocumented path. It also lets us short-circuit immediately (returning 401/429) without allocating a DB session for the route handler.

### Why store only the SHA-256 hash?

If the key table is leaked, an attacker still cannot impersonate users. SHA-256 is sufficient here (no bcrypt/argon2 needed) because API keys are already high-entropy random strings (UUID4 hex = 128 bits), unlike passwords. Lookup is O(1) via the unique index on `key_hash`.

### Why Stripe webhooks instead of polling Stripe's API?

Webhooks are push-based: the tier is updated within seconds of a payment completing. Polling requires a cron job, has latency proportional to the poll interval, and adds unnecessary Stripe API calls. Signature verification with `stripe.Webhook.construct_event` ensures the payload comes from Stripe, not an attacker.

---

## CI/CD

GitHub Actions runs on every push and pull request:

```yaml
# .github/workflows/ci.yml
- Lint: ruff + mypy
- Test: pytest (SQLite in-memory, no Docker)
- Build: docker build
```

---

## Git Workflow — Step by Step

See [GIT_GUIDE.md](GIT_GUIDE.md) for full commit and push instructions.
