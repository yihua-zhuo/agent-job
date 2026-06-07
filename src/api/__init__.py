"""API router discovery.

Router modules own their registration by exporting one or more FastAPI
``APIRouter`` instances. New domains should add ``src/api/routers/<domain>.py``;
this package discovers it without requiring a central import update.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Iterator

from fastapi import APIRouter

from api import routers

_logger = logging.getLogger(__name__)


def iter_routers() -> Iterator[APIRouter]:
    """Yield all APIRouter instances exported by modules in ``api.routers``.

    Routers are discovered by name convention: only attributes whose names
    match ``router`` or end with ``_router`` are considered.  This makes
    discovery deterministic and intent-explicit, avoiding accidental
    inclusion of non-router public attributes.
    """
    for info in sorted(
        pkgutil.iter_modules(routers.__path__, prefix=f"{routers.__name__}."),
        key=lambda item: item.name,
    ):
        module = importlib.import_module(info.name)
        for name in sorted(dir(module)):
            value = getattr(module, name, None)
            if not isinstance(value, APIRouter):
                continue
            if name == "router" or name.endswith("_router"):
                yield value
            else:
                _logger.debug(
                    "Skipping non-conforming APIRouter %r in %s; "
                    "rename to 'router' or '_router' suffix to include it.",
                    name,
                    info.name,
                )


__all__ = ["iter_routers"]
