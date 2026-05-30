"""Load and re-export ORM models.

Model modules own their SQLAlchemy classes. New domains should add
``src/db/models/<domain>.py``; importing this package discovers model classes
and registers their tables with ``Base.metadata``.
"""

from __future__ import annotations

import importlib
import pkgutil

from db.base import Base
from internal.db.models import (  # noqa: F401 — auto-discovery populates globals from module
    IdentityDepartmentModel,
    IdentityOrganizationModel,
    IdentityPermissionModel,
    IdentityRoleModel,
    IdentityRolePermissionModel,
    IdentityTenantModel,
    IdentityUserModel,
    IdentityUserRoleModel,
)

# Auto-discover old-style ORM models registered under src/db/models/
for _info in sorted(pkgutil.iter_modules(__path__, prefix=f"{__name__}."), key=lambda item: item.name):
    if _info.name == __name__:
        continue
    _module = importlib.import_module(_info.name)
    for _name, _value in vars(_module).items():
        if isinstance(_value, type) and issubclass(_value, Base) and _value is not Base:
            globals()[_name] = _value

# __all__ = all discovered old-style models + explicitly imported identity models
__all__ = sorted(
    name
    for name, value in globals().items()
    if isinstance(value, type) and issubclass(value, Base) and value is not Base
)
