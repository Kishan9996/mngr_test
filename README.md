# AI Calendar Scheduling Chatbot

A production-grade, conversational AI assistant that schedules appointments on **Google Calendar** and **Microsoft Outlook** via natural language. Built with **Python (FastAPI)** on the backend and **Next.js** on the frontend, powered by **Claude** (Anthropic) with tool-use.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Setup & Installation](#setup--installation)
   - [Docker (recommended)](#docker-recommended)
   - [Local development](#local-development)
5. [Running the Application](#running-the-application)
6. [Testing the Solution](#testing-the-solution)
7. [Example Usage](#example-usage)
8. [API Reference](#api-reference)
9. [Design Decisions](#design-decisions)
10. [Known Limitations](#known-limitations)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Next.js Frontend  (port 3000)                   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────┐  ┌────────┐  │
│  │ ChatInterface │  │ CalendarConnect   │  │ Bookings │  │Profile │  │
│  │ + useChat     │  │ + reconnect UI    │  │ View     │  │ Panel  │  │
│  └──────┬───────┘  └──────────────────┘  └──────────┘  └────────┘  │
│         │           AuthScreen (login / register)                    │
└─────────┼────────────────────────────────────────────────────────────┘
          │ HTTP + httpOnly cookie (auth_token)
          │ credentials: "include" on all requests
┌─────────▼────────────────────────────────────────────────────────────┐
│                      FastAPI Backend  (port 8000)                    │
│                                                                      │
│  RequestIDMiddleware → RequestLoggingMiddleware → CORSMiddleware      │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │/api/auth │  │/api/chat │  │/api/calendar    │  │/api/profile │  │
│  │rate: 5-10│  │rate: 30  │  │OAuth 2.0 flow   │  │working hours│  │
│  │/min      │  │/min      │  │events list      │  │preferences  │  │
│  └────┬─────┘  └────┬─────┘  └─────────────────┘  └─────────────┘  │
│       │             │                                                 │
│  ┌────▼─────────────▼──────────────────────────────────────────┐    │
│  │  AuthService (bcrypt + JWT)   ClaudeAIService (tool-use)    │    │
│  │  ProfileService               today's date in system prompt │    │
│  └─────────────────────────────────┬────────────────────────────┘    │
│                                    │                                  │
│  ┌─────────────────────────────────▼────────────────────────────┐    │
│  │              SchedulingService  (tool dispatcher)             │    │
│  │  • Past-date guard (3 layers)                                 │    │
│  │  • User working-hours profile fallback                        │    │
│  └─────────────────────────────────┬────────────────────────────┘    │
│                                    │                                  │
│  ┌─────────────────────────────────▼────────────────────────────┐    │
│  │  CalendarProvider  (Strategy + Template Method + Retry)       │    │
│  │  ┌────────────────────────┐  ┌────────────────────────────┐  │    │
│  │  │ GoogleCalendarProvider │  │ OutlookCalendarProvider     │  │    │
│  │  │ All calendars (not     │  │ All calendars via Graph API │  │    │
│  │  │ just primary)          │  │ + per-calendar events       │  │    │
│  │  │ 5-min list cache       │  │ 5-min list cache            │  │    │
│  │  └────────────────────────┘  └────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  DBSessionStore (Singleton)  ←→  SQLite  (chatbot.db)        │    │
│  │  Users · Sessions (server-owned IDs) · CalendarTokens        │    │
│  │  ConversationMessages · UserProfiles                          │    │
│  └──────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Strategy** | `CalendarProvider` base + Google/Outlook | Swap calendar backends without touching callers |
| **Factory Method** | `CalendarProviderFactory` | Instantiate the right provider from a string name |
| **Template Method** | `CalendarProvider.find_available_slots()` | Shared slot-filter algorithm; subclasses only override `get_busy_times` |
| **Singleton** | `DBSessionStore` | Single source of truth for all session state |
| **Command (dispatch table)** | `ClaudeAIService._dispatch()` | Route Claude tool calls without if-elif chains |
| **Dependency Injection** | FastAPI `Depends()` | Loose coupling; production vs. test stores swapped in one place |
| **Repository** | `AbstractSessionStore` ABC | Decouple storage from business logic; in-memory for tests, SQLite in production |

---

## Project Structure

```
chatbot Task/
├── .gitignore
├── README.md
│
├── backend/
│   ├── Makefile                        # venv management + dev tasks
│   ├── requirements.txt
│   ├── .env.example                    # copy to .env and fill in
│   └── app/
│       ├── main.py                     # FastAPI app, middleware wiring, sanitised error handlers
│       ├── core/
│       │   ├── config.py               # Pydantic Settings (reads .env)
│       │   ├── database.py             # SQLAlchemy engine + Base
│       │   ├── exceptions.py           # Custom exception hierarchy
│       │   ├── limiter.py              # Depends-based per-IP sliding-window rate limiter
│       │   └── logging.py              # Structured logging setup
│       ├── middleware/
│       │   ├── request_id.py           # Attaches X-Request-ID to every request/response
│       │   └── request_logging.py      # Logs method · path · status · duration · request_id
│       ├── models/
│       │   ├── appointment.py          # Domain dataclasses (TimeSlot, CalendarEvent, CalendarEventItem …)
│       │   ├── chat.py                 # API request/response models + ProcessResult
│       │   └── db.py                   # SQLAlchemy ORM models (User, UserSession, UserProfile …)
│       ├── services/
│       │   ├── auth/
│       │   │   └── auth_service.py     # JWT creation/verification, direct bcrypt hashing
│       │   ├── ai/
│       │   │   ├── base.py             # AIService ABC
│       │   │   └── claude_service.py   # Agentic loop, reconnect detection, today's date in prompt
│       │   ├── calendar/
│       │   │   ├── base.py             # CalendarProvider ABC + Template Method
│       │   │   ├── google_calendar.py  # All-calendar freebusy + events, retry, 5-min list cache
│       │   │   ├── outlook_calendar.py # All-calendar via Graph API, retry, 5-min list cache
│       │   │   └── factory.py          # CalendarProviderFactory
│       │   ├── profile/
│       │   │   └── profile_service.py  # Working hours / duration / timezone preferences
│       │   ├── scheduling/
│       │   │   └── scheduler.py        # Tool-call bridge, past-date guard, profile fallback
│       │   └── session/
│       │       ├── abstract_store.py   # AbstractSessionStore ABC
│       │       ├── session_store.py    # In-memory (tests)
│       │       └── db_session_store.py # SQLite-backed with server-owned session IDs
│       ├── api/
│       │   ├── deps.py                 # FastAPI dependency providers (cookie auth)
│       │   └── routes/
│       │       ├── auth.py             # /api/auth/* (register, login, logout, me)
│       │       ├── chat.py             # /api/chat/* (message, status, history)
│       │       ├── calendar.py         # /api/calendar/* (OAuth, events, disconnect)
│       │       └── profile.py          # /api/profile (GET, PATCH)
│       └── utils/
│           ├── cache.py                # TTLCache — 5-min calendar list cache
│           ├── date_utils.py           # Slot generation + past-slot filtering
│           └── retry.py                # with_retry decorator (exponential backoff)
│
├── backend/tests/
│   ├── conftest.py                     # Fixtures + dependency_overrides (in-memory store, fake auth)
│   ├── test_calendar_service.py
│   ├── test_scheduling.py
│   └── test_chat_api.py
│
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   └── page.tsx                    # Auth guard → AuthScreen or ChatInterface
    ├── components/
    │   ├── AuthScreen.tsx              # Login / register form
    │   ├── BookingsView.tsx            # Date-grouped event list from all connected calendars
    │   ├── CalendarConnect.tsx         # OAuth connect/disconnect + amber reconnect prompt
    │   ├── ChatInterface.tsx           # Chat + Bookings tab switcher, history loader
    │   ├── ChatMessage.tsx             # Message bubble (markdown-lite renderer)
    │   ├── ProfilePanel.tsx            # Working hours / duration / timezone settings
    │   └── TypingIndicator.tsx
    ├── hooks/
    │   ├── useAuth.ts                  # Cookie-based auth state; session_id from server
    │   └── useChat.ts                  # Conversation + history load + needsReconnect state
    └── lib/
        ├── api.ts                      # Fetch wrappers (credentials:include, 429/401 handling)
        ├── auth.ts                     # localStorage helpers (user info + server session_id)
        └── types.ts                    # Shared TypeScript interfaces
```

---

## Prerequisites

### Docker (recommended)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Filled-in `backend/.env` file (see below)

### Local development
- Python 3.10+ and `make`
- Node.js 18+ and npm
- Redis (optional — falls back to in-memory cache if not running)
- An [Anthropic API key](https://console.anthropic.com/)
- **Google Calendar** credentials — optional if only testing Outlook
- **Outlook / Azure** app registration — optional if only testing Google

---

## Setup & Installation

### Fill in `backend/.env` first (required for all methods)

```bash
cd "chatbot Task/backend"
cp .env.example .env
```

Edit `backend/.env`:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:///./chatbot.db
REDIS_URL=redis://localhost:6379        # redis://redis:6379 when using Docker

# Google Calendar (skip if testing Outlook only)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Outlook (skip if testing Google only)
OUTLOOK_CLIENT_ID=...
OUTLOOK_CLIENT_SECRET=...
OUTLOOK_TENANT_ID=common
```

#### Google Calendar OAuth setup

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project
2. **APIs & Services → Enable APIs** → **Google Calendar API**
3. **Credentials → Create Credentials → OAuth 2.0 Client ID** (Web application)
4. **Authorised redirect URIs**: `http://localhost:8000/api/calendar/auth/google/callback`
5. Copy **Client ID** and **Client secret** into `.env`
6. **OAuth consent screen** → add your test email as a test user

#### Outlook (Microsoft Graph) setup

1. [Azure Portal](https://portal.azure.com/) → **Azure AD → App registrations → New registration**
2. Supported accounts: **Accounts in any organizational directory and personal Microsoft accounts**
3. Redirect URI (Web): `http://localhost:8000/api/calendar/auth/outlook/callback`
4. **API permissions → Microsoft Graph → Delegated** → add `Calendars.ReadWrite` and `offline_access`
5. **Certificates & secrets → New client secret** — copy it immediately
6. Copy **Application (client) ID** and secret into `.env`

---

### Docker (recommended)

Runs the full stack — backend, frontend, and Redis — with one command. No Python or Node installation required on the host.

```bash
cd "chatbot Task"

# Set REDIS_URL=redis://redis:6379 in backend/.env (not localhost)
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Redis | localhost:6379 |

Stop: `docker compose down`  
Wipe volumes (DB + cache): `docker compose down -v`

> **Note:** After changing credentials in `backend/.env`, run `docker compose up --build` to rebuild.

---

### Local development

```bash
cd "chatbot Task"

# Backend
cd backend
make install          # creates .venv, installs all deps (including redis)
# Start Redis locally if you have it, or omit REDIS_URL to use in-memory cache

# Frontend
cd ../frontend
npm install
cp .env.example .env.local
```

---

## Running the Application

### Docker

```bash
docker compose up --build
# → http://localhost:3000
```

### Local (two terminals)

**Terminal 1 — Backend**
```bash
cd backend
make run        # → http://localhost:8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev     # → http://localhost:3000
```

The SQLite database (`backend/chatbot.db`) is created automatically on first start.  
Full reset: `make reset` (local) or `docker compose down -v` (Docker).

---

## Testing the Solution

### Backend unit & integration tests

```bash
cd backend
make test
```

38 tests, all running inside the venv with fully mocked calendar APIs and Claude — no real credentials needed.

```bash
# Docker
docker compose run --rm backend pytest tests/ -v

# Local
cd backend && make test
```

### Manual end-to-end walkthrough

1. Open **http://localhost:3000** and create an account
2. In the sidebar connect **Google Calendar** or **Outlook** via OAuth
3. Optionally set your **working hours** in the Schedule preferences panel
4. Type: *"Book a 1-hour team sync this week"* — the AI collects preferences, shows slots across all your calendars, and asks for confirmation before booking
5. Switch to the **Bookings** tab — see all upcoming events from all connected calendars, with a ↻ icon on recurring events
6. Stop the backend and restart — sign in again; your history, calendar connection, and working hours are all preserved

**Multi-user isolation test:** Log in as user A, have a conversation, log out. Log in as user B — confirm B sees an empty history and no calendar connections. Log in as user A in another browser — confirm A's history is fully restored.

**Reconnect prompt test:** Disconnect a calendar from the sidebar, then ask the AI to schedule something — an amber reconnect banner appears next to that provider.

**Rate limit test:** Hit `/api/auth/register` 6+ times in a minute from the same IP — the 6th request returns 429 with a `Retry-After` header.

### API docs (interactive)

`http://localhost:8000/docs`

---

## Example Usage

```
# First visit
[AuthScreen] Email: you@example.com  Password: ••••••••   [Create account]

# Chat tab
You:   I need to book a weekly team standup
AI:    How long should it be?
You:   30 minutes, recurring every Monday
AI:    Here are free Monday slots across your Google and Outlook calendars:
         1. Mon, Jan 20  ·  9:00 – 9:30 AM GMT
         2. Mon, Jan 20  · 11:00 – 11:30 AM GMT
       Which would you like?
You:   Option 1
AI:    Confirm: Weekly Team Standup, Mon 9:00 – 9:30 AM, repeating weekly.
       Shall I book it?
You:   Yes
AI:    Done! View it here: https://calendar.google.com/event?id=...

# Bookings tab — shows all upcoming events from Google + Outlook
# ↻ icon marks recurring events

# Next visit on a different device — sign in, everything is there
```

---

## API Reference

Authentication uses an **httpOnly cookie** (`auth_token`) set by the server. The browser sends it automatically — no `Authorization` header needed. Public endpoints: `/health`, `/api/auth/register`, `/api/auth/login`, `/api/calendar/auth/*/callback`.

### Auth · rate limited per IP

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/register` | `{email, password}` | Create account (5/min) → sets cookie, returns `{user_id, email, session_id}` |
| `POST` | `/api/auth/login` | `{email, password}` | Sign in (10/min) → sets cookie, returns `{user_id, email, session_id}` |
| `POST` | `/api/auth/logout` | — | Clears the auth cookie |
| `GET`  | `/api/auth/me` | — | Validate session → returns `{user_id, email, session_id}` |

### Chat · 30 requests/min per IP

| Method | Path | Params / Body | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/chat/message` | `{session_id, message, timezone}` | Send a message; returns `{response, connected_providers, needs_reconnect_providers}` |
| `GET`  | `/api/chat/status` | `?session_id=` | Connected provider list |
| `GET`  | `/api/chat/history` | `?session_id=` | Prior user/assistant turns (tool-use messages filtered out) |

### Calendar

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| `GET`  | `/api/calendar/auth/{provider}` | `?session_id=` | Start OAuth — browser cookie sent automatically, no token param |
| `GET`  | `/api/calendar/auth/{provider}/callback` | `?code=&state=` | Exchange code, store tokens per user |
| `DELETE` | `/api/calendar/disconnect/{provider}` | `?session_id=` | Remove tokens |
| `GET`  | `/api/calendar/events` | `?session_id=&days_ahead=30&timezone=` | Upcoming events from all connected calendars, merged and sorted |
| `GET`  | `/api/calendar/providers` | — | Supported provider list |

### Profile

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET`  | `/api/profile` | — | Working hours, default duration, timezone (creates defaults on first call) |
| `PATCH`| `/api/profile` | `{work_start?, work_end?, default_duration_minutes?, timezone?}` | Partial update |

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | `{status: ok|degraded, db: ok|error}` — pings SQLite |
| `GET`  | `/docs` | Interactive Swagger UI |

Every response includes `X-Request-ID` for log correlation.

---

## Design Decisions

### Session isolation — server-owned session IDs
Session IDs are assigned by the server, not the client. On login/register the server calls `get_or_create_for_user(user_id)` and returns the canonical `session_id`. The same user always gets the same session (history shared across devices). `link_session_to_user` hard-rejects (403) if a session already belongs to a different user. On logout, `clearSession()` wipes both user info and session_id from localStorage so the next user on the same browser cannot inherit them.

### httpOnly cookie auth
The JWT lives in an `httpOnly; SameSite=Lax` cookie managed entirely by the browser. No token in `localStorage` — eliminates the main XSS attack surface. All fetch calls use `credentials: "include"`. The OAuth start redirect sends the cookie automatically on browser navigation, so no token query param is needed.

### Observability
`RequestIDMiddleware` stamps every request with a 12-char hex ID echoed in `X-Request-ID`. `RequestLoggingMiddleware` logs `METHOD /path → STATUS Xms [rid]` — requests >2 s log at WARNING. Error responses include `request_id` for correlation. `/health` actively pings the DB and returns `"degraded"` if it's unreachable.

### Rate limiting
Implemented as a `Depends`-based sliding-window counter (`app/core/limiter.py`) rather than the slowapi decorator pattern — decorators on sync FastAPI routes alter the function signature inspection and cause 422 errors. Applied via `dependencies=[Depends(limit_auth_register)]` on the route decorator, leaving function signatures untouched.

### Past-date guard — three layers
1. `filter_available_slots` drops any slot ≤ now
2. `SchedulingService.get_available_slots` clamps `date_from` to the current time
3. `create_appointment` raises `PastBookingError` (400) if `start ≤ now`
Today's date is injected into the Claude system prompt on every turn so it cannot hallucinate past slots.

### Working hours profile
Each user has a `UserProfile` row with `work_start`, `work_end`, `default_duration_minutes`, and `timezone`. Created with sensible defaults on first access. Claude's `get_available_slots` tool omits work hour parameters by default — the scheduler fills them from the profile, with the conversation being able to override per-request.

### Multi-calendar support
Both providers query the user's full calendar list (not just "primary") for freebusy and event listing. Google uses the `calendarList` API + freebusy `items` array. Outlook queries each calendar individually via `/me/calendars/{id}/calendarView`. The calendar list is cached for 5 minutes per token prefix to avoid redundant API calls.

### Recurring events
Detected from `recurringEventId` / `recurrence` (Google) and `type: occurrence|seriesMaster` (Outlook). Shown with a ↻ icon in the bookings list. The `create_appointment` tool accepts an optional `recurrence` RRULE string (e.g. `RRULE:FREQ=WEEKLY;BYDAY=MO`), supported on Google Calendar.

### Claude with tool-use
Claude drives the conversation and decides when to call `get_connected_calendars`, `get_available_slots`, or `create_appointment`. `CalendarAuthError` inside a tool call is caught separately and surfaced as `needs_reconnect_providers` in the API response — the frontend shows an amber reconnect prompt without requiring a page reload.

### Retry with exponential backoff
`with_retry(max_attempts=3, backoff_base=1.0)` in `utils/retry.py` wraps `get_busy_times`, `create_event`, and `list_calendars` on both providers. Only retries on transient codes (429, 500–504) and network errors — 401/403 raise immediately.

### Strategy + Template Method for calendars
Adding a third provider (e.g. Apple Calendar) means implementing one class with four methods (`get_busy_times`, `get_upcoming_events`, `create_event`, `get_auth_url`) and one registry entry in `CalendarProviderFactory`. Zero changes to the AI layer, scheduler, or routes.

### Onboarding flow
New users go through a 3-step wizard (purpose/welcome → working hours → connect calendar) before reaching the chat. `UserProfile.onboarding_completed` persists the state; `init_db` adds the column to existing databases without requiring a migration tool.

### Redis cache with in-memory fallback
`app/utils/cache.py` tries to connect to Redis on first use. If the connection fails (Redis not running, wrong URL) it logs a warning and transparently falls back to the thread-safe in-memory `_MemoryCache`. Production deployments (Docker) get Redis; local development without Redis still works. Cached objects (calendar lists) are serialised as JSON via `dataclasses.asdict` so they round-trip correctly through Redis.

### Docker
Three services in `docker-compose.yml`: `redis` (alpine, persisted volume, health-checked), `backend` (python:3.11-slim, waits for Redis), `frontend` (Next.js standalone build, node:18-alpine). The frontend image uses Next.js's `output: "standalone"` mode to produce a minimal image without `node_modules` at runtime.

### Makefile-managed virtual environment
A stamp file (`$(VENV)/.installed`) means `make run` and `make test` only reinstall when `requirements.txt` changes. `make reset` wipes both `.venv` and `chatbot.db` for a completely clean start.

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| SQLite is single-writer | Fine for a demo; swap `DATABASE_URL` to PostgreSQL for concurrent production use — no code changes needed |
| Recurring event creation on Outlook | Google supports RRULE via the API. Outlook uses a different recurrence object model; creating recurring events on Outlook is not yet implemented |
| Working-hours DST edge cases | Slot times near clock-change transitions can shift by an hour; `zoneinfo` + `dateutil.rrule` would handle this precisely |
| No email verification on register | Users can register with any email. Add a verification step before enabling calendar connections in production |
| Google OAuth "Testing" mode | Newly created Google OAuth apps are in testing mode — tokens expire after 7 days unless the app is verified. Add your test emails as test users in the OAuth consent screen |
| Rate limits are in-process | The sliding-window counter resets on server restart and is not shared across multiple processes. Use Redis + a distributed rate limiter in a multi-instance deployment |
| Conversation history per session | Each user has one canonical session. There is no way to start a fresh conversation without resetting the database |
