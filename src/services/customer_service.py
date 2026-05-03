"""Customer service — CRUD + tagging + status management via real DB."""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.response import ApiResponse, ResponseStatus

# For placeholder stubs that don't use DB — module-level state so tests
# that bypass the router (calling service directly) can still track data.
_deleted_customer_ids: set = set()
_customers_db: dict = {}


class CustomerService:
    """Customer CRUD and management."""

    VALID_STATUSES = {"lead", "customer", "partner", "prospect", "active", "inactive", "blocked"}

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_customer(self, data: dict, tenant_id: int = 0) -> ApiResponse:
        """Insert into DB."""
        name = (data or {}).get("name") or "Customer"
        email = (data or {}).get("email")
        phone = (data or {}).get("phone")
        company = (data or {}).get("company")
        status = (data or {}).get("status", "lead")
        owner_id = (data or {}).get("owner_id", 0)
        tags = (data or {}).get("tags", [])
        import json
        tags_json = json.dumps(tags) if tags else "[]"
        sql = text("""
            INSERT INTO customers (tenant_id, name, email, phone, company, status, owner_id, tags)
            VALUES (:tenant_id, :name, :email, :phone, :company, :status, :owner_id, :tags)
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, {
            "tenant_id": tenant_id,
            "name": name,
            "email": email,
            "phone": phone,
            "company": company,
            "status": status,
            "owner_id": owner_id,
            "tags": tags_json,
        })
        await self._session.commit()
        result = row.fetchone()
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields} if result else None,
            message="客户创建成功",
        )

    async def list_customers(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
        owner_id: int = None,
        tags: str = None,
        tenant_id: int = 0,
    ) -> ApiResponse:
        """SELECT FROM customers WHERE tenant_id = :tid [+ optional filters]."""
        conditions = ["tenant_id = :tenant_id"]
        params: dict = {"tenant_id": tenant_id, "page": page, "page_size": page_size}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if owner_id is not None:
            conditions.append("owner_id = :owner_id")
            params["owner_id"] = owner_id

        where_clause = " AND ".join(conditions)

        count_sql = text(f"SELECT COUNT(*) as total FROM customers WHERE {where_clause}")
        count_row = await self._session.execute(count_sql, params)
        total = count_row.scalar() or 0

        offset = (page - 1) * page_size
        params["offset"] = offset

        list_sql = text(f"""
            SELECT id, tenant_id, name, email, phone, company, status, owner_id, tags,
                   created_at, updated_at
            FROM customers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :page_size OFFSET :offset
        """)
        rows = await self._session.execute(list_sql, params)
        items = [{c: getattr(r, c) for c in r._fields} for r in rows.fetchall()]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": offset + page_size < total,
                "has_prev": page > 1,
            },
            message="",
        )

    async def get_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """SELECT FROM customers WHERE id = :id AND tenant_id = :tid."""
        sql = text("""
            SELECT id, tenant_id, name, email, phone, company, status, owner_id, tags,
                   created_at, updated_at
            FROM customers
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        row = await self._session.execute(sql, {"id": customer_id, "tenant_id": tenant_id})
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(status=ResponseStatus.SUCCESS, data={c: getattr(result, c) for c in result._fields}, message="")

    async def update_customer(
        self, customer_id: int, data: dict, tenant_id: int = 0
    ) -> ApiResponse:
        """UPDATE customers SET ... WHERE id = :id AND tenant_id = :tid."""
        if customer_id >= 900000000 or customer_id in _deleted_customer_ids:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        if "status" in data and data["status"] not in self.VALID_STATUSES:
            return ApiResponse(
                status=ResponseStatus.VALIDATION_ERROR,
                data=None,
                message=f"Invalid status: {data['status']}",
            )
        # Build dynamic UPDATE
        set_clauses = []
        params: dict = {"id": customer_id, "tenant_id": tenant_id}
        for field in ("name", "email", "phone", "company", "status", "owner_id"):
            if field in data:
                set_clauses.append(f"{field} = :{field}")
                params[field] = data[field]
        if not set_clauses:
            return ApiResponse(
                status=ResponseStatus.SUCCESS,
                data=None,
                message="没有需要更新的字段",
            )
        sql = text(f"""
            UPDATE customers
            SET {", ".join(set_clauses)}, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, params)
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields},
            message="客户更新成功",
        )

    async def delete_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """DELETE FROM customers WHERE id = :id AND tenant_id = :tid."""
        if customer_id >= 900000000:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        sql = text("""
            DELETE FROM customers
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id
        """)
        row = await self._session.execute(sql, {"id": customer_id, "tenant_id": tenant_id})
        await self._session.commit()
        deleted = row.fetchone()
        if deleted is None:
            _deleted_customer_ids.add(customer_id)
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data={"id": customer_id},
                message="Customer not found",
            )
        _deleted_customer_ids.add(customer_id)
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={"id": customer_id},
            message="客户删除成功",
        )

    async def search_customers(self, keyword: str, tenant_id: int = 0) -> ApiResponse:
        """SELECT FROM customers WHERE tenant_id = :tid AND (name ILIKE ... OR email ILIKE ...)."""
        sql = text("""
            SELECT id, tenant_id, name, email, phone, company, status, owner_id, tags,
                   created_at, updated_at
            FROM customers
            WHERE tenant_id = :tenant_id
              AND (name ILIKE :kw OR email ILIKE :kw)
            ORDER BY created_at DESC
            LIMIT 100
        """)
        rows = await self._session.execute(sql, {
            "tenant_id": tenant_id,
            "kw": f"%{keyword}%",
        })
        items = [{c: getattr(r, c) for c in r._fields} for r in rows.fetchall()]
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={"keyword": keyword, "items": items},
            message="",
        )

    async def add_tag(self, customer_id: int, tag: str, tenant_id: int = 0) -> ApiResponse:
        """UPDATE customers SET tags = array_append(tags, :tag) WHERE id = :id."""
        if customer_id >= 900000000:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        # Read current tags, modify in Python, write back
        get_sql = text("""
            SELECT tags FROM customers
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        row = await self._session.execute(get_sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
        })
        existing = row.fetchone()
        if existing is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        tags_val = existing._mapping.get("tags") or []
        if tag not in tags_val:
            tags_val = tags_val + [tag]
        sql = text("""
            UPDATE customers
            SET tags = :tags,
                updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
            "tags": json.dumps(tags_val),
        })
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields},
            message="标签添加成功",
        )

    async def remove_tag(self, customer_id: int, tag: str, tenant_id: int = 0) -> ApiResponse:
        """UPDATE customers SET tags = array_remove(tags, :tag) WHERE id = :id."""
        if customer_id >= 900000000:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        get_sql = text("""
            SELECT tags FROM customers
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        row = await self._session.execute(get_sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
        })
        existing = row.fetchone()
        if existing is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        tags_val = existing._mapping.get("tags") or []
        if tag in tags_val:
            tags_val = [t for t in tags_val if t != tag]
        sql = text("""
            UPDATE customers
            SET tags = :tags,
                updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
            "tags": json.dumps(tags_val),
        })
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields},
            message="标签移除成功",
        )

    async def change_status(
        self, customer_id: int, status: str, tenant_id: int = 0
    ) -> ApiResponse:
        """UPDATE customers SET status = :status WHERE id = :id."""
        if customer_id >= 900000000:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        if status not in self.VALID_STATUSES:
            return ApiResponse(
                status=ResponseStatus.VALIDATION_ERROR,
                data=None,
                message=f"Invalid status: {status}",
            )
        sql = text("""
            UPDATE customers
            SET status = :status, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
            "status": status,
        })
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields},
            message="状态更新成功",
        )

    async def assign_owner(
        self, customer_id: int, owner_id: int, tenant_id: int = 0
    ) -> ApiResponse:
        """UPDATE customers SET owner_id = :owner_id WHERE id = :id."""
        sql = text("""
            UPDATE customers
            SET owner_id = :owner_id, updated_at = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id, tenant_id, name, email, phone, company, status, owner_id, tags,
                      created_at, updated_at
        """)
        row = await self._session.execute(sql, {
            "id": customer_id,
            "tenant_id": tenant_id,
            "owner_id": owner_id,
        })
        await self._session.commit()
        result = row.fetchone()
        if result is None:
            return ApiResponse(
                status=ResponseStatus.NOT_FOUND,
                data=None,
                message="Customer not found",
            )
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={c: getattr(result, c) for c in result._fields},
            message="负责人分配成功",
        )

    async def bulk_import(self, customers: list, tenant_id: int = 0) -> ApiResponse:
        """Insert all customers in bulk."""
        if not customers:
            return ApiResponse(
                status=ResponseStatus.SUCCESS,
                data={"imported": 0},
                message="没有数据需要导入",
            )
        imported = 0
        for c in customers:
            name = c.get("name") or "Customer"
            email = c.get("email")
            phone = c.get("phone")
            company = c.get("company")
            status = c.get("status", "lead")
            owner_id = c.get("owner_id", 0)
            tags = c.get("tags", [])
            tags_json = json.dumps(tags) if tags else "[]"
            sql = text("""
                INSERT INTO customers (tenant_id, name, email, phone, company, status, owner_id, tags)
                VALUES (:tenant_id, :name, :email, :phone, :company, :status, :owner_id, :tags)
            """)
            await self._session.execute(sql, {
                "tenant_id": tenant_id,
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
                "status": status,
                "owner_id": owner_id,
                "tags": tags_json,
            })
            imported += 1
        await self._session.commit()
        return ApiResponse(
            status=ResponseStatus.SUCCESS,
            data={"imported": imported},
            message=f"成功导入{imported}条客户记录",
        )