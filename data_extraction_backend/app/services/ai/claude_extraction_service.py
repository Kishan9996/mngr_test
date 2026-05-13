"""Claude AI service for natural-language data extraction.

Design patterns:
  Strategy    — implements AIService; swap LLM without touching callers.
  Dispatch    — tool calls routed through _dispatch(), loop stays clean.

Performance:
  Anthropic prompt cache  — static system prompt block marked cache_control.
  Session entity cache    — resolved customers injected as tiny dynamic addendum.
  Result truncation       — cap rows before sending back to Claude.
  History compression     — old tool_result blocks replaced with one-line summaries.

Security:
  org_id is NEVER in tool input schema — injected from auth session only.
  query_with_schema validates SQL before execution (no writes, :org_id required).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AIServiceError, AppError, DataServiceError
from app.services.ai.base import AIService
from app.services.cache.query_cache import QueryCache
from app.services.data.cross_domain_repository import CrossDomainRepository
from app.services.data.customer_repository import CustomerRepository
from app.services.data.ecommerce_repository import EcommerceRepository
from app.services.data.support_repository import SupportRepository
from app.services.session.abstract_store import AbstractSessionStore

logger = logging.getLogger(__name__)

_MAX_ROWS_TO_CLAUDE = 15
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|ATTACH)\b",
    re.IGNORECASE,
)

# ── DB schema description (static — Anthropic caches this) ────────────────────

_DB_SCHEMA = """
## Database Schema (read-only, your org_id is automatically applied)

### Shared Customer Identity
- customers(id, name, email) — canonical record; a customer may appear in one or both domains
- ecom_customer_profiles(customer_id→customers, location)
- support_customer_profiles(customer_id→customers, contact_info, account_status)

### Ecommerce Domain
- ecom_categories(id, name, description)
- ecom_products(id, name, description, price, category_id→ecom_categories)
- ecom_orders(id, customer_id→customers, order_date TEXT "YYYY-MM-DD", total_amount REAL)

### Support Domain
- support_agents(id, name, department, expertise)
- support_tickets(id, customer_id→customers, title, description,
    status ["open","in_progress","closed"], priority ["low","medium","high"], created_at)
- support_interactions(id, ticket_id→support_tickets, agent_id→support_agents, timestamp TEXT, notes)

## Tool Strategy
1. Call `lookup_customer` first to resolve a name/email → customer_id.
2. Use `query_ecommerce` or `query_support` for single-domain questions.
3. Use `query_cross_domain` for questions spanning both domains.
4. Use `query_with_schema` only when the typed tools cannot express the query.
   Always use the :org_id bind placeholder — never hardcode a number.
"""

# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "lookup_customer",
        "description": (
            "Resolve a customer by name or email to get their customer_id and which "
            "domains they exist in. Always call this first before querying orders or tickets. "
            "If the result contains more than one customer (count > 1), you MUST stop and "
            "present the list to the user — show each customer's name, email and id — then "
            "ask 'Which customer did you mean?' before making any further queries. "
            "Never proceed with an ambiguous customer_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":  {"type": "string", "description": "Full or partial customer name"},
                "email": {"type": "string", "description": "Exact customer email"},
            },
        },
    },
    {
        "name": "query_ecommerce",
        "description": (
            "Query orders in the ecommerce domain. "
            "Always use YYYY-MM-DD for date_from/date_to — never pass month names or relative strings. "
            "aggregate='total_spend' or 'order_count' requires a customer_id. "
            "aggregate='spend_per_customer' returns totals for all customers (no customer_id needed)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "From lookup_customer"},
                "date_from":   {"type": "string",  "description": "YYYY-MM-DD inclusive"},
                "date_to":     {"type": "string",  "description": "YYYY-MM-DD inclusive"},
                "aggregate": {
                    "type": "string",
                    "enum": ["total_spend", "order_count", "spend_per_customer"],
                    "description": (
                        "total_spend/order_count: requires customer_id. "
                        "spend_per_customer: all customers, no customer_id needed."
                    ),
                },
            },
        },
    },
    {
        "name": "query_support",
        "description": "Query support tickets, interactions and agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id":          {"type": "integer", "description": "From lookup_customer"},
                "status":               {"type": "string", "enum": ["open", "in_progress", "closed"]},
                "priority":             {"type": "string", "enum": ["low", "medium", "high"]},
                "include_interactions": {"type": "boolean"},
            },
        },
    },
    {
        "name": "query_cross_domain",
        "description": (
            "Queries spanning ecommerce AND support. Use for: "
            "'customers with both orders and tickets', "
            "'customers who shopped but never raised a ticket' (filter=ecommerce_only), "
            "'total spend for customers who have open tickets'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id":           {"type": "integer", "description": "Omit for all customers"},
                "filter": {
                    "type": "string",
                    "enum": ["has_both", "ecommerce_only", "support_only"],
                },
                "include_order_totals":  {"type": "boolean"},
                "include_ticket_counts": {"type": "boolean"},
            },
        },
    },
    {
        "name": "query_with_schema",
        "description": (
            "Fallback for queries the typed tools cannot express. "
            "Write one SELECT statement using :org_id as a bind placeholder. "
            "Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql":    {"type": "string", "description": "A single SELECT with :org_id"},
                "reason": {"type": "string", "description": "Why typed tools were insufficient"},
            },
            "required": ["sql", "reason"],
        },
    },
]


def _build_system_prompt(resolved_customers: dict[int, dict]) -> list[dict]:
    """Return a two-block system prompt.

    Block 0 (static):  schema + rules — Anthropic caches this across requests.
    Block 1 (dynamic): today's date + resolved entities — small, always fresh.
    """
    static_text = f"""You are a helpful data analyst assistant. \
Answer questions about ecommerce orders and customer support data conversationally.
Return clear, readable summaries — never raw JSON or SQL.

{_DB_SCHEMA}

## Rules
- Always call lookup_customer before querying orders or tickets by customer name.
- **Multiple matches**: if lookup_customer returns count > 1, STOP. List every match
  as "N. Name (email) — id=X" and ask "Which customer did you mean?" before any
  further tool calls. Never silently pick one.
- **Single match**: proceed directly — no need to confirm.
- **No match**: say so clearly and ask the user to check the name or provide an email.
- **Dates**: always convert relative references ("last month", "this week", "yesterday")
  to YYYY-MM-DD using today's date before calling any tool. Never pass month names
  or relative strings as date_from/date_to.
- **Domain gaps**: a customer may exist in only one domain. If orders are empty say
  "no orders on record" — don't imply the customer doesn't exist.
- When results are truncated, tell the user and suggest narrowing with filters.
- Format currency as £X.XX, dates as "DD Mon YYYY".
- Be concise. Use bullet points for lists of more than 3 items.
"""
    blocks: list[dict] = [
        {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
    ]

    from datetime import date
    dynamic_lines = [f"Today's date: {date.today().isoformat()}"]

    if resolved_customers:
        lines = "\n".join(
            f"  - \"{c.get('name','?')}\" → customer_id={cid} "
            f"(ecommerce={bool(c.get('in_ecommerce'))}, support={bool(c.get('in_support'))})"
            for cid, c in resolved_customers.items()
        )
        dynamic_lines.append(
            f"\n## Already resolved this session\n{lines}\n"
            "Do not call lookup_customer again for these customers."
        )

    blocks.append({"type": "text", "text": "\n".join(dynamic_lines)})
    return blocks


class ClaudeExtractionService(AIService):
    """Claude-powered service with typed tool-use and multi-layer caching."""

    def __init__(
        self,
        session_store: AbstractSessionStore,
        query_cache: QueryCache,
    ) -> None:
        self._store = session_store
        self._cache = query_cache
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    def process_message(self, session_id: str, user_message: str) -> str:
        self._store.append_message(session_id, {"role": "user", "content": user_message})
        try:
            return self._agentic_loop(session_id)
        except AppError as exc:
            logger.warning("AppError in agentic loop: %s", exc.message)
            return f"I ran into an issue: {exc.message} Please try again."
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            raise AIServiceError(str(exc)) from exc

    # ── Private ────────────────────────────────────────────────────────────────

    def _agentic_loop(self, session_id: str) -> str:
        session = self._store.get(session_id)

        while True:
            response = self._client.messages.create(
                model=self._settings.claude_model,
                max_tokens=1024,
                system=_build_system_prompt(session.resolved_customers),
                tools=TOOLS,
                messages=_compress_history(session.conversation_history),
            )

            self._store.append_message(
                session_id, {"role": "assistant", "content": response.content}
            )

            if response.stop_reason == "end_turn":
                return next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )

            if response.stop_reason == "tool_use":
                tool_results = self._execute_tools(session_id, response.content)
                self._store.append_message(
                    session_id, {"role": "user", "content": tool_results}
                )
                session = self._store.get(session_id)
                continue

            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return "Something unexpected happened. Please try again."

    def _execute_tools(self, session_id: str, content_blocks: list) -> list[dict]:
        results: list[dict] = []
        session = self._store.get(session_id)

        for block in content_blocks:
            if block.type != "tool_use":
                continue

            logger.info("Tool call: %s | input=%s", block.name, block.input)

            try:
                output  = self._dispatch(session_id, session.org_id, block.name, block.input)
                content = json.dumps(_truncate(block.name, output))
                is_error = False

                # Only cache when unambiguous — multiple matches require user confirmation first
                if block.name == "lookup_customer" and output.get("found"):
                    if output.get("count", 0) == 1:
                        self._store.cache_customer(session_id, output["customers"][0])

            except AppError as exc:
                content  = json.dumps({"error": exc.message})
                is_error = True
                logger.warning("Tool %s error: %s", block.name, exc.message)
            except Exception as exc:
                content  = json.dumps({"error": f"Unexpected error: {exc}"})
                is_error = True
                logger.exception("Unexpected error in tool %s", block.name)

            results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     content,
                "is_error":    is_error,
            })

        return results

    def _dispatch(
        self, session_id: str, org_id: int, tool_name: str, tool_input: dict
    ) -> dict:
        # Cache-aside: check before hitting DB
        cached = self._cache.get(org_id, tool_name, tool_input)
        if cached is not None:
            return cached

        with SessionLocal() as db:
            if tool_name == "lookup_customer":
                result = CustomerRepository(db).find(org_id, **tool_input)

            elif tool_name == "query_ecommerce":
                result = EcommerceRepository(db).query(org_id, **tool_input)

            elif tool_name == "query_support":
                result = SupportRepository(db).query(org_id, **tool_input)

            elif tool_name == "query_cross_domain":
                result = CrossDomainRepository(db).query(org_id, **tool_input)

            elif tool_name == "query_with_schema":
                result = self._safe_sql(db, org_id, tool_input["sql"])

            else:
                raise DataServiceError(f"Unknown tool: {tool_name}")

        self._cache.set(org_id, tool_name, tool_input, result)
        return result

    @staticmethod
    def _safe_sql(db, org_id: int, sql: str) -> dict:
        """Execute arbitrary SELECT — validates and injects org_id as bind param."""
        if _WRITE_KEYWORDS.search(sql):
            raise DataServiceError(
                "Only SELECT statements are permitted. "
                "Remove any INSERT/UPDATE/DELETE/DROP/CREATE/ALTER."
            )
        if ":org_id" not in sql:
            raise DataServiceError(
                "Query must include :org_id placeholder, e.g. "
                "WHERE table.org_id = :org_id"
            )
        from sqlalchemy import text
        rows = db.execute(text(sql), {"org_id": org_id}).fetchall()
        data = [dict(r._mapping) for r in rows]
        return {"rows": data, "count": len(data)}


# ── History compression ────────────────────────────────────────────────────────

def _compress_history(history: list[dict]) -> list[dict]:
    """Keep last 2 turns (4 messages) full; compress older tool_result blocks."""
    cutoff = max(0, len(history) - 4)
    compressed = []
    for i, msg in enumerate(history):
        if i >= cutoff or msg.get("role") != "user":
            compressed.append(msg)
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            compressed.append(msg)
            continue
        slim = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                try:
                    data = json.loads(block["content"])
                    slim.append({**block, "content": json.dumps(_summarise(data))})
                except Exception:
                    slim.append(block)
            else:
                slim.append(block)
        compressed.append({**msg, "content": slim})
    return compressed


def _summarise(data: dict) -> dict:
    if "customers" in data:
        return {"summary": f"{len(data['customers'])} customers returned"}
    if "orders" in data:
        return {"summary": f"{len(data['orders'])} orders, total_spend={data.get('total_spend')}"}
    if "tickets" in data:
        return {"summary": f"{len(data['tickets'])} tickets returned"}
    if "rows" in data:
        return {"summary": f"{data.get('count', len(data['rows']))} rows returned"}
    return {"summary": "result returned"}


def _truncate(tool_name: str, result: dict) -> dict:
    """Cap large result sets before sending to Claude."""
    for key in ("rows", "orders", "tickets", "customers", "products"):
        rows = result.get(key)
        if rows and len(rows) > _MAX_ROWS_TO_CLAUDE:
            return {
                **result,
                key:         rows[:_MAX_ROWS_TO_CLAUDE],
                "truncated": True,
                "total":     len(rows),
                "shown":     _MAX_ROWS_TO_CLAUDE,
                "hint":      (
                    f"Showing {_MAX_ROWS_TO_CLAUDE} of {len(rows)} results. "
                    "Suggest the user add filters to narrow results."
                ),
            }
    return result
