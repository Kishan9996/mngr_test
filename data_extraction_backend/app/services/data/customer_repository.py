"""Canonical customer lookups across both domains."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.data.base import DataRepository


class CustomerRepository(DataRepository):

    def find(
        self,
        org_id: int,
        name: str | None = None,
        email: str | None = None,
    ) -> dict:
        if not name and not email:
            return {"found": False, "message": "Provide name or email to look up a customer."}

        sql = """
            SELECT
                c.id, c.name, c.email,
                ep.location,
                sp.contact_info,
                sp.account_status,
                CASE WHEN ep.customer_id IS NOT NULL THEN 1 ELSE 0 END AS in_ecommerce,
                CASE WHEN sp.customer_id IS NOT NULL THEN 1 ELSE 0 END AS in_support
            FROM customers c
            LEFT JOIN ecom_customer_profiles    ep ON ep.customer_id = c.id
            LEFT JOIN support_customer_profiles sp ON sp.customer_id = c.id
            WHERE c.org_id = :org_id
        """
        params: dict = {"org_id": org_id}

        if name:
            sql += " AND c.name LIKE :name COLLATE NOCASE"
            params["name"] = f"%{name}%"
        if email:
            sql += " AND lower(c.email) = :email"
            params["email"] = email.lower()

        rows = self._db.execute(text(sql), params).fetchall()
        if not rows:
            term = email or name
            return {"found": False, "message": f"No customer matching '{term}'."}

        customers = [dict(r._mapping) for r in rows]
        return {"found": True, "customers": customers, "count": len(customers)}

    def exists_in_ecommerce(self, org_id: int, customer_id: int) -> bool:
        row = self._db.execute(
            text("SELECT 1 FROM ecom_customer_profiles WHERE customer_id = :cid"),
            {"cid": customer_id},
        ).fetchone()
        return row is not None

    def exists_in_support(self, org_id: int, customer_id: int) -> bool:
        row = self._db.execute(
            text("SELECT 1 FROM support_customer_profiles WHERE customer_id = :cid"),
            {"cid": customer_id},
        ).fetchone()
        return row is not None
