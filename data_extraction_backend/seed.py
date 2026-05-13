"""Multi-tenant CSV seed script.

Usage (CLI):
    python seed.py \\
        --org-name   "MNGR Demo" \\
        --data-dir   ../data_extraction_task/ai_data_extraction_chatbot_technical_task_sample_data \\
        --admin-email    admin@mngr.com \\
        --admin-password changeme123

Usage (programmatic — called from /api/seed route):
    from seed import run_seed
    result = run_seed(data_dir=..., org_name=..., admin_email=..., admin_password=...,
                      db_session_factory=SessionLocal)

Expected CSV layout under --data-dir:
    ecommerce/ecom_customers.csv    (id, name, email, location)
    ecommerce/ecom_orders.csv       (id, customer_id, order_date, total_amount)
    ecommerce/ecom_products.csv     (id, name, description, price, category_id)
    ecommerce/ecom_categories.csv   (id, name, description)
    support/support_customers.csv   (id, name, email, contact_info, account_status)
    support/support_tickets.csv     (id, title, description, customer_id, status, priority)
    support/support_agents.csv      (id, name, department, expertise)
    support/support_interactions.csv (id, ticket_id, agent_id, timestamp, notes)
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower().strip()).strip("-") or "org"


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_seed(
    data_dir: str,
    org_name: str,
    admin_email: str,
    admin_password: str,
    db_session_factory=None,
) -> dict[str, Any]:
    """Core seeding logic — returns summary dict."""
    from app.core.database import SessionLocal, init_db
    from app.core.security import hash_password
    from app.models.db import (
        Customer, EcomCategory, EcomCustomerProfile, EcomOrder, EcomProduct,
        Organization, SupportAgent, SupportCustomerProfile, SupportInteraction,
        SupportTicket, User,
    )
    from sqlalchemy import select
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    init_db()
    factory = db_session_factory or SessionLocal
    base = Path(data_dir)

    # ── Load CSVs ──────────────────────────────────────────────────────────────
    ecom_customers   = _load_csv(base / "ecommerce" / "ecom_customers.csv")
    ecom_orders      = _load_csv(base / "ecommerce" / "ecom_orders.csv")
    ecom_products    = _load_csv(base / "ecommerce" / "ecom_products.csv")
    ecom_categories  = _load_csv(base / "ecommerce" / "ecom_categories.csv")
    supp_customers   = _load_csv(base / "support"   / "support_customers.csv")
    supp_tickets     = _load_csv(base / "support"   / "support_tickets.csv")
    supp_agents      = _load_csv(base / "support"   / "support_agents.csv")
    supp_interactions = _load_csv(base / "support"  / "support_interactions.csv")

    with factory() as db:
        # ── Organisation ──────────────────────────────────────────────────────
        slug = _slugify(org_name)
        org = db.scalar(select(Organization).where(Organization.slug == slug))
        if not org:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            db.flush()
            logger.info("Created org '%s' (id=%d)", org_name, org.id)
        else:
            logger.info("Reusing existing org '%s' (id=%d)", org_name, org.id)

        org_id = org.id

        # ── Admin user ────────────────────────────────────────────────────────
        email_lower = admin_email.lower().strip()
        admin = db.scalar(
            select(User).where(User.org_id == org_id, User.email == email_lower)
        )
        if not admin:
            admin = User(
                id=str(uuid.uuid4()),
                org_id=org_id,
                email=email_lower,
                password_hash=hash_password(admin_password),
                role="admin",
            )
            db.add(admin)
            logger.info("Created admin user %s", email_lower)

        # ── Merge customers by email (Option C) ───────────────────────────────
        # Build unified email set from both domains
        ecom_by_csv_id: dict[str, dict] = {r["id"]: r for r in ecom_customers}
        supp_by_csv_id: dict[str, dict] = {r["id"]: r for r in supp_customers}

        # email → canonical DB customer_id
        email_to_canonical: dict[str, int] = {}

        all_emails: dict[str, dict] = {}
        for r in ecom_customers:
            all_emails[r["email"].lower()] = {"name": r["name"], "email": r["email"].lower()}
        for r in supp_customers:
            all_emails[r["email"].lower()] = {"name": r["name"], "email": r["email"].lower()}

        for email, info in all_emails.items():
            existing = db.scalar(
                select(Customer).where(Customer.org_id == org_id, Customer.email == email)
            )
            if existing:
                email_to_canonical[email] = existing.id
            else:
                c = Customer(org_id=org_id, name=info["name"], email=email)
                db.add(c)
                db.flush()
                email_to_canonical[email] = c.id
                logger.debug("Customer %s → id=%d", email, c.id)

        # ── Ecom customer profiles ────────────────────────────────────────────
        for r in ecom_customers:
            cid = email_to_canonical[r["email"].lower()]
            if not db.get(EcomCustomerProfile, cid):
                db.add(EcomCustomerProfile(customer_id=cid, location=r.get("location", "")))

        # ── Support customer profiles ─────────────────────────────────────────
        for r in supp_customers:
            cid = email_to_canonical[r["email"].lower()]
            if not db.get(SupportCustomerProfile, cid):
                db.add(SupportCustomerProfile(
                    customer_id=cid,
                    contact_info=r.get("contact_info", ""),
                    account_status=r.get("account_status", "active"),
                ))

        # ── Ecom categories ───────────────────────────────────────────────────
        # Map CSV category id → DB category id
        cat_csv_to_db: dict[str, int] = {}
        for r in ecom_categories:
            existing = db.scalar(
                select(EcomCategory).where(
                    EcomCategory.org_id == org_id,
                    EcomCategory.name   == r["name"],
                )
            )
            if existing:
                cat_csv_to_db[r["id"]] = existing.id
            else:
                cat = EcomCategory(
                    org_id=org_id,
                    name=r["name"],
                    description=r.get("description", ""),
                )
                db.add(cat)
                db.flush()
                cat_csv_to_db[r["id"]] = cat.id

        # ── Ecom products ─────────────────────────────────────────────────────
        prod_csv_to_db: dict[str, int] = {}
        for r in ecom_products:
            cat_db_id = cat_csv_to_db.get(r.get("category_id", ""))
            existing = db.scalar(
                select(EcomProduct).where(
                    EcomProduct.org_id == org_id,
                    EcomProduct.name   == r["name"],
                )
            )
            if existing:
                prod_csv_to_db[r["id"]] = existing.id
            else:
                p = EcomProduct(
                    org_id=org_id,
                    name=r["name"],
                    description=r.get("description", ""),
                    price=float(r.get("price", 0)),
                    category_id=cat_db_id,
                )
                db.add(p)
                db.flush()
                prod_csv_to_db[r["id"]] = p.id

        # ── Ecom orders ───────────────────────────────────────────────────────
        orders_created = 0
        for r in ecom_orders:
            ecom_cust = ecom_by_csv_id.get(r["customer_id"])
            if not ecom_cust:
                continue
            cid = email_to_canonical.get(ecom_cust["email"].lower())
            if not cid:
                continue
            existing = db.scalar(
                select(EcomOrder).where(
                    EcomOrder.org_id      == org_id,
                    EcomOrder.customer_id == cid,
                    EcomOrder.order_date  == r["order_date"],
                    EcomOrder.total_amount == float(r["total_amount"]),
                )
            )
            if not existing:
                db.add(EcomOrder(
                    org_id=org_id,
                    customer_id=cid,
                    order_date=r["order_date"],
                    total_amount=float(r["total_amount"]),
                ))
                orders_created += 1

        # ── Support agents ────────────────────────────────────────────────────
        agent_csv_to_db: dict[str, int] = {}
        for r in supp_agents:
            existing = db.scalar(
                select(SupportAgent).where(
                    SupportAgent.org_id == org_id,
                    SupportAgent.name   == r["name"],
                )
            )
            if existing:
                agent_csv_to_db[r["id"]] = existing.id
            else:
                a = SupportAgent(
                    org_id=org_id,
                    name=r["name"],
                    department=r.get("department", ""),
                    expertise=r.get("expertise", ""),
                )
                db.add(a)
                db.flush()
                agent_csv_to_db[r["id"]] = a.id

        # ── Support tickets ───────────────────────────────────────────────────
        ticket_csv_to_db: dict[str, int] = {}
        tickets_created = 0
        for r in supp_tickets:
            supp_cust = supp_by_csv_id.get(r["customer_id"])
            if not supp_cust:
                continue
            cid = email_to_canonical.get(supp_cust["email"].lower())
            if not cid:
                continue
            existing = db.scalar(
                select(SupportTicket).where(
                    SupportTicket.org_id      == org_id,
                    SupportTicket.customer_id == cid,
                    SupportTicket.title       == r["title"],
                )
            )
            if existing:
                ticket_csv_to_db[r["id"]] = existing.id
            else:
                t = SupportTicket(
                    org_id=org_id,
                    customer_id=cid,
                    title=r["title"],
                    description=r.get("description", ""),
                    status=r.get("status", "open"),
                    priority=r.get("priority", "medium"),
                )
                db.add(t)
                db.flush()
                ticket_csv_to_db[r["id"]] = t.id
                tickets_created += 1

        # ── Support interactions ──────────────────────────────────────────────
        for r in supp_interactions:
            ticket_db_id = ticket_csv_to_db.get(r["ticket_id"])
            if not ticket_db_id:
                continue
            agent_db_id = agent_csv_to_db.get(r.get("agent_id", ""))
            existing = db.scalar(
                select(SupportInteraction).where(
                    SupportInteraction.ticket_id == ticket_db_id,
                    SupportInteraction.timestamp == r["timestamp"],
                )
            )
            if not existing:
                db.add(SupportInteraction(
                    ticket_id=ticket_db_id,
                    agent_id=agent_db_id,
                    timestamp=r["timestamp"],
                    notes=r.get("notes", ""),
                ))

        db.commit()
        logger.info(
            "Seed complete — org_id=%d, customers=%d, orders=%d, tickets=%d",
            org_id, len(all_emails), orders_created, tickets_created,
        )

        return {
            "org_id":            org_id,
            "org_name":          org_name,
            "customers_created": len(all_emails),
            "orders_created":    orders_created,
            "tickets_created":   tickets_created,
            "message":           f"Seeded {len(all_emails)} customers, {orders_created} orders, {tickets_created} tickets.",
        }


# ── Demo org 2: Acme Retail (hardcoded, no CSVs needed) ───────────────────────
#
# Intentionally designed to test corner cases:
#   - Two customers named "Alice" (different emails) → disambiguation flow
#   - James Wilson: ecommerce-only (no support tickets)
#   - Rachel Kim:   support-only   (no orders)
#   - Mixed ticket statuses, priorities, and agents across departments

_ACME_DATA: dict = {
    "categories": [
        {"id": "1", "name": "Furniture",    "description": "Desks, chairs, shelving"},
        {"id": "2", "name": "Stationery",   "description": "Pens, notebooks, paper"},
        {"id": "3", "name": "Electronics",  "description": "Monitors, keyboards, cables"},
        {"id": "4", "name": "Breakroom",    "description": "Coffee, snacks, appliances"},
    ],
    "products": [
        {"id": "1", "name": "Standing Desk",        "description": "Height-adjustable, 140 cm", "price": "549.00",  "category_id": "1"},
        {"id": "2", "name": "Ergonomic Chair",       "description": "Lumbar support, armrests",  "price": "299.00",  "category_id": "1"},
        {"id": "3", "name": "Wireless Keyboard",     "description": "Compact TKL layout",         "price": "89.99",   "category_id": "3"},
        {"id": "4", "name": "27\" Monitor",          "description": "4K IPS, USB-C",              "price": "449.00",  "category_id": "3"},
        {"id": "5", "name": "Notebook Pack (x5)",    "description": "A5, lined",                  "price": "14.99",   "category_id": "2"},
        {"id": "6", "name": "Coffee Machine",        "description": "Bean-to-cup, 12-cup",        "price": "199.00",  "category_id": "4"},
    ],
    # Ecommerce customers — note two customers named "Alice" for disambiguation testing
    "ecom_customers": [
        {"id": "1", "name": "Alice Thompson",  "email": "alice.thompson@acme-corp.com",  "location": "New York, US"},
        {"id": "2", "name": "Alice Nguyen",    "email": "alice.nguyen@acme-corp.com",    "location": "San Francisco, US"},
        {"id": "3", "name": "James Wilson",    "email": "james.wilson@acme-corp.com",    "location": "Chicago, US"},
        {"id": "4", "name": "Maria Santos",    "email": "maria.santos@acme-corp.com",    "location": "Miami, US"},
        {"id": "5", "name": "David Park",      "email": "david.park@acme-corp.com",      "location": "Seattle, US"},
        {"id": "6", "name": "Sophie Laurent",  "email": "sophie.laurent@acme-corp.com",  "location": "Austin, US"},
    ],
    "ecom_orders": [
        # Alice Thompson — multiple orders, good for date-range tests
        {"id": "1",  "customer_id": "1", "order_date": "2026-05-10", "total_amount": "549.00"},
        {"id": "2",  "customer_id": "1", "order_date": "2026-04-22", "total_amount": "89.99"},
        {"id": "3",  "customer_id": "1", "order_date": "2026-03-15", "total_amount": "14.99"},
        # Alice Nguyen — fewer orders
        {"id": "4",  "customer_id": "2", "order_date": "2026-05-01", "total_amount": "449.00"},
        {"id": "5",  "customer_id": "2", "order_date": "2026-04-10", "total_amount": "299.00"},
        # James Wilson — ecommerce only (no support tickets)
        {"id": "6",  "customer_id": "3", "order_date": "2026-05-08", "total_amount": "199.00"},
        {"id": "7",  "customer_id": "3", "order_date": "2026-04-30", "total_amount": "89.99"},
        # Maria Santos
        {"id": "8",  "customer_id": "4", "order_date": "2026-05-05", "total_amount": "449.00"},
        # David Park — large single order
        {"id": "9",  "customer_id": "5", "order_date": "2026-04-18", "total_amount": "998.00"},
        # Sophie Laurent — no tickets
        {"id": "10", "customer_id": "6", "order_date": "2026-05-11", "total_amount": "14.99"},
    ],
    # Support customers — Rachel Kim is support-only (no orders)
    "support_customers": [
        {"id": "1", "name": "Alice Thompson", "email": "alice.thompson@acme-corp.com", "contact_info": "+1 212 555 0101", "account_status": "active"},
        {"id": "2", "name": "Alice Nguyen",   "email": "alice.nguyen@acme-corp.com",   "contact_info": "+1 415 555 0102", "account_status": "active"},
        {"id": "3", "name": "Maria Santos",   "email": "maria.santos@acme-corp.com",   "contact_info": "+1 305 555 0103", "account_status": "active"},
        {"id": "4", "name": "David Park",     "email": "david.park@acme-corp.com",     "contact_info": "+1 206 555 0104", "account_status": "suspended"},
        {"id": "5", "name": "Rachel Kim",     "email": "rachel.kim@acme-corp.com",     "contact_info": "+1 617 555 0105", "account_status": "active"},
    ],
    "support_agents": [
        {"id": "1", "name": "Connor Walsh",    "department": "Technical",  "expertise": "Hardware, setup, connectivity"},
        {"id": "2", "name": "Amara Diallo",    "department": "Billing",    "expertise": "Invoices, refunds, payment plans"},
        {"id": "3", "name": "Yuki Tanaka",     "department": "Logistics",  "expertise": "Shipping, returns, lost orders"},
        {"id": "4", "name": "Priya Mehta",     "department": "Technical",  "expertise": "Software, account access, integrations"},
    ],
    "support_tickets": [
        # Alice Thompson — two tickets (one closed, one open)
        {"id": "1",  "customer_id": "1", "title": "Standing desk won't adjust height",       "description": "Motor makes noise but doesn't move",         "status": "open",        "priority": "high"},
        {"id": "2",  "customer_id": "1", "title": "Missing items in March order",             "description": "Notebook pack was not included",             "status": "closed",      "priority": "low"},
        # Alice Nguyen — one in-progress ticket
        {"id": "3",  "customer_id": "2", "title": "Monitor flickering at 4K resolution",      "description": "Happens every 10-15 minutes randomly",       "status": "in_progress", "priority": "high"},
        # Maria Santos — two open high-priority tickets
        {"id": "4",  "customer_id": "4", "title": "Incorrect invoice amount",                 "description": "Charged £449 twice for the same order",      "status": "open",        "priority": "high"},
        {"id": "5",  "customer_id": "4", "title": "Order 8 not delivered after 2 weeks",      "description": "Tracking stopped updating after dispatch",    "status": "open",        "priority": "high"},
        # David Park — account suspended, open ticket
        {"id": "6",  "customer_id": "4", "title": "Account suspended without notice",         "description": "Cannot log in, no email received",           "status": "open",        "priority": "high"},
        # Rachel Kim — support-only (no orders), one low-priority ticket
        {"id": "7",  "customer_id": "5", "title": "How do I add a second user to my account?","description": "Need to share access with a colleague",       "status": "open",        "priority": "low"},
    ],
    "support_interactions": [
        {"id": "1",  "ticket_id": "1", "agent_id": "1", "timestamp": "2026-05-11 09:00:00", "notes": "Requested video of the issue"},
        {"id": "2",  "ticket_id": "1", "agent_id": "1", "timestamp": "2026-05-12 14:30:00", "notes": "Video received, escalated to manufacturer"},
        {"id": "3",  "ticket_id": "2", "agent_id": "3", "timestamp": "2026-04-20 10:00:00", "notes": "Confirmed missing item, reshipped"},
        {"id": "4",  "ticket_id": "2", "agent_id": "3", "timestamp": "2026-04-28 11:00:00", "notes": "Customer confirmed receipt, closed"},
        {"id": "5",  "ticket_id": "3", "agent_id": "1", "timestamp": "2026-05-02 09:15:00", "notes": "Sent updated firmware, awaiting test"},
        {"id": "6",  "ticket_id": "3", "agent_id": "4", "timestamp": "2026-05-06 16:00:00", "notes": "Firmware applied, issue persists — hardware swap arranged"},
        {"id": "7",  "ticket_id": "4", "agent_id": "2", "timestamp": "2026-05-06 10:00:00", "notes": "Confirmed duplicate charge, refund initiated"},
        {"id": "8",  "ticket_id": "5", "agent_id": "3", "timestamp": "2026-05-07 08:00:00", "notes": "Contacted courier, investigating"},
        {"id": "9",  "ticket_id": "6", "agent_id": "4", "timestamp": "2026-05-09 13:00:00", "notes": "Reviewing account flags, awaiting security clearance"},
        {"id": "10", "ticket_id": "7", "agent_id": "4", "timestamp": "2026-05-10 15:00:00", "notes": "Sent instructions for multi-user setup"},
    ],
}


def seed_demo_org2(
    org_name: str = "Acme Retail",
    admin_email: str = "admin@acme-retail.com",
    admin_password: str = "acme123456",
    db_session_factory=None,
) -> dict:
    """Seed Acme Retail demo org from hardcoded data — no CSV files needed.

    Designed to exercise corner cases:
      - Two customers named 'Alice' → name disambiguation
      - James Wilson: ecommerce-only (no support tickets)
      - Rachel Kim:   support-only   (no orders)
      - David Park:   suspended account with open ticket
    """
    from app.core.database import SessionLocal, init_db
    from app.core.security import hash_password
    from app.models.db import (
        Customer, EcomCategory, EcomCustomerProfile, EcomOrder, EcomProduct,
        Organization, SupportAgent, SupportCustomerProfile, SupportInteraction,
        SupportTicket, User,
    )
    from sqlalchemy import select

    init_db()
    factory = db_session_factory or SessionLocal
    d = _ACME_DATA

    with factory() as db:
        slug = _slugify(org_name)
        org = db.scalar(select(Organization).where(Organization.slug == slug))
        if not org:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            db.flush()
            logger.info("Created org '%s' (id=%d)", org_name, org.id)
        else:
            logger.info("Reusing existing org '%s' (id=%d)", org_name, org.id)
        org_id = org.id

        # Admin user
        email_lower = admin_email.lower().strip()
        if not db.scalar(select(User).where(User.org_id == org_id, User.email == email_lower)):
            db.add(User(
                id=str(uuid.uuid4()),
                org_id=org_id,
                email=email_lower,
                password_hash=hash_password(admin_password),
                role="admin",
            ))

        # Merge customers by email
        ecom_by_id  = {r["id"]: r for r in d["ecom_customers"]}
        supp_by_id  = {r["id"]: r for r in d["support_customers"]}
        email_to_cid: dict[str, int] = {}

        all_emails: dict[str, dict] = {}
        for r in d["ecom_customers"] + d["support_customers"]:
            all_emails[r["email"].lower()] = {"name": r["name"], "email": r["email"].lower()}

        for email, info in all_emails.items():
            existing = db.scalar(select(Customer).where(Customer.org_id == org_id, Customer.email == email))
            if existing:
                email_to_cid[email] = existing.id
            else:
                c = Customer(org_id=org_id, name=info["name"], email=email)
                db.add(c)
                db.flush()
                email_to_cid[email] = c.id

        for r in d["ecom_customers"]:
            cid = email_to_cid[r["email"].lower()]
            if not db.get(EcomCustomerProfile, cid):
                db.add(EcomCustomerProfile(customer_id=cid, location=r.get("location", "")))

        for r in d["support_customers"]:
            cid = email_to_cid[r["email"].lower()]
            if not db.get(SupportCustomerProfile, cid):
                db.add(SupportCustomerProfile(
                    customer_id=cid,
                    contact_info=r.get("contact_info", ""),
                    account_status=r.get("account_status", "active"),
                ))

        # Categories
        cat_map: dict[str, int] = {}
        for r in d["categories"]:
            ex = db.scalar(select(EcomCategory).where(EcomCategory.org_id == org_id, EcomCategory.name == r["name"]))
            if ex:
                cat_map[r["id"]] = ex.id
            else:
                c = EcomCategory(org_id=org_id, name=r["name"], description=r.get("description", ""))
                db.add(c)
                db.flush()
                cat_map[r["id"]] = c.id

        # Products
        for r in d["products"]:
            if not db.scalar(select(EcomProduct).where(EcomProduct.org_id == org_id, EcomProduct.name == r["name"])):
                db.add(EcomProduct(
                    org_id=org_id, name=r["name"], description=r.get("description", ""),
                    price=float(r["price"]), category_id=cat_map.get(r.get("category_id", "")),
                ))

        # Orders
        orders_created = 0
        for r in d["ecom_orders"]:
            ec = ecom_by_id.get(r["customer_id"])
            if not ec:
                continue
            cid = email_to_cid.get(ec["email"].lower())
            if not cid:
                continue
            if not db.scalar(select(EcomOrder).where(
                EcomOrder.org_id == org_id, EcomOrder.customer_id == cid,
                EcomOrder.order_date == r["order_date"], EcomOrder.total_amount == float(r["total_amount"])
            )):
                db.add(EcomOrder(org_id=org_id, customer_id=cid, order_date=r["order_date"], total_amount=float(r["total_amount"])))
                orders_created += 1

        # Support agents
        agent_map: dict[str, int] = {}
        for r in d["support_agents"]:
            ex = db.scalar(select(SupportAgent).where(SupportAgent.org_id == org_id, SupportAgent.name == r["name"]))
            if ex:
                agent_map[r["id"]] = ex.id
            else:
                a = SupportAgent(org_id=org_id, name=r["name"], department=r.get("department", ""), expertise=r.get("expertise", ""))
                db.add(a)
                db.flush()
                agent_map[r["id"]] = a.id

        # Tickets
        ticket_map: dict[str, int] = {}
        tickets_created = 0
        for r in d["support_tickets"]:
            sc = supp_by_id.get(r["customer_id"])
            if not sc:
                continue
            cid = email_to_cid.get(sc["email"].lower())
            if not cid:
                continue
            ex = db.scalar(select(SupportTicket).where(
                SupportTicket.org_id == org_id, SupportTicket.customer_id == cid, SupportTicket.title == r["title"]
            ))
            if ex:
                ticket_map[r["id"]] = ex.id
            else:
                t = SupportTicket(
                    org_id=org_id, customer_id=cid, title=r["title"],
                    description=r.get("description", ""), status=r.get("status", "open"), priority=r.get("priority", "medium"),
                )
                db.add(t)
                db.flush()
                ticket_map[r["id"]] = t.id
                tickets_created += 1

        # Interactions
        for r in d["support_interactions"]:
            tid = ticket_map.get(r["ticket_id"])
            if not tid:
                continue
            aid = agent_map.get(r.get("agent_id", ""))
            if not db.scalar(select(SupportInteraction).where(
                SupportInteraction.ticket_id == tid, SupportInteraction.timestamp == r["timestamp"]
            )):
                db.add(SupportInteraction(ticket_id=tid, agent_id=aid, timestamp=r["timestamp"], notes=r.get("notes", "")))

        db.commit()
        logger.info("Acme Retail seed complete — org_id=%d, customers=%d, orders=%d, tickets=%d",
                    org_id, len(all_emails), orders_created, tickets_created)

        return {
            "org_id":            org_id,
            "org_name":          org_name,
            "customers_created": len(all_emails),
            "orders_created":    orders_created,
            "tickets_created":   tickets_created,
            "message":           f"Seeded {len(all_emails)} customers, {orders_created} orders, {tickets_created} tickets.",
        }


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./extraction.db")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Seed the extraction database from CSVs.")
    parser.add_argument("--org-name",       required=True)
    parser.add_argument("--data-dir",       required=True)
    parser.add_argument("--admin-email",    required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--seed-demo-org2", action="store_true",
                        help="Also seed the Acme Retail demo org (no CSVs needed)")
    args = parser.parse_args()

    result = run_seed(
        data_dir=args.data_dir,
        org_name=args.org_name,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
    )
    print(result["message"])
    print(f"Org ID: {result['org_id']}")

    if args.seed_demo_org2:
        r2 = seed_demo_org2()
        print(r2["message"])
        print(f"Org ID: {r2['org_id']}")
