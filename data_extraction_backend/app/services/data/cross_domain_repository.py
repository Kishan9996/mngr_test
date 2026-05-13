"""Queries that span both ecommerce and support domains."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.data.base import DataRepository

_MAX_ROWS = 50


class CrossDomainRepository(DataRepository):

    def query(
        self,
        org_id:               int,
        customer_id:          int | None = None,
        filter:               str | None = None,   # has_both | ecommerce_only | support_only
        include_order_totals: bool       = False,
        include_ticket_counts: bool      = False,
    ) -> dict:
        if filter == "ecommerce_only":
            return self._ecommerce_only(org_id)
        if filter == "support_only":
            return self._support_only(org_id)
        return self._combined(org_id, customer_id, filter, include_order_totals, include_ticket_counts)

    def get_customer_full_profile(self, org_id: int, customer_id: int) -> dict:
        """Orders + open tickets for one customer in a single response."""
        order_sql = """
            SELECT id, order_date, total_amount
            FROM ecom_orders
            WHERE org_id = :org_id AND customer_id = :cid
            ORDER BY order_date DESC
            LIMIT 20
        """
        ticket_sql = """
            SELECT id, title, status, priority, created_at
            FROM support_tickets
            WHERE org_id = :org_id AND customer_id = :cid
            ORDER BY created_at DESC
            LIMIT 20
        """
        params = {"org_id": org_id, "cid": customer_id}
        orders  = [dict(r._mapping) for r in self._db.execute(text(order_sql),  params).fetchall()]
        tickets = [dict(r._mapping) for r in self._db.execute(text(ticket_sql), params).fetchall()]

        total_spend = sum(o["total_amount"] for o in orders)
        return {
            "customer_id":    customer_id,
            "orders":         orders,
            "order_count":    len(orders),
            "total_spend":    round(total_spend, 2),
            "tickets":        tickets,
            "ticket_count":   len(tickets),
            "open_tickets":   [t for t in tickets if t["status"] != "closed"],
        }

    # ── Private ────────────────────────────────────────────────────────────────

    def _ecommerce_only(self, org_id: int) -> dict:
        sql = """
            SELECT c.id, c.name, c.email, ep.location
            FROM customers c
            JOIN ecom_customer_profiles ep ON ep.customer_id = c.id
            WHERE c.org_id = :org_id
              AND NOT EXISTS (
                  SELECT 1 FROM support_customer_profiles sp
                  WHERE sp.customer_id = c.id
              )
            LIMIT :lim
        """
        rows = self._db.execute(text(sql), {"org_id": org_id, "lim": _MAX_ROWS}).fetchall()
        return {
            "filter": "ecommerce_only",
            "description": "Customers who have placed orders but never raised a support ticket",
            "customers": [dict(r._mapping) for r in rows],
            "count": len(rows),
        }

    def _support_only(self, org_id: int) -> dict:
        sql = """
            SELECT c.id, c.name, c.email, sp.account_status
            FROM customers c
            JOIN support_customer_profiles sp ON sp.customer_id = c.id
            WHERE c.org_id = :org_id
              AND NOT EXISTS (
                  SELECT 1 FROM ecom_customer_profiles ep
                  WHERE ep.customer_id = c.id
              )
            LIMIT :lim
        """
        rows = self._db.execute(text(sql), {"org_id": org_id, "lim": _MAX_ROWS}).fetchall()
        return {
            "filter": "support_only",
            "description": "Customers who have raised support tickets but never placed an order",
            "customers": [dict(r._mapping) for r in rows],
            "count": len(rows),
        }

    def _combined(
        self,
        org_id: int,
        customer_id: int | None,
        filter: str | None,
        include_order_totals: bool,
        include_ticket_counts: bool,
    ) -> dict:
        select_parts = ["c.id AS customer_id", "c.name", "c.email"]
        joins: list[str] = []
        wheres = ["c.org_id = :org_id"]
        params: dict = {"org_id": org_id}

        if include_order_totals or filter == "has_both":
            select_parts += [
                "ROUND(COALESCE(SUM(DISTINCT o.total_amount), 0), 2) AS total_spend",
                "COUNT(DISTINCT o.id) AS order_count",
            ]
            joins.append(
                "LEFT JOIN ecom_orders o ON o.customer_id = c.id AND o.org_id = :org_id"
            )

        if include_ticket_counts or filter == "has_both":
            select_parts.append("COUNT(DISTINCT t.id) AS ticket_count")
            joins.append(
                "LEFT JOIN support_tickets t ON t.customer_id = c.id AND t.org_id = :org_id"
            )

        if filter == "has_both":
            wheres += [
                "EXISTS (SELECT 1 FROM ecom_orders eo    WHERE eo.customer_id = c.id AND eo.org_id = :org_id)",
                "EXISTS (SELECT 1 FROM support_tickets st WHERE st.customer_id = c.id AND st.org_id = :org_id)",
            ]

        if customer_id:
            wheres.append("c.id = :cid")
            params["cid"] = customer_id

        sql = (
            f"SELECT {', '.join(select_parts)}"
            f" FROM customers c"
            f" {' '.join(joins)}"
            f" WHERE {' AND '.join(wheres)}"
            f" GROUP BY c.id, c.name, c.email"
            f" LIMIT :lim"
        )
        params["lim"] = _MAX_ROWS

        rows = self._db.execute(text(sql), params).fetchall()
        return {
            "filter": filter or "combined",
            "rows": [dict(r._mapping) for r in rows],
            "count": len(rows),
        }
