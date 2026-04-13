"""Customer service layer - handles customer business logic."""
from typing import Optional, List, Dict
from src.models.response import ApiResponse
from src.models.customer import Customer, CustomerStatus


class CustomerService:
    """Customer service with in-memory storage"""

    def __init__(self):
        self._customers: Dict[int, Customer] = {}
        self._next_id = 1

    def create_customer(self, data: dict, tenant_id: int = 0) -> ApiResponse:
        """Create a new customer"""
        if not data.get('name'):
            return ApiResponse.error(message="客户名称不能为空", code=3001)

        status_value = data.get('status', 'lead')
        if isinstance(status_value, str):
            try:
                status_value = CustomerStatus(status_value)
            except ValueError:
                status_value = CustomerStatus.LEAD

        customer = Customer(
            id=self._next_id,
            tenant_id=tenant_id,
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            company=data.get('company'),
            status=status_value,
            owner_id=data.get('owner_id', 0),
            tags=data.get('tags', []),
        )
        self._customers[self._next_id] = customer
        self._next_id += 1
        return ApiResponse.success(data=customer.to_dict(), message="客户创建成功")

    def list_customers(self, page=1, page_size=20, status=None, owner_id=None, tags=None, tenant_id: int = 0) -> ApiResponse:
        """List customers with pagination and filters"""
        filtered = list(self._customers.values())

        # Filter by tenant_id for isolation (tenant_id=0 means no filtering)
        if tenant_id != 0:
            filtered = [c for c in filtered if c.tenant_id == tenant_id]

        if status:
            filtered = [c for c in filtered if c.status == status]
        if owner_id:
            filtered = [c for c in filtered if c.owner_id == owner_id]
        if tags:
            filtered = [c for c in filtered if any(t in (c.tags or []) for t in tags)]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        items = [c.to_dict() for c in filtered[start:end]]

        return ApiResponse.paginated(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message=""
        )

    def get_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """Get customer by ID"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        return ApiResponse.success(data=customer.to_dict(), message="")

    def update_customer(self, customer_id: int, data: dict, tenant_id: int = 0) -> ApiResponse:
        """Update customer fields"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)

        for key in ['name', 'email', 'phone', 'company', 'status', 'owner_id', 'tags']:
            if key in data:
                if key == 'status':
                    status_val = data[key]
                    if isinstance(status_val, str):
                        try:
                            status_val = CustomerStatus(status_val)
                        except ValueError:
                            status_val = CustomerStatus.LEAD
                    setattr(customer, key, status_val)
                else:
                    setattr(customer, key, data[key])

        return ApiResponse.success(data=customer.to_dict(), message="客户更新成功")

    def delete_customer(self, customer_id: int, tenant_id: int = 0) -> ApiResponse:
        """Delete a customer"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        del self._customers[customer_id]
        return ApiResponse.success(message="客户删除成功")

    def search_customers(self, keyword: str, tenant_id: int = 0) -> ApiResponse:
        """Search customers by keyword (tenant-scoped)"""
        results = [
            c.to_dict() for c in self._customers.values()
            if (tenant_id == 0 or c.tenant_id == tenant_id)
            and (keyword.lower() in c.name.lower() or (c.email and keyword.lower() in c.email.lower()))
        ]
        return ApiResponse.success(data={"keyword": keyword, "items": results}, message="")

    def add_tag(self, customer_id: int, tag: str, tenant_id: int = 0) -> ApiResponse:
        """Add a tag to customer"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        if customer.tags is None:
            customer.tags = []
        if tag not in customer.tags:
            customer.tags.append(tag)
        return ApiResponse.success(data={"id": customer_id, "tag": tag}, message="标签添加成功")

    def remove_tag(self, customer_id: int, tag: str, tenant_id: int = 0) -> ApiResponse:
        """Remove a tag from customer"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        if customer.tags and tag in customer.tags:
            customer.tags.remove(tag)
        return ApiResponse.success(data={"id": customer_id, "tag": tag}, message="标签移除成功")

    def change_status(self, customer_id: int, status: str, tenant_id: int = 0) -> ApiResponse:
        """Change customer status"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        try:
            customer.status = CustomerStatus(status)
        except ValueError:
            customer.status = CustomerStatus.LEAD
        return ApiResponse.success(data={"id": customer_id, "status": customer.status.value}, message="状态更新成功")

    def assign_owner(self, customer_id: int, owner_id: int, tenant_id: int = 0) -> ApiResponse:
        """Assign owner to customer"""
        customer = self._customers.get(customer_id)
        if not customer:
            return ApiResponse.error(message="客户不存在", code=3001)
        # Verify tenant ownership
        if tenant_id and customer.tenant_id != tenant_id:
            return ApiResponse.error(message="客户不存在", code=3001)
        customer.owner_id = owner_id
        return ApiResponse.success(data={"id": customer_id, "owner_id": owner_id}, message="负责人分配成功")

    def bulk_import(self, customers: list, tenant_id: int = 0) -> ApiResponse:
        """Bulk import customers"""
        if not isinstance(customers, list):
            return ApiResponse.error(message="customers 必须是数组", code=1001)

        imported = 0
        errors = []
        for i, data in enumerate(customers):
            if not data.get('name'):
                errors.append({"index": i, "error": "客户名称不能为空"})
                continue
            customer = Customer(
                id=self._next_id,
                tenant_id=tenant_id,
                name=data['name'],
                email=data.get('email'),
                phone=data.get('phone'),
                company=data.get('company'),
                status='active',
                owner_id=data.get('owner_id', 0),
                tags=data.get('tags', []),
            )
            self._customers[self._next_id] = customer
            self._next_id += 1
            imported += 1

        return ApiResponse.success(
            data={"imported": imported, "errors": errors},
            message=f"成功导入{imported}条客户记录"
        )