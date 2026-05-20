"""API router discovery.

Router modules own their registration by exporting one or more FastAPI
``APIRouter`` instances. New domains should add ``src/api/routers/<domain>.py``;
this package discovers it without requiring a central import update.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator

from fastapi import APIRouter

from api import routers


def iter_routers() -> Iterator[APIRouter]:
    """Yield all APIRouter instances exported by modules in ``api.routers``."""
    for info in sorted(pkgutil.iter_modules(routers.__path__, prefix=f"{routers.__name__}."), key=lambda item: item.name):
        module = importlib.import_module(info.name)
        for name in sorted(dir(module)):
            value = getattr(module, name)
            if isinstance(value, APIRouter):
                yield value


__all__ = ["iter_routers"]
