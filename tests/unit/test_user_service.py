"""Unit tests for UserService."""
import pytest
from services.user_service import UserService


@pytest.fixture
def service(mock_db_session):
    return UserService(mock_db_session)


@pytest.mark.asyncio
class TestUserService:



















    pass
