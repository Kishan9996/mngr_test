"""Support domain queries: tickets, interactions, agents."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.data.base import DataRepository

_MAX_ROWS = 50


class SupportRepository(DataRepository):

    def query(
        self,
        org_id:               int,
        customer_id:          int | None  = None,
        status:               str | None  = None,
        priority:             str | None  = None,
        include_interactions: bool        = False,
    ) -> dict:
        sql = """
            SELECT t.id, t.title, t.description, t.status, t.priority, t.created_at,
                   c.name AS customer_name, c.email AS customer_email
            FROM support_tickets t
            JOIN customers c ON c.id = t.customer_id
            WHERE t.org_id = :org_id
        """
        params: dict = {"org_id": org_id}

        if customer_id:
            sql += " AND t.customer_id = :cid"
            params["cid"] = customer_id
        if status:
            sql += " AND t.status = :status"
            params["status"] = status
        if priority:
            sql += " AND t.priority = :priority"
            params["priority"] = priority

        sql += f" ORDER BY t.created_at DESC LIMIT :lim"
        params["lim"] = _MAX_ROWS

        rows = self._db.execute(text(sql), params).fetchall()
        tickets = [dict(r._mapping) for r in rows]

        if include_interactions and tickets:
            ticket_ids = [t["id"] for t in tickets[:10]]  # cap to avoid explosion
            interaction_sql = """
                SELECT i.ticket_id, i.timestamp, i.notes, a.name AS agent_name, a.department
                FROM support_interactions i
                LEFT JOIN support_agents a ON a.id = i.agent_id
                WHERE i.ticket_id IN ({placeholders})
                ORDER BY i.timestamp
            """.format(placeholders=",".join(f":t{i}" for i in range(len(ticket_ids))))
            iparams = {f"t{i}": tid for i, tid in enumerate(ticket_ids)}
            irows = self._db.execute(text(interaction_sql), iparams).fetchall()

            by_ticket: dict[int, list] = {}
            for r in irows:
                by_ticket.setdefault(r.ticket_id, []).append(dict(r._mapping))
            for t in tickets:
                t["interactions"] = by_ticket.get(t["id"], [])

        return {"tickets": tickets, "count": len(tickets)}

    def get_agents(self, org_id: int) -> dict:
        rows = self._db.execute(
            text("SELECT id, name, department, expertise FROM support_agents WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).fetchall()
        return {"agents": [dict(r._mapping) for r in rows]}

    def ticket_counts_by_status(self, org_id: int) -> dict:
        sql = """
            SELECT status, COUNT(*) AS count
            FROM support_tickets
            WHERE org_id = :org_id
            GROUP BY status
        """
        rows = self._db.execute(text(sql), {"org_id": org_id}).fetchall()
        return {r.status: r.count for r in rows}
