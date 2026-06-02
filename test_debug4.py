import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
sys.path.insert(0, '/home/runner/work/agent-job/agent-job/src')

from src.pkg.errors.app_exceptions import NotFoundException, ValidationException

# What pytest.raises sees
try:
    with pytest.raises(NotFoundException) as exc_info:
        exc = NotFoundException('Ticket')
        print(f"Exception created: {type(exc)}, id={id(exc)}")
        print(f"Exception module: {exc.__class__.__module__}")
        print(f"Exception class: {exc.__class__}")
        print(f"Exception repr: {repr(exc)}")
        raise exc
except Exception as e:
    print(f"Caught by pytest.raises: {type(e)}, id={id(e)}")
    print(f"Match: {e is exc}")

print()
# Check what pytest expects to match
print("pytest.raises checks:", pytest.raises(NotFoundException))

# Try with match= param
try:
    with pytest.raises(NotFoundException, match="not found") as exc_info2:
        raise NotFoundException('Ticket')
    print("match= param: PASSED")
except Exception as e:
    print(f"match= param: FAILED with {type(e)}")
