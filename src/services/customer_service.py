"""Customer service layer - handles customer business logic via PostgreSQL/SQLAlchemy async."""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import select, update, delete, func, text
from src.db.connection import get_db_session
from src.db.models.customer import CustomerModel
from src.models.response import ApiResponse
from src.models.customer import Customer, CustomerStatus


class CustomerService:
    """Customer service backed by PostgreSQL via SQLAlchemy async."""

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------
    async def create_customer(self, data: dict, tenant_id: int = 0) -> ApiResponse:
        """Create a new customer"""
        if not data.get('name'):
            return ApiResponse.error(message="客户名称不能为空", code=3001)

        status_value = data.get('status', 'lead')
        if isinstance(status_value, str):
            try:
                status_value = CustomerStatus(status_value)
            except ValueError:
                status_value = CustomerStatus.LEAD

        name = data['name']
        email = data.get('email')
        phone = data.get('phone')
        company = data.get('company')
        owner_id = data.get('owner_id', 0)
        tags = data.get('tags', [])

        # Raw SQL INSERT with RETURNING *
        insert_sql = text("""
            INSERT INTO customers (tenant_id, name, email, phone, company, status,
                                   owner_id, tags, created_at, updated_at)
            VALUES (:tenant_id, :name, :email, :phone, :company, :status,
                    :owner_id, :tags::jsonb, :created_at, :updated_at)
            RETURNING *
        """)
        now = datetime.utcnow()

        async with get_db_session() as session:
            result = await session.execute(
                insert_sql,
                {
                    "tenant_id": tenant_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "company": company,
                    "status": status_value.value,
                    "owner_id": owner_id,
                    "tags": tags,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            row = result.fetchone()
            if row is None:
                return ApiResponse.error(message="客户创建失败", code=1500)
            customer_dict = self._row_to_dict(row._mapping)
        return ApiResponse.success(data=customer_dict, message="客户创建成功")

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------
    async def list_customers(
        self,
        page=1,
        page_size=20,
        status=None,
        owner_id=None,
        tags=None,
        tenant_id: int = 0,
    ) -> ApiResponse:
        """List customers with pagination and filters"""
        conditions = []
        params: dict = {}

        if tenant_id != 0:
            conditions.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id

        if status:
            conditions.append("status = :status")
            params["status"] = status

        if owner_id:
            conditions.append("owner_id = :owner_id")
            params["owner_id"] = owner_id

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Total count query
        count_sql = text(f"SELECT COUNT(*) AS total FROM customers WHERE {where_clause}")
        # Data query with LIMIT/OFFSET
        data_sql = text(
            f"SELECT * FROM customers WHERE {where_clause} "
            f"ORDER BY id LIMIT :limit OFFSET :offset"
        )

        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

        async with get_db_session() as session:
            count_result = await session.execute(count_sql, params)
            total = count_result.scalar() or 0

            data_result = await session.execute(data_sql, params)
            rows = data_result.fetchall()

        items = [self._row_to_dict(row._mapping) for row in rows]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="",
        )

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------
    async def get_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """Get customer by ID"""
        sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            customer_dict = self._row_to_dict(row._mapping)

        # Tenant isolation check (same logic as original: non-zero tenant_id enforced)
        if tenant_id and customer_dict.get("tenant_id") != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)

        return ApiResponse.success(data=customer_dict, message="")

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------
    async def update_customer(
        self, customer_id: int, data: dict, tenant_id: int = 0
    ) -> ApiResponse:
        """Update customer fields"""
        # Verify record exists and belongs to tenant
        fetch_sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(fetch_sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            if tenant_id and row._mapping.get("tenant_id") != tenant_id:
                return ApiResponse.error(message="客户不存在", code=3001)

        # Build dynamic UPDATE
        update_fields = []
        params: dict = {"id": customer_id}
        for key in ['name', 'email', 'phone', 'company', 'owner_id']:
            if key in data:
                update_fields.append(f"{key} = :{key}")
                params[key] = data[key]

        if 'status' in data:
            status_val = data['status']
            if isinstance(status_val, str):
                try:
                    status_val = CustomerStatus(status_val)
                except ValueError:
                    status_val = CustomerStatus.LEAD
            update_fields.append("status = :status")
            params["status"] = status_val.value

        if 'tags' in data:
            update_fields.append("tags = :tags::jsonb")
            params["tags"] = data["tags"]

        if not update_fields:
            return ApiResponse.error(message="没有需要更新的字段", code=1001)

        update_fields.append("updated_at = :updated_at")
        params["updated_at"] = datetime.utcnow()

        # Tenant isolation: UPDATE ... WHERE id=? AND tenant_id=?
        if tenant_id:
            params["tenant_id"] = tenant_id
            where_clause = "id = :id AND tenant_id = :tenant_id"
        else:
            where_clause = "id = :id"

        update_sql = text(
            f"UPDATE customers SET {', '.join(update_fields)} WHERE {where_clause} RETURNING *"
        )

        async with get_db_session() as session:
            result = await session.execute(update_sql, params)
            updated_row = result.fetchone()
            if not updated_row:
                return ApiResponse.error(message="客户不存在", code=3001)
            customer_dict = self._row_to_dict(updated_row._mapping)

        return ApiResponse.success(data=customer_dict, message="客户更新成功")

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------
    async def delete_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """Delete a customer"""
        # Tenant isolation: DELETE ... WHERE id=? AND tenant_id=?
        params: dict = {"id": customer_id}
        if tenant_id:
            params["tenant_id"] = tenant_id
            where_clause = "id = :id AND tenant_id = :tenant_id"
        else:
            where_clause = "id = :id"

        del_sql = text(f"DELETE FROM customers WHERE {where_clause} RETURNING id")

        async with get_db_session() as session:
            result = await session.execute(del_sql, params)
            deleted_row = result.fetchone()
            if not deleted_row:
                return ApiResponse.error(message="客户不存在", code=3001)

        return ApiResponse.success(message="客户删除成功")

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    async def search_customers(self, keyword: str, tenant_id: int = 0) -> ApiResponse:
        """Search customers by keyword (tenant-scoped)"""
        params: dict = {"keyword": f"%{keyword.lower()}%"}
        if tenant_id:
            params["tenant_id"] = tenant_id
            where_clause = "tenant_id = :tenant_id AND (LOWER(name) LIKE :keyword OR LOWER(email) LIKE :keyword)"
        else:
            where_clause = "(LOWER(name) LIKE :keyword OR LOWER(email) LIKE :keyword)"

        sql = text(f"SELECT * FROM customers WHERE {where_clause} ORDER BY id")
        async with get_db_session() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

        items = [self._row_to_dict(row._mapping) for row in rows]
        return ApiResponse.success(data={"keyword": keyword, "items": items}, message="")

    # ------------------------------------------------------------------
    # add_tag
    # ------------------------------------------------------------------
    async def add_tag(self, customer_id: int, tag: str, tenant_id: int = 0) -> ApiResponse:
        """Add a tag to customer"""
        fetch_sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(fetch_sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            if tenant_id and row._mapping.get("tenant_id") != tenant_id:
                return ApiResponse.error(message="客户不存在", code=3001)

            existing_tags = row._mapping.get("tags") or []
            if isinstance(existing_tags, str):
                import json
                existing_tags = json.loads(existing_tags)

            if tag not in existing_tags:
                existing_tags = existing_tags + [tag]

            now = datetime.utcnow()
            update_sql = text(
                "UPDATE customers SET tags = :tags::jsonb, updated_at = :updated_at "
                "WHERE id = :id RETURNING *"
            )
            upd_result = await session.execute(
                update_sql, {"tags": existing_tags, "updated_at": now, "id": customer_id}
            )
            upd_result.fetchone()

        return ApiResponse.success(data={"id": customer_id, "tag": tag}, message="标签添加成功")

    # ------------------------------------------------------------------
    # remove_tag
    # ------------------------------------------------------------------
    async def remove_tag(
        self, customer_id: int, tag: str, tenant_id: int = 0
    ) -> ApiResponse:
        """Remove a tag from customer"""
        fetch_sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(fetch_sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            if tenant_id and row._mapping.get("tenant_id") != tenant_id:
                return ApiResponse.error(message="客户不存在", code=3001)

            existing_tags = row._mapping.get("tags") or []
            if isinstance(existing_tags, str):
                import json
                existing_tags = json.loads(existing_tags)

            if tag in existing_tags:
                existing_tags = [t for t in existing_tags if t != tag]

            now = datetime.utcnow()
            update_sql = text(
                "UPDATE customers SET tags = :tags::jsonb, updated_at = :updated_at "
                "WHERE id = :id RETURNING *"
            )
            await session.execute(
                update_sql, {"tags": existing_tags, "updated_at": now, "id": customer_id}
            )

        return ApiResponse.success(data={"id": customer_id, "tag": tag}, message="标签移除成功")

    # ------------------------------------------------------------------
    # change_status
    # ------------------------------------------------------------------
    async def change_status(
        self, customer_id: int, status: str, tenant_id: int = 0
    ) -> ApiResponse:
        """Change customer status"""
        fetch_sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(fetch_sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            if tenant_id and row._mapping.get("tenant_id") != tenant_id:
                return ApiResponse.error(message="客户不存在", code=3001)

        try:
            new_status = CustomerStatus(status)
        except ValueError:
            new_status = CustomerStatus.LEAD

        params: dict = {"id": customer_id, "status": new_status.value, "updated_at": datetime.utcnow()}
        if tenant_id:
            params["tenant_id"] = tenant_id
            where_clause = "id = :id AND tenant_id = :tenant_id"
        else:
            where_clause = "id = :id"

        update_sql = text(
            f"UPDATE customers SET status = :status, updated_at = :updated_at "
            f"WHERE {where_clause} RETURNING *"
        )

        async with get_db_session() as session:
            await session.execute(update_sql, params)
            result = await session.execute(fetch_sql, {"id": customer_id})
            updated_row = result.fetchone()
            if not updated_row:
                return ApiResponse.error(message="客户不存在", code=3001)

        return ApiResponse.success(
            data={"id": customer_id, "status": new_status.value}, message="状态更新成功"
        )

    # ------------------------------------------------------------------
    # assign_owner
    # ------------------------------------------------------------------
    async def assign_owner(
        self, customer_id: int, owner_id: int, tenant_id: int = 0
    ) -> ApiResponse:
        """Assign owner to customer"""
        fetch_sql = text("SELECT * FROM customers WHERE id = :id")
        async with get_db_session() as session:
            result = await session.execute(fetch_sql, {"id": customer_id})
            row = result.fetchone()
            if not row:
                return ApiResponse.error(message="客户不存在", code=3001)
            if tenant_id and row._mapping.get("tenant_id") != tenant_id:
                return ApiResponse.error(message="客户不存在", code=3001)

        params: dict = {"id": customer_id, "owner_id": owner_id, "updated_at": datetime.utcnow()}
        if tenant_id:
            params["tenant_id"] = tenant_id
            where_clause = "id = :id AND tenant_id = :tenant_id"
        else:
            where_clause = "id = :id"

        update_sql = text(
            f"UPDATE customers SET owner_id = :owner_id, updated_at = :updated_at "
            f"WHERE {where_clause} RETURNING *"
        )

        async with get_db_session() as session:
            await session.execute(update_sql, params)
            result = await session.execute(fetch_sql, {"id": customer_id})
            updated_row = result.fetchone()
            if not updated_row:
                return ApiResponse.error(message="客户不存在", code=3001)

        return ApiResponse.success(
            data={"id": customer_id, "owner_id": owner_id}, message="负责人分配成功"
        )

    # ------------------------------------------------------------------
    # bulk_import
    # ------------------------------------------------------------------
    async def bulk_import(self, customers: list, tenant_id: int = 0) -> ApiResponse:
        """Bulk import customers"""
        if not isinstance(customers, list):
            return ApiResponse.error(message="customers 必须是数组", code=1001)

        imported = 0
        errors = []
        now = datetime.utcnow()

        for i, data in enumerate(customers):
            if not data.get('name'):
                errors.append({"index": i, "error": "客户名称不能为空"})
                continue

            status_value = data.get('status', 'lead')
            if isinstance(status_value, str):
                try:
                    status_value = CustomerStatus(status_value)
                except ValueError:
                    status_value = CustomerStatus.LEAD

            tags = data.get('tags', [])

            insert_sql = text("""
                INSERT INTO customers (tenant_id, name, email, phone, company, status,
                                       owner_id, tags, created_at, updated_at)
                VALUES (:tenant_id, :name, :email, :phone, :company, :status,
                        :owner_id, :tags::jsonb, :created_at, :updated_at)
                RETURNING id
            """)

            async with get_db_session() as session:
                try:
                    result = await session.execute(
                        insert_sql,
                        {
                            "tenant_id": tenant_id,
                            "name": data['name'],
                            "email": data.get('email'),
                            "phone": data.get('phone'),
                            "company": data.get('company'),
                            "status": status_value.value,
                            "owner_id": data.get('owner_id', 0),
                            "tags": tags,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    row = result.fetchone()
                    if row is None:
                        errors.append({"index": i, "error": "客户创建失败"})
                        continue
                    imported += 1
                except Exception as e:
                    errors.append({"index": i, "error": str(e)})

        return ApiResponse.success(
            data={"imported": imported, "errors": errors},
            message=f"成功导入{imported}条客户记录",
        )

    # ------------------------------------------------------------------
    # count_by_status
    # ------------------------------------------------------------------
    async def count_by_status(self, tenant_id: int) -> Dict[CustomerStatus, int]:
        """Return count of customers grouped by CustomerStatus for a given tenant."""
        if tenant_id <= 0:
            return {}

        sql = text(
            "SELECT status, COUNT(*) AS cnt FROM customers "
            "WHERE tenant_id = :tenant_id GROUP BY status"
        )

        async with get_db_session() as session:
            result = await session.execute(sql, {"tenant_id": tenant_id})
            rows = result.fetchall()

        counts: Dict[CustomerStatus, int] = {}
        for row in rows:
            status_str = row._mapping["status"]
            try:
                cs = CustomerStatus(status_str)
            except ValueError:
                cs = CustomerStatus.LEAD
            counts[cs] = row._mapping["cnt"]

        return counts

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_dict(mapping) -> dict:
        """Convert a RowMapping from a result row to a plain dict."""
        result = dict(mapping)
        # Ensure status is the string value
        if "status" in result and hasattr(result["status"], "value"):
            result["status"] = result["status"].value
        # Format datetime fields as ISO strings
        for field in ("created_at", "updated_at"):
            val = result.get(field)
            if isinstance(val, datetime):
                result[field] = val.isoformat()
        return result
