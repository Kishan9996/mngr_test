# AI Data Extraction Chatbot

A production-grade, multi-tenant conversational AI that lets users query structured business data using plain English. Powered by **Claude** (Anthropic) with tool-use, built with **Python (FastAPI)** and **Next.js**.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Demo Organisations](#demo-organisations)
3. [Architecture Overview](#architecture-overview)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Setup & Installation](#setup--installation)
7. [Running the Application](#running-the-application)
8. [Makefile Reference](#makefile-reference)
9. [API Reference](#api-reference)
10. [Example Queries & Responses](#example-queries--responses)
11. [Testing Guide](#testing-guide)
12. [Design Decisions](#design-decisions)
13. [Known Limitations](#known-limitations)

---

## Quick Start

```bash
cd data_extraction_backend
cp .env.example .env          # add your ANTHROPIC_API_KEY
make install                  # creates .venv, installs all deps
make seed-all                 # loads sample CSVs + Acme Retail demo org
make dev                      # → http://localhost:8001
```

```bash
cd ../data_extraction_frontend
cp .env.example .env.local
npm install
npm run dev                   # → http://localhost:3001
```

Open http://localhost:3001, log in with one of the demo accounts below, and start asking questions.

---

## Demo Organisations

Two fully isolated organisations are created by `make seed-all`. They share no data.

| Organisation | Admin email | Password | Data source | Notes |
|---|---|---|---|---|
| **MNGR Demo** | `admin@mngr.com` | `changeme123` | Provided CSV files | 15 customers, 25 orders, 15 tickets |
| **Acme Retail** | `admin@acme-retail.com` | `acme123456` | Built-in demo data | 7 customers, 10 orders, 7 tickets |

Acme Retail is specifically designed to exercise corner cases:
- Two customers named **Alice** (Thompson and Nguyen) → tests disambiguation flow
- **James Wilson** — ecommerce-only (no support tickets)
- **Rachel Kim** — support-only (no orders)
- **David Park** — suspended account with an open ticket

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                   Next.js Frontend  (port 3001)                      │
│                                                                      │
│   AuthScreen (login / register / org creation)                       │
│   ChatInterface (suggestion chips, message history, typing dots)     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ HTTP + httpOnly cookies
                          │ access_token (15 min) + refresh_token (7 d)
┌─────────────────────────▼────────────────────────────────────────────┐
│                   FastAPI Backend  (port 8001)                        │
│                                                                      │
│   RequestIDMiddleware → RequestLoggingMiddleware → CORSMiddleware     │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ /api/auth   │  │ /api/chat   │  │ /api/seed│  │   /health    │  │
│  │ register    │  │ message     │  │ admin    │  │              │  │
│  │ login       │  │ history     │  │ only     │  │              │  │
│  │ refresh     │  │ clear       │  │          │  │              │  │
│  │ logout / me │  │             │  │          │  │              │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┘  └──────────────┘  │
│         │                │                                            │
│  ┌──────▼────────────────▼──────────────────────────────────────┐   │
│  │  AuthService              ClaudeExtractionService            │   │
│  │  access + refresh JWT     Anthropic prompt cache             │   │
│  │  token rotation           history compression                │   │
│  │  bcrypt passwords         result truncation (15 rows max)    │   │
│  └───────────────────────────────┬──────────────────────────────┘   │
│                                  │ tool dispatch (org_id injected)   │
│  ┌───────────────────────────────▼──────────────────────────────┐   │
│  │              QueryCache  (TTL per tool, thread-safe)          │   │
│  └───────────────────────────────┬──────────────────────────────┘   │
│                                  │ cache miss only                   │
│  ┌───────────────────────────────▼──────────────────────────────┐   │
│  │  CustomerRepository   EcommerceRepository                    │   │
│  │  SupportRepository    CrossDomainRepository                  │   │
│  └───────────────────────────────┬──────────────────────────────┘   │
│                                  │                                    │
│  ┌───────────────────────────────▼──────────────────────────────┐   │
│  │  SQLite  (extraction.db)  — WAL mode, 64 MB cache, mmap      │   │
│  │  organizations · users · refresh_tokens                      │   │
│  │  customers (canonical) · ecom_* · support_*                  │   │
│  │  chat_sessions · session_messages                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Strategy** | `AIService` ABC → `ClaudeExtractionService` | Swap LLM without touching callers |
| **Repository** | `DataRepository` ABC → 4 concrete repos | Decouple SQL from business logic |
| **Dispatch table** | `ClaudeExtractionService._dispatch()` | Route tool calls without if-elif chains |
| **Cache-aside** | `QueryCache` wrapping every `_dispatch` call | DB only hit on cache miss |
| **Two-token auth** | `security.py` + `AuthService` | Short-lived access + rotatable refresh tokens |
| **Shared kernel** | `customers` table + domain extension tables | Single canonical identity, domain-specific attributes |

---

## Project Structure

```
data_extraction_backend/
├── schema.sql                          # Full DDL with indexes — source of truth
├── seed.py                             # Multi-tenant CSV loader + Acme Retail demo seeder
├── requirements.txt
├── .env.example
├── Makefile
├── Dockerfile
└── app/
    ├── main.py                         # FastAPI app, middleware, error handlers
    ├── core/
    │   ├── config.py                   # Pydantic Settings (reads .env)
    │   ├── database.py                 # SQLAlchemy engine + WAL PRAGMAs
    │   ├── exceptions.py               # Custom exception hierarchy
    │   ├── security.py                 # JWT (access + refresh), bcrypt, revocation
    │   └── logging.py                  # Structured stdout logging
    ├── middleware/
    │   ├── request_id.py               # X-Request-ID on every request/response
    │   └── request_logging.py          # method · path · status · duration · rid
    ├── models/
    │   ├── db.py                       # SQLAlchemy ORM (14 tables)
    │   └── schemas.py                  # Pydantic request/response + ExtractionSession
    ├── services/
    │   ├── ai/
    │   │   ├── base.py                 # AIService ABC
    │   │   └── claude_extraction_service.py  # Tool-use loop, caching, compression
    │   ├── auth/
    │   │   └── auth_service.py         # register / login / refresh / logout
    │   ├── cache/
    │   │   └── query_cache.py          # TTL cache keyed by (org_id, tool, params)
    │   ├── data/
    │   │   ├── base.py                 # DataRepository ABC
    │   │   ├── customer_repository.py  # Name/email lookup, domain presence
    │   │   ├── ecommerce_repository.py # Orders, aggregates, products
    │   │   ├── support_repository.py   # Tickets, interactions, agents
    │   │   └── cross_domain_repository.py  # Spans both domains
    │   └── session/
    │       ├── abstract_store.py       # AbstractSessionStore ABC
    │       └── db_session_store.py     # SQLite-backed, entity cache in context_json
    └── api/
        ├── deps.py                     # FastAPI DI: current_user, require_admin
        └── routes/
            ├── auth.py                 # httpOnly cookie management
            ├── chat.py                 # Cross-org session guard
            ├── seed.py                 # Admin-only data ingestion
            └── health.py
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+ (frontend only)
- `make`
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup & Installation

### 1. Configure environment

```bash
cd data_extraction_backend
cp .env.example .env
```

Open `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:///./extraction.db
FRONTEND_URL=http://localhost:3001
```

### 2. Install dependencies

```bash
make install
# Creates .venv and installs all Python packages.
# Safe to run repeatedly — only reinstalls when requirements.txt changes.
```

### 3. Seed the database

```bash
# Option A — MNGR Demo org only (from the provided CSV files):
make seed

# Option B — Both orgs (recommended for testing corner cases):
make seed-all
```

`seed-all` creates two fully isolated organisations — see [Demo Organisations](#demo-organisations) for credentials.

To seed a different organisation from your own CSV files:

```bash
.venv/bin/python seed.py \
  --org-name   "Your Company" \
  --data-dir   /path/to/your/csv/folder \
  --admin-email    you@yourco.com \
  --admin-password yourpassword
```

**Expected CSV layout:**

```
<data-dir>/
├── ecommerce/
│   ├── ecom_customers.csv      (id, name, email, location)
│   ├── ecom_orders.csv         (id, customer_id, order_date, total_amount)
│   ├── ecom_products.csv       (id, name, description, price, category_id)
│   └── ecom_categories.csv     (id, name, description)
└── support/
    ├── support_customers.csv   (id, name, email, contact_info, account_status)
    ├── support_tickets.csv     (id, title, description, customer_id, status, priority)
    ├── support_agents.csv      (id, name, department, expertise)
    └── support_interactions.csv (id, ticket_id, agent_id, timestamp, notes)
```

---

## Running the Application

### Local

```bash
# Terminal 1 — Backend
cd data_extraction_backend
make dev          # → http://localhost:8001  (Swagger: http://localhost:8001/docs)

# Terminal 2 — Frontend
cd data_extraction_frontend
npm run dev       # → http://localhost:3001
```

### Docker

```bash
cd "chatbot Task"
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8001 |
| Swagger | http://localhost:8001/docs |

---

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make install` | Create `.venv` and install all dependencies |
| `make dev` | Start backend in hot-reload mode on port 8001 |
| `make seed` | Seed MNGR Demo org from CSV files |
| `make seed-all` | Seed MNGR Demo + Acme Retail demo org |
| `make test` | Run pytest test suite |
| `make lint` | Run ruff linter |
| `make clean` | Remove `.venv` and `__pycache__` (keeps DB and `.env`) |
| `make reset` | `clean` + delete `extraction.db` (full fresh start) |

---

## API Reference

Authentication uses **httpOnly cookies** set by the server. The browser sends them automatically — no `Authorization` header required.

- `access_token` — short-lived (15 min), used on every request
- `refresh_token` — longer-lived (7 days), path-scoped to `/api/auth/refresh` only

### Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/register` | `{email, password, org_name}` | Creates user + org → sets both cookies |
| `POST` | `/api/auth/login` | `{email, password}` | Signs in → sets both cookies |
| `POST` | `/api/auth/refresh` | — | Rotates token pair (old refresh token revoked atomically) |
| `POST` | `/api/auth/logout` | — | Revokes refresh token, clears both cookies |
| `GET`  | `/api/auth/me` | — | Returns `{user_id, email, org_id, org_name, role}` |

### Chat

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/chat/message` | `{message, session_id?}` | Send message → `{reply, session_id}` |
| `GET`  | `/api/chat/history/{session_id}` | — | Text turns only (tool call blocks filtered out) |
| `DELETE` | `/api/chat/history/{session_id}` | — | Clear conversation history + entity cache for this session |

### Seed (admin role only)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/seed` | `{data_dir, org_name, admin_email, admin_password}` | Load CSVs into a new or existing org. Idempotent. Flushes query cache after seeding. |

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{status, db, service}` — pings SQLite |
| `GET` | `/docs` | Interactive Swagger UI |

Every response includes an `X-Request-ID` header for log correlation.

---

## Example Queries & Responses

Log in as `admin@mngr.com` / `changeme123` (MNGR Demo org).

### Single-customer order lookup
```
You:  Show me all orders from Alice Chen in the last month
AI:   Alice Chen placed 2 orders in April 2026:
      • 26 Apr 2026 — £59.00
      • 18 Apr 2026 — £199.99
      Total: £258.99
```

### Open support tickets
```
You:  List all open support tickets for Ben Okafor
AI:   Ben Okafor has 1 open ticket:
      • "Refund for damaged smartphone" — High priority, open since 04 May 2026
```

### Cross-domain aggregate
```
You:  What is the total order value for each customer who has open support tickets?
AI:   Customers with open tickets and their total spend:
      1. Alice Chen — £732.49 (4 orders)
      2. Ben Okafor — £449.00 (1 order)
      3. Carla Rossi — £699.00 (1 order)
      ...
```

### No-purchase customers
```
You:  Find customers who have made purchases but never raised support tickets
AI:   3 customers have placed orders but have no support tickets on record:
      • Kojo Mensah
      • Lina Andersson
      • Mateo Silva
```

### Customer with no orders (MNGR Demo)
```
You:  Show me orders for Nadia Khoury
AI:   Nadia Khoury has no orders on record.
      She does have 1 support ticket: "Password reset not working" (open, medium priority).
```

---

## Testing Guide

### Run the test suite

```bash
make test
```

### Manual walkthrough

1. Open http://localhost:3001 and log in (or use Swagger at http://localhost:8001/docs)
2. Start with a suggestion chip or type a query

---

### Corner Cases

The following scenarios verify known edge cases. Run `make seed-all` first so both orgs exist.

Log in as **`admin@mngr.com`** for Groups A–F, **`admin@acme-retail.com`** for Group H.

---

#### Group A — Customer Resolution

| # | Query | Expected behaviour |
|---|-------|--------------------|
| A1 | `"Show me orders for Alice Chen"` | Single match → proceeds directly |
| A2 | `"Show me orders for alice chen"` | Case-insensitive → same result as A1 |
| A3 | `"Show me orders for Alice"` | Multiple matches → Claude lists all with name, email, id and asks to clarify |
| A4 | `"Show me orders for nobody@fake.com"` | `"No customer matching..."` — asks to check the email |
| A5 | `"What did alice.chen@example.com order?"` | Email lookup (exact, unambiguous) |
| A6 | Ask about Alice (msg 1), then `"What about her tickets?"` | Claude reuses cached `customer_id` — does **not** call `lookup_customer` again |

---

#### Group B — Domain Gaps

| # | Query | Expected behaviour |
|---|-------|--------------------|
| B1 | `"Show me support tickets for Kojo Mensah"` | Ecommerce-only → `"no support tickets on record"`, not `"customer not found"` |
| B2 | `"Show me orders for Nadia Khoury"` | Support-only → `"no orders on record"` |
| B3 | `"Tell me everything about Nadia Khoury"` | Full profile: orders = 0, tickets listed — both gaps acknowledged |

---

#### Group C — Relative Dates *(today = 2026-05-13)*

| # | Query | Date range Claude must use |
|---|-------|---------------------------|
| C1 | `"Show me orders from last month"` | `2026-04-01` → `2026-04-30` |
| C2 | `"Any orders in the last 7 days?"` | `2026-05-06` → `2026-05-13` |
| C3 | `"Orders from Q1 this year"` | `2026-01-01` → `2026-03-31` |
| C4 | `"Orders from yesterday"` | `2026-05-12` → `2026-05-12` |
| C5 | `"Orders in May"` | `2026-05-01` → `2026-05-31` |

> Dates must reach the tool as `YYYY-MM-DD`. Any other format is rejected with a clear error.

---

#### Group D — Cross-Domain Queries

| # | Query | Expected behaviour |
|---|-------|--------------------|
| D1 | `"Total order value for each customer who has open support tickets"` | Cross-domain join: aggregated spend + open ticket filter |
| D2 | `"Find customers who purchased but never raised a support ticket"` | `filter=ecommerce_only` → Kojo Mensah, Lina Andersson, Mateo Silva |
| D3 | `"Which customers raised tickets but never ordered?"` | `filter=support_only` → Nadia Khoury, Oscar Nilsen |
| D4 | `"Show me Alice's full history"` | `get_customer_full_profile` → orders + tickets in one response |
| D5 | `"Who are our highest spending customers with open issues?"` | Claude chains spend aggregate + open ticket filter |

---

#### Group E — Ambiguous Natural Language

| # | Query | Expected behaviour |
|---|-------|--------------------|
| E1 | `"Show me all urgent tickets"` | `"urgent"` is not a valid priority — Claude should map to `high` or ask to confirm |
| E2 | `"List tickets that aren't closed"` | Must cover both `open` and `in_progress`, not just one |
| E3 | `"Show me recent orders"` | No date given — Claude asks "how recent?" or defaults to last 30 days |
| E4 | `"How many customers do we have?"` | Ambiguous domain — Claude clarifies or answers all three counts |
| E5 | `"High priority open tickets for Ben"` | Multi-filter: `customer_id=X, status=open, priority=high` |

---

#### Group F — query_with_schema Safety

| # | Query | Expected behaviour |
|---|-------|--------------------|
| F1 | `"Delete all orders from Alice"` | No delete tool exists. If Claude attempts `query_with_schema` with `DELETE`, rejected: *"Only SELECT statements are permitted"* |
| F2 | Type raw SQL without `:org_id` placeholder | Rejected: *"Query must include :org_id placeholder"* |
| F3 | `"How many products are in each category?"` | Falls back to `query_with_schema` with valid `SELECT` — returns category counts |

---

#### Group G — Authentication & Authorisation

| # | Scenario | Expected behaviour |
|---|----------|--------------------|
| G1 | Call `POST /api/chat/message` with no cookies | `401 Not authenticated` |
| G2 | Call `POST /api/auth/refresh` after logout | `401 Refresh token has been revoked` |
| G3 | Reuse a refresh token after it has been rotated (replay attack) | `401` — token was revoked on first use |
| G4 | Call `POST /api/seed` logged in as a `member` role user | `403 Admin access required` |
| G5 | Let access token expire (15 min), call `POST /api/auth/refresh` | New token pair issued, old refresh revoked |

---

#### Group H — Multi-Org Isolation *(requires `make seed-all`)*

Log in as `admin@acme-retail.com` for H1–H3, then compare with `admin@mngr.com`.

| # | Scenario | Expected behaviour |
|---|----------|-------------------|
| H1 | Log in as MNGR Demo, ask `"List all customers"` | Returns only MNGR Demo's 15 customers |
| H2 | Log in as Acme Retail, ask `"List all customers"` | Returns only Acme Retail's 7 customers |
| H3 | Acme: `"Show me orders for Alice"` | Two matches: Alice Thompson and Alice Nguyen — disambiguation required |
| H4 | MNGR: `"Show me orders for James Wilson"` | `"No customer matching 'James Wilson'"` — he only exists in Acme Retail |
| H5 | Acme: `"Show me tickets for Rachel Kim"` | Support-only — `"no orders on record"` but tickets shown |
| H6 | Acme: `"Show me orders for James Wilson"` | Ecommerce-only — orders shown, `"no support tickets on record"` |

---

## Design Decisions

### Shared customer identity (Option C)
Customers from both CSV domains are merged at seed time using email as the key, into a single `customers` table. Domain-specific attributes (`location`, `contact_info`, `account_status`) live in separate extension tables. All order and ticket foreign keys point to `customers.id` — cross-domain queries are a clean SQL JOIN, not a fragile email-match at query time.

### Two-token JWT strategy
**Access tokens** (15 min) are stateless — validated by signature alone, no DB lookup per request. **Refresh tokens** (7 days) have a `jti` UUID stored in the `refresh_tokens` table. On `/auth/refresh` the old `jti` is revoked and a new pair is issued atomically. Replaying an old refresh token is rejected immediately. Logout marks the current `jti` as revoked.

### org_id never in tool input
Claude's tool schemas have no `org_id` parameter. It is injected exclusively from the authenticated session in `_dispatch()`. Cross-org data leakage is structurally impossible — not merely a convention.

### Three-layer memory model
1. **Operational data** — SQLite, queried on demand via tools; never put into the context window
2. **Schema knowledge** — injected once per request in the system prompt (Anthropic-cached, ~90% token discount)
3. **Conversation memory** — message history in `session_messages`; resolved customer IDs cached in `chat_sessions.context_json` to avoid repeat `lookup_customer` calls

### Anthropic prompt caching
The static system prompt block (schema + rules, ~1500 tokens) is marked `cache_control: ephemeral`. Anthropic caches it for 5 minutes — the dynamic block (today's date + resolved entities) is tiny and sent fresh each turn.

### Name disambiguation
If `lookup_customer` returns `count > 1`, Claude is required to stop, present the full list (name + email + id), and ask the user to confirm before any further queries. The entity cache is only populated on unambiguous (`count == 1`) lookups.

### Query result caching
`QueryCache` is a thread-safe, per-tool TTL cache keyed by `(org_id, sha256(params)[:12])`. Different TTLs per tool: 2 min for tickets (status changes), 5 min for order aggregates. `invalidate_org()` is called after every seed operation.

### Date validation
`date_from`/`date_to` are validated against `YYYY-MM-DD` at the repository layer before any SQL runs. A bad format (e.g. `"May 2026"`) raises a `DataServiceError` that Claude surfaces as a helpful message, rather than silently returning 0 rows.

### SQLite performance
Six PRAGMAs on every connection: `WAL` (concurrent reads during writes), `NORMAL` sync, 64 MB page cache, `MEMORY` temp store, 256 MB `mmap_size`. Composite indexes on all hot paths: `(org_id, email)`, `(org_id, customer_id)`, `(org_id, order_date)`, `(org_id, status)`.

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| No order line items | The sample data has `total_amount` per order but no `order_items` table. Product-per-order breakdown is not available. |
| SQLite single-writer | Fine for demo; swap `DATABASE_URL` to PostgreSQL for concurrent production use — no code changes needed |
| Stale refresh tokens accumulate | Expired/revoked tokens stay in the DB. Add a nightly `DELETE FROM refresh_tokens WHERE expires_at < now()` for production. |
| In-process query cache | Resets on server restart, not shared across processes. Replace `QueryCache` with a Redis backend for multi-instance deployments. |
| CSV column contract | `seed.py` expects exact column names from the provided sample files. Different schemas require a mapping layer before seeding. |
| One session per user | One canonical chat session per user. Start fresh by calling `DELETE /api/chat/history/{session_id}` or `make reset`. |
