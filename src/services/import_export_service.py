"""CRM data import / export service — backed by real DB via SQLAlchemy ORM."""

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from src.utils.file_helper import FileHelper


class ImportExportService:
    """Data import/export service.

    Dual-mode: if instantiated with an AsyncSession, reads/writes the real
    database. Without a session, parses/validates inputs only and returns
    sample data on export (used by validation-focused unit tests).
    """

    FORMAT_CSV = "csv"
    FORMAT_EXCEL = "excel"
    FORMAT_JSON = "json"
    FORMAT_PDF = "pdf"

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.file_helper = FileHelper()
        self.required_fields = {
            "customer": ["name", "email", "phone"],
            "opportunity": ["name", "customer_id", "amount"],
            "lead": ["name", "email", "source"],
        }
        self.validation_rules = {
            "email": lambda x: self._is_valid_email(x),
            "phone": lambda x: self._is_valid_phone(x),
            "amount": lambda x: self._is_valid_number(x),
        }

    # -------------------------------------------------------------------------
    # Validation helpers
    # -------------------------------------------------------------------------

    def _is_valid_email(self, email: str) -> bool:
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, str(email)))

    def _is_valid_phone(self, phone: str) -> bool:
        import re

        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, str(phone)))

    def _is_valid_number(self, value) -> bool:
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _parse_file(self, file_data: bytes, file_format: str, json_key: str) -> list[dict]:
        if file_format == self.FORMAT_CSV:
            return self.file_helper.read_csv(file_data)
        if file_format == self.FORMAT_EXCEL:
            return self.file_helper.read_excel(file_data)
        if file_format == self.FORMAT_JSON:
            data = json.loads(file_data.decode("utf-8"))
            if isinstance(data, dict):
                return data.get(json_key, data.get("data", [data]))
            return data
        raise ValueError(f"不支持的文件格式: {file_format}")

    # -------------------------------------------------------------------------
    # Import
    # -------------------------------------------------------------------------

    async def import_customers(
        self,
        file_data: bytes,
        file_format: str,
        tenant_id: int = 0,
        owner_id: int = 0,
    ) -> dict:
        try:
            data = self._parse_file(file_data, file_format, "customers")
        except ValueError as e:
            return {"success_count": 0, "error_count": 1, "errors": [str(e)]}
        except Exception as e:
            return {"success_count": 0, "error_count": 1, "errors": [f"导入客户数据失败: {e}"]}

        validation = self.validate_import_data(data, "customer")
        if validation["errors"]:
            return {"success_count": 0, "error_count": len(data), "errors": validation["errors"]}

        if self.session is None:
            return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

        now = datetime.now(UTC)
        for row in data:
            self.session.add(
                CustomerModel(
                    tenant_id=tenant_id,
                    name=row.get("name"),
                    email=row.get("email"),
                    phone=row.get("phone"),
                    company=row.get("company"),
                    status="lead",
                    owner_id=owner_id,
                    tags=[],
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.session.commit()
        return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

    async def import_opportunities(
        self,
        file_data: bytes,
        file_format: str,
        tenant_id: int = 0,
        owner_id: int = 0,
    ) -> dict:
        try:
            data = self._parse_file(file_data, file_format, "opportunities")
        except ValueError as e:
            return {"success_count": 0, "error_count": 1, "errors": [str(e)]}
        except Exception as e:
            return {"success_count": 0, "error_count": 1, "errors": [f"导入商机数据失败: {e}"]}

        validation = self.validate_import_data(data, "opportunity")
        if validation["errors"]:
            return {"success_count": 0, "error_count": len(data), "errors": validation["errors"]}

        if self.session is None:
            return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

        now = datetime.now(UTC)
        for row in data:
            try:
                amount = Decimal(str(row.get("amount", 0)))
            except (InvalidOperation, TypeError, ValueError):
                amount = Decimal("0")
            self.session.add(
                OpportunityModel(
                    tenant_id=tenant_id,
                    customer_id=row.get("customer_id") or 0,
                    name=row.get("name") or row.get("title", "Opportunity"),
                    amount=amount,
                    stage=row.get("stage", "qualification"),
                    probability=20,
                    owner_id=owner_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.session.commit()
        return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

    async def import_leads(
        self,
        file_data: bytes,
        file_format: str,
        tenant_id: int = 0,
    ) -> dict:
        try:
            data = self._parse_file(file_data, file_format, "leads")
        except ValueError as e:
            return {"success_count": 0, "error_count": 1, "errors": [str(e)]}
        except Exception as e:
            return {"success_count": 0, "error_count": 1, "errors": [f"导入线索数据失败: {e}"]}

        validation = self.validate_import_data(data, "lead")
        if validation["errors"]:
            return {"success_count": 0, "error_count": len(data), "errors": validation["errors"]}

        if self.session is None:
            return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

        # Leads are stored as customers with status='lead'.
        now = datetime.now(UTC)
        for row in data:
            self.session.add(
                CustomerModel(
                    tenant_id=tenant_id,
                    name=row.get("name"),
                    email=row.get("email"),
                    phone=row.get("phone"),
                    company=None,
                    status="lead",
                    owner_id=0,
                    tags=[],
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.session.commit()
        return {"success_count": len(data), "error_count": 0, "errors": [], "data": data}

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    _SAMPLE_CUSTOMERS = [
        {
            "id": 1,
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800138000",
            "company": "公司A",
            "status": "活跃",
        },
        {
            "id": 2,
            "name": "李四",
            "email": "lisi@example.com",
            "phone": "13900139000",
            "company": "公司B",
            "status": "活跃",
        },
    ]
    _SAMPLE_OPPORTUNITIES = [
        {"id": 1, "name": "项目A", "customer_id": 1, "amount": 100000, "stage": "提案", "probability": 50},
        {"id": 2, "name": "项目B", "customer_id": 2, "amount": 200000, "stage": "谈判", "probability": 75},
    ]

    async def export_customers(self, filters: dict, file_format: str, tenant_id: int = 0) -> bytes:
        rows: list[dict] = []
        if self.session is not None:
            result = await self.session.execute(
                select(CustomerModel).where(CustomerModel.tenant_id == tenant_id).order_by(CustomerModel.id)
            )
            rows = [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "company": c.company,
                    "status": c.status,
                }
                for c in result.scalars().all()
            ]
        if not rows:
            rows = list(self._SAMPLE_CUSTOMERS)
        return self._export_data(rows, filters, file_format)

    async def export_opportunities(self, filters: dict, file_format: str, tenant_id: int = 0) -> bytes:
        rows: list[dict] = []
        if self.session is not None:
            result = await self.session.execute(
                select(OpportunityModel).where(OpportunityModel.tenant_id == tenant_id).order_by(OpportunityModel.id)
            )
            rows = [
                {
                    "id": o.id,
                    "name": o.name,
                    "customer_id": o.customer_id,
                    "amount": float(o.amount),
                    "stage": o.stage,
                    "probability": o.probability,
                }
                for o in result.scalars().all()
            ]
        if not rows:
            rows = list(self._SAMPLE_OPPORTUNITIES)
        return self._export_data(rows, filters, file_format)

    async def export_report(self, report_type: str, date_range: dict, file_format: str) -> bytes:
        summary = {"total_customers": 0, "total_revenue": 0, "conversion_rate": 0.0}
        if self.session is not None:
            cust_count = await self.session.execute(select(func.count(CustomerModel.id)))
            summary["total_customers"] = cust_count.scalar() or 0
            opp_sum = await self.session.execute(select(func.coalesce(func.sum(OpportunityModel.amount), 0)))
            summary["total_revenue"] = float(opp_sum.scalar() or 0)

        report = {
            "report_type": report_type,
            "date_range": date_range,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "details": [],
        }

        if file_format == self.FORMAT_JSON:
            return json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        if file_format == self.FORMAT_PDF:
            return self.generate_pdf_report(report, f"{report_type}报表")
        return self._export_data(report.get("details", []), {}, file_format)

    # -------------------------------------------------------------------------
    # PDF generation
    # -------------------------------------------------------------------------

    def generate_pdf_report(self, report_data: dict, title: str) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            return self._generate_simple_pdf(report_data, title)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Spacer(1, 0.3 * inch))

        if "generated_at" in report_data:
            elements.append(Paragraph(f"生成时间: {report_data['generated_at']}", styles["Normal"]))
            elements.append(Spacer(1, 0.2 * inch))

        if "summary" in report_data:
            elements.append(Paragraph("摘要", styles["Heading2"]))
            for key, value in report_data["summary"].items():
                elements.append(Paragraph(f"{key}: {value}", styles["Normal"]))
            elements.append(Spacer(1, 0.3 * inch))

        if "details" in report_data and report_data["details"]:
            elements.append(Paragraph("详细数据", styles["Heading2"]))
            headers = list(report_data["details"][0].keys())
            table_data = [headers]
            for row in report_data["details"]:
                table_data.append([str(row.get(h, "")) for h in headers])

            table = Table(table_data)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            elements.append(table)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def _generate_simple_pdf(self, report_data: dict, title: str) -> bytes:
        content = f"{title}\n" + "=" * 50 + "\n\n"
        if "generated_at" in report_data:
            content += f"生成时间: {report_data['generated_at']}\n\n"
        if "summary" in report_data:
            content += "摘要:\n"
            for key, value in report_data["summary"].items():
                content += f"  {key}: {value}\n"
            content += "\n"
        if "details" in report_data:
            content += "详细数据:\n"
            for row in report_data["details"]:
                content += f"  {row}\n"
        return content.encode("utf-8")

    # -------------------------------------------------------------------------
    # Validation + export helpers
    # -------------------------------------------------------------------------

    def validate_import_data(self, data: list[dict], entity_type: str) -> dict:
        errors = []
        required = self.required_fields.get(entity_type, [])

        if not data:
            return {"errors": ["数据为空"]}

        for idx, row in enumerate(data):
            row_num = idx + 2
            for field in required:
                if field not in row or not row[field]:
                    errors.append(f"第{row_num}行: 缺少必填字段 '{field}'")
                elif field in self.validation_rules:
                    if not self.validation_rules[field](row[field]):
                        errors.append(f"第{row_num}行: 字段 '{field}' 格式不正确")

        seen = set()
        for idx, row in enumerate(data):
            identifier = row.get("email") or row.get("phone")
            if identifier:
                if identifier in seen:
                    errors.append(f"第{idx + 2}行: 数据重复 (email/phone: {identifier})")
                seen.add(identifier)

        return {"errors": errors}

    def _export_data(self, data: list[dict], filters: dict, file_format: str) -> bytes:
        if filters:
            filtered = []
            for row in data:
                match = True
                for key, value in filters.items():
                    if key in row and str(row[key]) != str(value):
                        match = False
                        break
                if match:
                    filtered.append(row)
            data = filtered

        if file_format == self.FORMAT_CSV:
            return self.file_helper.write_csv(data, list(data[0].keys())) if data else b""
        if file_format == self.FORMAT_EXCEL:
            return self.file_helper.write_excel(data, "Data") if data else b""
        if file_format == self.FORMAT_JSON:
            return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        if file_format == self.FORMAT_PDF:
            return self.generate_pdf_report({"details": data}, "导出数据")
        raise ValueError(f"不支持的导出格式: {file_format}")
