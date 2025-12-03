"""Database layer for Customer Support Agent System."""

from customer_support_agent.database.client import (
    db_client,
    DATABASE_ID,
    FIRESTORE_PROJECT,
)

__all__ = [
    "db_client",
    "DATABASE_ID",
    "FIRESTORE_PROJECT",
]
