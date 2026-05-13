-- AI Data Extraction Chatbot — Multi-tenant schema
-- Run once to initialise; seed.py handles data population.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── Tenancy ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS organizations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    slug       TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT    PRIMARY KEY,          -- UUID
    org_id        INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email         TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'member'
                  CHECK (role IN ('admin', 'member')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (org_id, email)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti        TEXT    PRIMARY KEY,             -- UUID, JWT ID claim
    user_id    TEXT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Chat sessions ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id   TEXT    PRIMARY KEY,
    user_id      TEXT    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id       INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    context_json TEXT    NOT NULL DEFAULT '{}', -- resolved entities cache
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    last_active  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS session_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    content_json TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Shared customer identity ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id     INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (org_id, email)
);

CREATE TABLE IF NOT EXISTS ecom_customer_profiles (
    customer_id INTEGER PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
    location    TEXT
);

CREATE TABLE IF NOT EXISTS support_customer_profiles (
    customer_id    INTEGER PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
    contact_info   TEXT,
    account_status TEXT NOT NULL DEFAULT 'active'
);

-- ── Ecommerce domain ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ecom_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id      INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS ecom_products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id      INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    description TEXT,
    price       REAL    NOT NULL,
    category_id INTEGER REFERENCES ecom_categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ecom_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id       INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    order_date   TEXT    NOT NULL,              -- YYYY-MM-DD
    total_amount REAL    NOT NULL
);

-- ── Support domain ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS support_agents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id     INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    department TEXT,
    expertise  TEXT
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id      INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    description TEXT,
    status      TEXT    NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'closed')),
    priority    TEXT    NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS support_interactions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    agent_id  INTEGER REFERENCES support_agents(id) ON DELETE SET NULL,
    timestamp TEXT    NOT NULL,
    notes     TEXT
);

-- ── Indexes ────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_users_org              ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user          ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session       ON session_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_customers_org_email    ON customers(org_id, email);
CREATE INDEX IF NOT EXISTS idx_customers_org_name     ON customers(org_id, name);
CREATE INDEX IF NOT EXISTS idx_orders_org_customer    ON ecom_orders(org_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_org_date        ON ecom_orders(org_id, order_date);
CREATE INDEX IF NOT EXISTS idx_products_org           ON ecom_products(org_id);
CREATE INDEX IF NOT EXISTS idx_tickets_org_customer   ON support_tickets(org_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_org_status     ON support_tickets(org_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_org_priority   ON support_tickets(org_id, priority);
CREATE INDEX IF NOT EXISTS idx_interactions_ticket    ON support_interactions(ticket_id);
