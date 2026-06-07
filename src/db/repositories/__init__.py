"""Re-export all repository classes."""

from db.repositories.base import BaseRepository
from db.repositories.customer import CustomerRepository

__all__ = ["BaseRepository", "CustomerRepository"]
