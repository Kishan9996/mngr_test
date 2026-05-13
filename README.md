# AI Calendar Scheduling Chatbot

A production-grade, conversational AI assistant that schedules appointments on **Google Calendar** and **Microsoft Outlook** via natural language. Built with **Python (FastAPI)** on the backend and **Next.js** on the frontend, powered by **Claude** (Anthropic) with tool-use.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Setup & Installation](#setup--installation)
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
│  ┌─────────────────────┐   ┌──────────────────┐   ┌─────────────┐  │
│  │  ChatInterface       │   │ CalendarConnect   │   │  AuthScreen │  │
│  │  (useChat hook)      │   │ (reconnect UI)    │   │ (JWT auth)  │  │
│  └──────────┬──────────┘   └──────────────────┘   └─────────────┘  │
└─────────────┼────────────────────────────────────────────────────────┘
              │ HTTP/REST  +  Authorization: Bearer <JWT>
┌─────────────▼────────────────────────────────────────────────────────┐
│                      FastAPI Backend  (port 8000)                    │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │  /api/auth     │  │  /api/chat     │  │  /api/calendar/auth    │ │
│  │  register/login│  │  message/status│  │  OAuth 2.0 flow        │ │
│  └────────┬───────┘  └───────┬────────┘  └────────────────────────┘ │
│           │                  │                                        │
│  ┌────────▼──────────────────▼──────────────────────────────────┐   │
│  │  AuthService         ClaudeAIService                          │   │
│  │  JWT · bcrypt        Tool-use loop + reconnect detection      │   │
│  └────────────────────────────┬──────────────────────────────────┘   │
│                               │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐   │
│  │              SchedulingService  (tool dispatcher)              │   │
│  └────────────────────────────┬──────────────────────────────────┘   │
│                               │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐   │
│  │  CalendarProvider  (Strategy + Template Method + Retry)        │   │
│  │  ┌──────────────────────────┐  ┌──────────────────────────┐   │   │
│  │  │  GoogleCalendarProvider  │  │  OutlookCalendarProvider  │   │   │
│  │  │  google-api-python-client│  │  Microsoft Graph API      │   │   │
│  │  └──────────────────────────┘  └──────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  DBSessionStore (Singleton)  ←→  SQLite  (chatbot.db)        │    │
│  │  Users · Sessions · Calendar tokens · Conversation history   │    │
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
| **Repository** | `AbstractSessionStore` ABC | Decouple storage details from business logic; in-memory used in tests, SQLite in production |

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
│       ├── main.py                     # FastAPI app + lifespan (DB init)
│       ├── core/
│       │   ├── config.py               # Pydantic Settings (reads .env)
│       │   ├── database.py             # SQLAlchemy engine + Base
│       │   ├── exceptions.py           # Custom exception hierarchy
│       │   └── logging.py              # Structured logging setup
│       ├── models/
│       │   ├── appointment.py          # Domain dataclasses (TimeSlot, CalendarEvent …)
│       │   ├── chat.py                 # API request/response + ProcessResult
│       │   └── db.py                   # SQLAlchemy ORM models
│       ├── services/
│       │   ├── auth/
│       │   │   └── auth_service.py     # JWT creation/verification, bcrypt hashing
│       │   ├── ai/
│       │   │   ├── base.py             # AIService ABC
│       │   │   └── claude_service.py   # Claude tool-use loop + reconnect detection
│       │   ├── calendar/
│       │   │   ├── base.py             # CalendarProvider ABC + Template Method
│       │   │   ├── google_calendar.py  # Google implementation (+ retry)
│       │   │   ├── outlook_calendar.py # Outlook implementation (+ retry)
│       │   │   └── factory.py          # CalendarProviderFactory
│       │   ├── scheduling/
│       │   │   └── scheduler.py        # Tool-call bridge (AI → calendar)
│       │   └── session/
│       │       ├── abstract_store.py   # AbstractSessionStore ABC
│       │       ├── session_store.py    # In-memory (tests)
│       │       └── db_session_store.py # SQLite-backed (production)
│       ├── api/
│       │   ├── deps.py                 # FastAPI dependency providers
│       │   └── routes/
│       │       ├── auth.py             # /api/auth/*
│       │       ├── chat.py             # /api/chat/*
│       │       └── calendar.py         # /api/calendar/*
│       └── utils/
│           ├── date_utils.py           # Slot generation + filtering
│           └── retry.py                # with_retry decorator (exponential backoff)
│
├── backend/tests/
│   ├── conftest.py                     # Fixtures + dependency overrides
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
    │   ├── ChatInterface.tsx           # Main chat layout
    │   ├── ChatMessage.tsx             # Message bubble (markdown-lite)
    │   ├── CalendarConnect.tsx         # OAuth buttons + reconnect prompt
    │   └── TypingIndicator.tsx
    ├── hooks/
    │   ├── useAuth.ts                  # JWT state (login / register / logout)
    │   └── useChat.ts                  # Conversation state + needsReconnect
    └── lib/
        ├── api.ts                      # Fetch wrappers (auth headers injected)
        ├── auth.ts                     # localStorage helpers for JWT
        └── types.ts                    # Shared TypeScript interfaces
```

---

## Prerequisites

### Backend
- Python 3.10+
- `make` (pre-installed on macOS/Linux; Windows users can use Git Bash or WSL)
- An [Anthropic API key](https://console.anthropic.com/)
- **Google Calendar** credentials (see below) — optional if only testing Outlook
- **Outlook / Azure** app registration (see below) — optional if only testing Google

### Frontend
- Node.js 18+
- npm / yarn / pnpm

---

## Setup & Installation

### 1. Enter the project

```bash
cd "chatbot Task"
```

### 2. Backend — one command

```bash
cd backend
cp .env.example .env      # then fill in your credentials (see below)
make install              # creates .venv and installs all dependencies
```

The Makefile manages the virtual environment entirely — you never need to activate it manually. Every `make` command (run, test, lint) automatically uses `.venv/bin/`.

> **Re-installing after adding packages:** Just run `make install` again. The Makefile uses a stamp file so it only reinstalls when `requirements.txt` actually changes.

#### Fill in `backend/.env`

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<output of: python3 -c "import secrets; print(secrets.token_hex(32))">

# Google Calendar (skip if testing Outlook only)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Outlook (skip if testing Google only)
OUTLOOK_CLIENT_ID=...
OUTLOOK_CLIENT_SECRET=...
OUTLOOK_TENANT_ID=common
```

#### Google Calendar Setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. **APIs & Services → Enable APIs** → enable **Google Calendar API**
3. **Credentials → Create Credentials → OAuth 2.0 Client ID** — choose **Web application**
4. Add this to **Authorised redirect URIs**: `http://localhost:8000/api/calendar/auth/google/callback`
5. Copy the **Client ID** and **Client secret** into `.env`
6. Under **OAuth consent screen**, add your test Google account as a test user

#### Outlook (Microsoft Graph) Setup

1. Open [Azure Portal](https://portal.azure.com/) → **Azure Active Directory → App registrations → New registration**
2. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
3. Redirect URI (Web): `http://localhost:8000/api/calendar/auth/outlook/callback`
4. **API permissions → Microsoft Graph → Delegated** → add `Calendars.ReadWrite` and `offline_access`
5. **Certificates & secrets → New client secret** — copy the value immediately
6. Copy the **Application (client) ID** and secret into `.env`

### 3. Frontend

```bash
cd ../frontend
npm install
cp .env.example .env.local
# .env.local already contains: NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running the Application

Open **two terminals**:

**Terminal 1 — Backend**
```bash
cd backend
make run
# → http://localhost:8000  (API docs at /docs)
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
# → http://localhost:3000
```

> The SQLite database (`backend/chatbot.db`) is created automatically on first start. To wipe it and start fresh: `make reset`.

---

## Testing the Solution

### Backend unit & integration tests

```bash
cd backend
make test
```

All 37 tests run in the venv with no real credentials needed — calendar APIs and Claude are fully mocked.

### Manual end-to-end walkthrough

1. Open **http://localhost:3000**
2. **Create an account** (or sign in if you've been here before) — your conversation history and calendar connections persist across sessions and server restarts
3. In the sidebar, click **Connect** next to **Google Calendar** or **Outlook Calendar** and complete the OAuth consent
4. The sidebar shows **Connected** — your token is stored in the database against your account
5. Type: *"Book a 1-hour team sync sometime this week"*
6. The AI collects preferences, shows available slots, and asks you to confirm before booking
7. Verify the event in your Google Calendar or Outlook

**Testing token expiry / reconnect prompt:**  
Disconnect a calendar from the sidebar, then send a scheduling message. The AI will report the connection expired and the sidebar shows an amber **Reconnect now** banner for that provider.

### API docs (interactive Swagger UI)

`http://localhost:8000/docs`

---

## Example Usage

```
# First visit — create an account
[AuthScreen] Email: you@example.com  Password: ••••••••   [Create account]

# Chat
You:   I need to schedule a team standup
AI:    Happy to help! How long should the standup be?
       (15 min / 30 min / 1 hour, or tell me a custom duration)
You:   30 minutes
AI:    What dates work — tomorrow, later this week, or a specific day?
You:   Sometime this week
AI:    Here are the available slots on your Google Calendar:
         1. Tuesday, Jan 14  ·  9:00 – 9:30 AM GMT
         2. Tuesday, Jan 14  ·  2:00 – 2:30 PM GMT
         3. Wednesday, Jan 15 · 10:00 – 10:30 AM GMT
         4. Wednesday, Jan 15 ·  3:00 – 3:30 PM GMT
       Which would you like?
You:   Option 3
AI:    Just to confirm — I'll book **Team Standup** on Wednesday, Jan 15
       at 10:00 – 10:30 AM GMT on your Google Calendar. Shall I go ahead?
You:   Yes
AI:    Done! Your meeting is booked.
       View it here: https://calendar.google.com/event?id=...

# Next visit (different browser / device)
[AuthScreen] Sign in with the same email — calendar tokens and history are restored automatically
```

---

## API Reference

All routes except `/health`, `/api/auth/register`, `/api/auth/login`, and `/api/calendar/auth/*/callback` require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/auth/register` | `{email, password}` | Create account → returns JWT |
| `POST` | `/api/auth/login` | `{email, password}` | Sign in → returns JWT |
| `GET`  | `/api/auth/me` | — | Return current user info |

### Chat

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/chat/message` | `{session_id, message, timezone}` | Send a message; receive AI reply + `needs_reconnect_providers` |
| `GET`  | `/api/chat/status` | `?session_id=` | List connected calendar providers |

### Calendar OAuth

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| `GET`  | `/api/calendar/auth/{provider}` | `?session_id=&token=` | Start OAuth (browser redirect) |
| `GET`  | `/api/calendar/auth/{provider}/callback` | `?code=&state=` | OAuth callback — exchange code, store tokens |
| `DELETE` | `/api/calendar/disconnect/{provider}` | `?session_id=` | Remove stored tokens for this user |
| `GET`  | `/api/calendar/providers` | — | List supported providers |

### Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `GET`  | `/docs` | Interactive Swagger UI |

---

## Design Decisions

### JWT auth + SQLite persistence
User accounts are stored in SQLite with bcrypt-hashed passwords. On login, a 30-day JWT is issued and stored client-side. Calendar OAuth tokens are stored **per user** (not per session), so they survive server restarts and work across multiple devices. Conversation history is stored per session. Both are queryable via SQLAlchemy — swap `DATABASE_URL` in `.env` to move to PostgreSQL with no code changes.

### Repository pattern for sessions
`AbstractSessionStore` defines the interface. `DBSessionStore` (SQLite) is used in production; `SessionStore` (in-memory) is used in tests via FastAPI's `dependency_overrides`. Adding Redis is one new concrete class.

### Claude with tool-use
Rather than a rigid state machine, Claude drives the conversation naturally and decides *when* to check availability or book. The user can change their mind, add constraints, or ask follow-up questions without breaking a fixed flow. `CalendarAuthError` raised during a tool call is caught separately and surfaced back to the frontend as `needs_reconnect_providers` in the API response.

### Retry with exponential backoff
`with_retry(max_attempts=3, backoff_base=1.0)` in `utils/retry.py` wraps `get_busy_times` and `create_event` on both calendar providers. It retries only on transient status codes (429, 500–504) and network errors — permanent errors (401, 403) raise immediately.

### Strategy + Template Method for calendars
Adding a third provider (e.g. Apple Calendar) means implementing one class with three methods (`get_busy_times`, `create_event`, `get_auth_url`) and adding one entry to `CalendarProviderFactory._REGISTRY`. Zero changes to the AI layer, scheduler, or routes.

### OAuth security
- The `state` parameter in the OAuth flow carries the `session_id` to prevent CSRF
- For the browser-redirect OAuth start endpoint, the JWT is passed as a URL query param (no other way to include a header on a browser navigation); the callback is unauthenticated but resolves the user via the stored `session_id → user_id` mapping in the DB
- Calendar tokens are stored server-side only; the browser never sees them

### Virtual environment via Makefile
The Makefile owns the `.venv` lifecycle. A stamp file (`$(VENV)/.installed`) means `make run` and `make test` only reinstall packages when `requirements.txt` changes, keeping day-to-day iteration fast.

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| SQLite is single-writer | Suitable for a demo; swap `DATABASE_URL` to PostgreSQL for concurrent production use |
| Free/busy from primary calendar only | Extend `get_busy_times` to merge multiple calendar IDs |
| No recurring events | Add a `recurrence` field to `CalendarEvent` and provider implementations |
| Working-hours DST edge cases | Slot times near DST transitions can shift by an hour; `zoneinfo` + `dateutil.rrule` would fix this fully |
| No rate limiting on the chat endpoint | Add `slowapi` middleware for production |
| JWT stored in `localStorage` | Move to `httpOnly` cookie for XSS protection in a production deployment |
