# AI Calendar Scheduling Chatbot

A production-grade, conversational AI assistant that schedules appointments on **Google Calendar** and **Microsoft Outlook** via natural language. Built with **Python (FastAPI)** on the backend and **Next.js** on the frontend, powered by **Claude** (Anthropic) with tool-use.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Setup & Installation](#setup--installation)
4. [Running the Application](#running-the-application)
5. [Testing the Solution](#testing-the-solution)
6. [Example Usage](#example-usage)
7. [API Reference](#api-reference)
8. [Design Decisions](#design-decisions)
9. [Known Limitations](#known-limitations)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend (port 3000)              │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │   ChatInterface      │  │        CalendarConnect           │  │
│  │   (useChat hook)     │  │   (Google / Outlook OAuth)       │  │
│  └──────────┬──────────┘  └──────────────────────────────────┘  │
└─────────────┼────────────────────────────────────────────────────┘
              │ HTTP/REST
┌─────────────▼────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                    │
│                                                                   │
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │  /api/chat   │    │         /api/calendar/auth           │   │
│  │  (chat.py)   │    │     (Google + Outlook OAuth flow)    │   │
│  └──────┬───────┘    └──────────────────────────────────────┘   │
│         │                                                         │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │               ClaudeAIService                            │    │
│  │  • Maintains conversation history per session            │    │
│  │  • Drives tool-use loop (get_slots → confirm → create)  │    │
│  └──────┬──────────────────────────────────────────────────┘    │
│         │                                                         │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │            SchedulingService (tool dispatcher)           │    │
│  └──────┬──────────────────────────────────────────────────┘    │
│         │                                                         │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │        CalendarProvider (Strategy + Template Method)     │    │
│  │  ┌─────────────────────┐  ┌──────────────────────────┐  │    │
│  │  │ GoogleCalendarProvider│  │OutlookCalendarProvider   │  │    │
│  │  │  (google-api-python) │  │  (Microsoft Graph API)   │  │    │
│  │  └─────────────────────┘  └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SessionStore (Singleton) — in-memory per-session state  │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Strategy** | `CalendarProvider` base + Google/Outlook impls | Swap calendar backends without touching callers |
| **Factory Method** | `CalendarProviderFactory` | Create the right provider from a string name |
| **Template Method** | `CalendarProvider.find_available_slots()` | Algorithm skeleton — busy-time fetch is overridden, slot-filter logic is shared |
| **Singleton** | `SessionStore` | Single source of truth for session state |
| **Command (dispatch table)** | `ClaudeAIService._dispatch()` | Route Claude tool calls to handlers without if-elif chains |
| **Dependency Injection** | FastAPI `Depends()` | Loose coupling between routes and services |

---

## Prerequisites

### Backend
- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
- **Google Calendar** credentials (see below) — optional if testing Outlook only
- **Outlook / Azure** app registration (see below) — optional if testing Google only

### Frontend
- Node.js 18+
- npm / yarn / pnpm

---

## Setup & Installation

### 1. Clone / enter the project

```bash
cd "chatbot Task"
```

### 2. Backend

```bash
cd backend

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
```

Edit `backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...

# Google (skip if not testing Google Calendar)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Outlook (skip if not testing Outlook)
OUTLOOK_CLIENT_ID=...
OUTLOOK_CLIENT_SECRET=...
OUTLOOK_TENANT_ID=common
```

#### Google Calendar Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services** → **Enable APIs** → enable **Google Calendar API**
3. **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID** (Web application)
4. Add authorised redirect URI: `http://localhost:8000/api/calendar/auth/google/callback`
5. Copy **Client ID** and **Client secret** into `.env`
6. On first run you'll be asked to verify the app in Google's OAuth consent screen; add your test email as a test user.

#### Outlook (Microsoft Graph) Setup

1. Go to [Azure Portal](https://portal.azure.com/) → **Azure Active Directory** → **App registrations** → **New registration**
2. Name: anything; Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
3. Redirect URI (Web): `http://localhost:8000/api/calendar/auth/outlook/callback`
4. **API permissions** → **Microsoft Graph** → **Delegated** → add `Calendars.ReadWrite` and `offline_access`
5. **Certificates & secrets** → **New client secret** — copy the value
6. Copy **Application (client) ID** and secret into `.env`

### 3. Frontend

```bash
cd ../frontend

npm install          # or: yarn / pnpm install

cp .env.example .env.local
# .env.local already has: NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running the Application

Open **two terminals**:

**Terminal 1 — Backend**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Visit **http://localhost:3000** in your browser.

---

## Testing the Solution

### Unit & Integration Tests (backend)

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

All tests use mocked calendar APIs — **no real credentials required** to run the test suite.

### Manual End-to-End Test

1. Open http://localhost:3000
2. In the sidebar, click **Connect** next to **Google Calendar** (or Outlook)
3. Complete the OAuth consent flow in the browser
4. Return to the chat — the calendar now shows **Connected**
5. Type: *"Book a 1-hour team sync sometime this week"*
6. The AI will ask for preferences, show available slots, and confirm before booking
7. Verify the event appears in your Google Calendar / Outlook

### API Docs (interactive)

The backend exposes Swagger UI at **http://localhost:8000/docs**.

---

## Example Usage

```
You:   I need to schedule a team standup
AI:    How long should the standup be? (15 min, 30 min, or custom?)
You:   30 minutes
AI:    What dates work for you — tomorrow, or later this week?
You:   Sometime this week
AI:    Here are the available slots on your Google Calendar:
         1. Tuesday, Jan 14 · 9:00 AM – 9:30 AM GMT
         2. Tuesday, Jan 14 · 2:00 PM – 2:30 PM GMT
         3. Wednesday, Jan 15 · 10:00 AM – 10:30 AM GMT
         4. Wednesday, Jan 15 · 3:00 PM – 3:30 PM GMT
       Which slot would you like?
You:   Option 3 please
AI:    I'll book **Team Standup** on Wednesday, Jan 15 at 10:00–10:30 AM GMT.
       Shall I confirm?
You:   Yes
AI:    Done! Your meeting is booked. 🎉
       View it here: https://calendar.google.com/event?id=...
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat/message` | Send a chat message; receive AI reply |
| `GET`  | `/api/chat/status?session_id=` | List connected providers for a session |
| `GET`  | `/api/calendar/auth/{provider}?session_id=` | Begin OAuth flow (redirects to provider) |
| `GET`  | `/api/calendar/auth/{provider}/callback` | OAuth callback (handled by backend) |
| `DELETE` | `/api/calendar/disconnect/{provider}?session_id=` | Remove stored tokens |
| `GET`  | `/api/calendar/providers` | List supported calendar providers |
| `GET`  | `/health` | Health check |

---

## Design Decisions

### Why FastAPI + Next.js?
FastAPI provides async-native Python with automatic OpenAPI docs. Next.js gives us a React-based frontend with SSR capabilities. The two are decoupled via a REST API, so either can be replaced independently.

### Why Claude with Tool Use?
Rather than a rigid state machine, Claude drives the conversation naturally and decides *when* to check availability or book. This makes the dialogue far more flexible — the user can change their mind, add constraints, or ask follow-ups without breaking a fixed flow.

### Why an in-memory Session Store?
For a take-home task, in-memory is sufficient and avoids infrastructure dependencies. The `SessionStore` implements a repository interface so swapping to Redis requires only a new concrete class — no changes to callers.

### Why Strategy + Template Method for Calendars?
Adding a third provider (e.g. Apple Calendar) means implementing one class with three methods (`get_busy_times`, `create_event`, `get_auth_url`) and registering it in the factory. Zero changes to the AI layer, scheduler, or routes.

### OAuth Security
- OAuth `state` parameter = session ID, preventing CSRF on the callback.
- Tokens are stored server-side (in session), never sent to the browser.
- Token refresh is automatic (Google via `google-auth`, Outlook via MSAL).

---

## Known Limitations

| Limitation | Mitigation / Future Work |
|------------|--------------------------|
| In-memory sessions are lost on restart | Replace `SessionStore` with Redis |
| Single-user per session (no multi-tenancy auth) | Add JWT-based user auth layer |
| Free/busy only from primary calendar | Extend to list all user calendars and merge |
| No recurring events support | Add `recurrence` field to `CalendarEvent` model |
| Working hours not timezone-DST aware on edge cases | Use `zoneinfo` + `dateutil` for full DST handling |
| Frontend has no error retry UI | Add exponential-backoff retry in `useChat` hook |
| No rate limiting on chat endpoint | Add `slowapi` middleware |
