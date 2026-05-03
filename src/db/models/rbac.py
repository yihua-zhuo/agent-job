"""RBAC ORM models — roles, permissions, user role assignments."""
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class RoleModel(Base):
    """Role entity mapped to the `roles` table."""

    __tablename__ = "roles"
    __table_args__ = (
        Index("ix_roles_tenant_name", "tenant_id", "name", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=0)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    permissions: Mapped[List["RolePermissionModel"]] = relationship(
        "RolePermissionModel", back_populates="role", cascade="all, delete-orphan"
    )
    user_assignments: Mapped[List["UserRoleModel"]] = relationship(
        "UserRoleModel", back_populates="role", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "is_system": self.is_system,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PermissionModel(Base):
    """Permission entity mapped to the `permissions` table."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    roles: Mapped[List["RolePermissionModel"]] = relationship(
        "RolePermissionModel", back_populates="permission", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RolePermissionModel(Base):
    """Junction table: role ↔ permission (many-to-many)."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    role: Mapped["RoleModel"] = relationship("RoleModel", back_populates="permissions")
    permission: Mapped["PermissionModel"] = relationship("PermissionModel", back_populates="roles")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role_id": self.role_id,
            "permission_id": self.permission_id,
        }


class UserRoleModel(Base):
    """Assignment of a role to a user (tenant-scoped)."""

    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ix_user_roles_user_tenant_role", "user_id", "tenant_id", "role_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=0)
    granted_by: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    role: Mapped["RoleModel"] = relationship("RoleModel", back_populates="user_assignments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "tenant_id": self.tenant_id,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
        }
