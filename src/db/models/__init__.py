"""Load and re-export ORM models.

Model modules own their SQLAlchemy classes. New domains should add
``src/db/models/<domain>.py``; importing this package discovers model classes
and registers their tables with ``Base.metadata``.
"""

from __future__ import annotations

import importlib
import pkgutil

from db.base import Base

_package_name = __name__
_model_names: list[str] = []

for _info in sorted(pkgutil.iter_modules(__path__, prefix=f"{_package_name}."), key=lambda item: item.name):
    if _info.name == _package_name:
        continue
    _module = importlib.import_module(_info.name)
    for _name, _value in vars(_module).items():
        if isinstance(_value, type) and issubclass(_value, Base) and _value is not Base:
            globals()[_name] = _value
            _model_names.append(_name)

__all__ = sorted(set(_model_names))
