"""Ecommerce domain queries: orders, products, categories."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import DataServiceError
from app.services.data.base import DataRepository

_MAX_ROWS = 50
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str | None, field: str) -> None:
    if value and not _DATE_RE.match(value):
        raise DataServiceError(
            f"Invalid {field} format '{value}'. Use YYYY-MM-DD (e.g. 2026-01-31)."
        )


class EcommerceRepository(DataRepository):

    def query(
        self,
        org_id: int,
        customer_id: int | None = None,
        date_from:   str | None = None,
        date_to:     str | None = None,
        aggregate:   str | None = None,   # total_spend | order_count | spend_per_customer
    ) -> dict:
        _validate_date(date_from, "date_from")
        _validate_date(date_to,   "date_to")

        if aggregate == "spend_per_customer":
            return self._spend_per_customer(org_id)

        if aggregate in ("total_spend", "order_count"):
            if not customer_id:
                raise DataServiceError(
                    f"aggregate='{aggregate}' requires a customer_id. "
                    "Call lookup_customer first to resolve one."
                )
            return self._customer_aggregate(org_id, customer_id, aggregate)

        return self._order_rows(org_id, customer_id, date_from, date_to)

    def get_products(self, org_id: int, category: str | None = None) -> dict:
        sql = """
            SELECT p.id, p.name, p.description, p.price,
                   c.name AS category_name
            FROM ecom_products p
            LEFT JOIN ecom_categories c ON c.id = p.category_id
            WHERE p.org_id = :org_id
        """
        params: dict = {"org_id": org_id}
        if category:
            sql += " AND c.name LIKE :cat COLLATE NOCASE"
            params["cat"] = f"%{category}%"
        sql += " ORDER BY c.name, p.price"

        rows = self._db.execute(text(sql), params).fetchall()
        return {"products": [dict(r._mapping) for r in rows], "count": len(rows)}

    # ── Private helpers ────────────────────────────────────────────────────────

    def _spend_per_customer(self, org_id: int) -> dict:
        sql = """
            SELECT c.id AS customer_id, c.name, c.email,
                   ROUND(SUM(o.total_amount), 2) AS total_spend,
                   COUNT(o.id)                   AS order_count
            FROM ecom_orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE o.org_id = :org_id
            GROUP BY c.id, c.name, c.email
            ORDER BY total_spend DESC
            LIMIT :lim
        """
        rows = self._db.execute(text(sql), {"org_id": org_id, "lim": _MAX_ROWS}).fetchall()
        return {"aggregate": "spend_per_customer", "rows": [dict(r._mapping) for r in rows]}

    def _customer_aggregate(self, org_id: int, customer_id: int, aggregate: str) -> dict:
        sql = """
            SELECT ROUND(SUM(total_amount), 2) AS total_spend,
                   COUNT(id) AS order_count
            FROM ecom_orders
            WHERE org_id = :org_id AND customer_id = :cid
        """
        row = self._db.execute(text(sql), {"org_id": org_id, "cid": customer_id}).fetchone()
        if not row:
            return {"total_spend": 0.0, "order_count": 0}
        return {"total_spend": row.total_spend or 0.0, "order_count": row.order_count or 0}

    def _order_rows(
        self,
        org_id: int,
        customer_id: int | None,
        date_from: str | None,
        date_to: str | None,
    ) -> dict:
        select_cols = "o.id, o.order_date, o.total_amount, c.name AS customer_name, c.email"
        joins = "JOIN customers c ON c.id = o.customer_id"

        sql = f"SELECT {select_cols} FROM ecom_orders o {joins} WHERE o.org_id = :org_id"
        params: dict = {"org_id": org_id}

        if customer_id:
            sql += " AND o.customer_id = :cid"
            params["cid"] = customer_id
        if date_from:
            sql += " AND o.order_date >= :df"
            params["df"] = date_from
        if date_to:
            sql += " AND o.order_date <= :dt"
            params["dt"] = date_to

        sql += " ORDER BY o.order_date DESC LIMIT :lim"
        params["lim"] = _MAX_ROWS

        rows = self._db.execute(text(sql), params).fetchall()
        data = [dict(r._mapping) for r in rows]
        return {"orders": data, "count": len(data)}
