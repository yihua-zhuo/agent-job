"""租户上下文（线程本地存储）"""

import threading


class TenantContext:
    """租户上下文（线程本地存储）"""

    _local = threading.local()

    @classmethod
    def set_tenant_id(cls, tenant_id: int):
        cls._local.tenant_id = tenant_id

    @classmethod
    def get_tenant_id(cls) -> int | None:
        return getattr(cls._local, "tenant_id", None)

    @classmethod
    def clear(cls):
        cls._local.tenant_id = None
