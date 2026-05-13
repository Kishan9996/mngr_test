from __future__ import annotations

from abc import ABC

from sqlalchemy.orm import Session


class DataRepository(ABC):
    """All data repositories receive a DB session and operate within it.

    org_id is injected by the dispatch layer — never passed through tool input.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
