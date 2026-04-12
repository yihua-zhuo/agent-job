"""
CRM 数据导入导出服务
"""
import csv
import json
import openpyxl
from io import BytesIO, StringIO
from typing import List, Dict, Optional
from datetime import datetime
from src.utils.file_helper import FileHelper


class ImportExportService:
    """数据导入导出服务"""

    # 支持的格式
    FORMAT_CSV = "csv"
    FORMAT_EXCEL = "excel"
    FORMAT_JSON = "json"
    FORMAT_PDF = "pdf"

    def __init__(self):
        self.file_helper = FileHelper()
        # 必填字段配置
        self.required_fields = {
            "customer": ["name", "email", "phone"],
            "opportunity": ["name", "customer_id", "amount"],
            "lead": ["name", "email", "source"]
        }
        # 字段格式验证规则
        self.validation_rules = {
            "email": lambda x: self._is_valid_email(x),
            "phone": lambda x: self._is_valid_phone(x),
            "amount": lambda x: self._is_valid_number(x)
        }

    def _is_valid_email(self, email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, str(email)))

    def _is_valid_phone(self, phone: str) -> bool:
        """验证手机号格式"""
        import re
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, str(phone)))

    def _is_valid_number(self, value) -> bool:
        """验证数值格式"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def import_customers(self, file_data: bytes, file_format: str) -> Dict:
        """导入客户数据
        返回: {success_count, error_count, errors[]}
        """
        try:
            # 根据格式读取数据
            if file_format == self.FORMAT_CSV:
                data = self.file_helper.read_csv(file_data)
            elif file_format == self.FORMAT_EXCEL:
                data = self.file_helper.read_excel(file_data)
            elif file_format == self.FORMAT_JSON:
                data = json.loads(file_data.decode('utf-8'))
                if isinstance(data, dict):
                    data = data.get('customers', data.get('data', [data]))
            else:
                return {
                    "success_count": 0,
                    "error_count": 1,
                    "errors": [f"不支持的文件格式: {file_format}"]
                }

            # 验证数据
            validation_result = self.validate_import_data(data, "customer")
            if validation_result["errors"]:
                return {
                    "success_count": 0,
                    "error_count": len(data),
                    "errors": validation_result["errors"]
                }

            # TODO: 调用数据库服务保存客户数据
            # 这里假设所有验证通过的数据都可以成功导入
            success_count = len(data)
            
            return {
                "success_count": success_count,
                "error_count": 0,
                "errors": [],
                "data": data
            }

        except Exception as e:
            return {
                "success_count": 0,
                "error_count": 1,
                "errors": [f"导入客户数据失败: {str(e)}"]
            }

    def import_opportunities(self, file_data: bytes, file_format: str) -> Dict:
        """导入商机数据"""
        try:
            if file_format == self.FORMAT_CSV:
                data = self.file_helper.read_csv(file_data)
            elif file_format == self.FORMAT_EXCEL:
                data = self.file_helper.read_excel(file_data)
            elif file_format == self.FORMAT_JSON:
                data = json.loads(file_data.decode('utf-8'))
                if isinstance(data, dict):
                    data = data.get('opportunities', data.get('data', [data]))
            else:
                return {
                    "success_count": 0,
                    "error_count": 1,
                    "errors": [f"不支持的文件格式: {file_format}"]
                }

            validation_result = self.validate_import_data(data, "opportunity")
            if validation_result["errors"]:
                return {
                    "success_count": 0,
                    "error_count": len(data),
                    "errors": validation_result["errors"]
                }

            success_count = len(data)
            
            return {
                "success_count": success_count,
                "error_count": 0,
                "errors": [],
                "data": data
            }

        except Exception as e:
            return {
                "success_count": 0,
                "error_count": 1,
                "errors": [f"导入商机数据失败: {str(e)}"]
            }

    def import_leads(self, file_data: bytes, file_format: str) -> Dict:
        """导入线索数据"""
        try:
            if file_format == self.FORMAT_CSV:
                data = self.file_helper.read_csv(file_data)
            elif file_format == self.FORMAT_EXCEL:
                data = self.file_helper.read_excel(file_data)
            elif file_format == self.FORMAT_JSON:
                data = json.loads(file_data.decode('utf-8'))
                if isinstance(data, dict):
                    data = data.get('leads', data.get('data', [data]))
            else:
                return {
                    "success_count": 0,
                    "error_count": 1,
                    "errors": [f"不支持的文件格式: {file_format}"]
                }

            validation_result = self.validate_import_data(data, "lead")
            if validation_result["errors"]:
                return {
                    "success_count": 0,
                    "error_count": len(data),
                    "errors": validation_result["errors"]
                }

            success_count = len(data)
            
            return {
                "success_count": success_count,
                "error_count": 0,
                "errors": [],
                "data": data
            }

        except Exception as e:
            return {
                "success_count": 0,
                "error_count": 1,
                "errors": [f"导入线索数据失败: {str(e)}"]
            }

    def export_customers(self, filters: Dict, file_format: str) -> bytes:
        """导出客户数据"""
        # TODO: 从数据库获取客户数据，应用filters
        # 模拟数据
        sample_data = [
            {"id": 1, "name": "张三", "email": "zhangsan@example.com", "phone": "13800138000", "company": "公司A", "status": "活跃"},
            {"id": 2, "name": "李四", "email": "lisi@example.com", "phone": "13900139000", "company": "公司B", "status": "活跃"},
        ]
        
        return self._export_data(sample_data, filters, file_format)

    def export_opportunities(self, filters: Dict, file_format: str) -> bytes:
        """导出商机数据"""
        # TODO: 从数据库获取商机数据
        sample_data = [
            {"id": 1, "name": "项目A", "customer_id": 1, "amount": 100000, "stage": "提案", "probability": 50},
            {"id": 2, "name": "项目B", "customer_id": 2, "amount": 200000, "stage": "谈判", "probability": 75},
        ]
        
        return self._export_data(sample_data, filters, file_format)

    def export_report(self, report_type: str, date_range: Dict, file_format: str) -> bytes:
        """导出报表"""
        # TODO: 根据report_type和date_range生成报表数据
        sample_report = {
            "report_type": report_type,
            "date_range": date_range,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_customers": 100,
                "total_revenue": 5000000,
                "conversion_rate": 0.25
            },
            "details": [
                {"month": "2024-01", "revenue": 400000, "customers": 10},
                {"month": "2024-02", "revenue": 450000, "customers": 12},
            ]
        }
        
        if file_format == self.FORMAT_JSON:
            return json.dumps(sample_report, ensure_ascii=False, indent=2).encode('utf-8')
        elif file_format == self.FORMAT_PDF:
            return self.generate_pdf_report(sample_report, f"{report_type}报表")
        else:
            # CSV 或 Excel 格式
            return self._export_data(sample_report.get("details", []), {}, file_format)

    def generate_pdf_report(self, report_data: Dict, title: str) -> bytes:
        """生成PDF报表"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
        except ImportError:
            # 如果没有 reportlab，返回文本格式的PDF
            return self._generate_simple_pdf(report_data, title)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # 标题
        elements.append(Paragraph(title, styles['Title']))
        elements.append(Spacer(1, 0.3 * inch))
        
        # 生成时间
        if 'generated_at' in report_data:
            elements.append(Paragraph(f"生成时间: {report_data['generated_at']}", styles['Normal']))
            elements.append(Spacer(1, 0.2 * inch))
        
        # 摘要信息
        if 'summary' in report_data:
            elements.append(Paragraph("摘要", styles['Heading2']))
            for key, value in report_data['summary'].items():
                elements.append(Paragraph(f"{key}: {value}", styles['Normal']))
            elements.append(Spacer(1, 0.3 * inch))
        
        # 详细信息表格
        if 'details' in report_data and report_data['details']:
            elements.append(Paragraph("详细数据", styles['Heading2']))
            headers = list(report_data['details'][0].keys())
            table_data = [headers]
            for row in report_data['details']:
                table_data.append([str(row.get(h, '')) for h in headers])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def _generate_simple_pdf(self, report_data: Dict, title: str) -> bytes:
        """生成简单的文本PDF（不依赖reportlab）"""
        content = f"{title}\n"
        content += "=" * 50 + "\n\n"
        
        if 'generated_at' in report_data:
            content += f"生成时间: {report_data['generated_at']}\n\n"
        
        if 'summary' in report_data:
            content += "摘要:\n"
            for key, value in report_data['summary'].items():
                content += f"  {key}: {value}\n"
            content += "\n"
        
        if 'details' in report_data:
            content += "详细数据:\n"
            for row in report_data['details']:
                content += f"  {row}\n"
        
        # 返回一个简单的PDF格式（实际上是文本）
        # 实际生产环境应使用专业的PDF生成库
        return content.encode('utf-8')

    def validate_import_data(self, data: List[Dict], entity_type: str) -> Dict:
        """验证导入数据
        检查: 必填字段、格式、重复
        """
        errors = []
        required = self.required_fields.get(entity_type, [])
        
        if not data:
            return {"errors": ["数据为空"]}
        
        # 检查必填字段
        for idx, row in enumerate(data):
            row_num = idx + 2  # Excel行号（1是表头）
            
            for field in required:
                if field not in row or not row[field]:
                    errors.append(f"第{row_num}行: 缺少必填字段 '{field}'")
                elif field in self.validation_rules:
                    if not self.validation_rules[field](row[field]):
                        errors.append(f"第{row_num}行: 字段 '{field}' 格式不正确")
        
        # 检查重复（基于邮箱或电话）
        seen = set()
        for idx, row in enumerate(data):
            identifier = row.get('email') or row.get('phone')
            if identifier:
                if identifier in seen:
                    errors.append(f"第{idx + 2}行: 数据重复 (email/phone: {identifier})")
                seen.add(identifier)
        
        return {"errors": errors}

    def _export_data(self, data: List[Dict], filters: Dict, file_format: str) -> bytes:
        """内部方法：导出数据"""
        # 应用过滤条件
        if filters:
            filtered_data = []
            for row in data:
                match = True
                for key, value in filters.items():
                    if key in row and str(row[key]) != str(value):
                        match = False
                        break
                if match:
                    filtered_data.append(row)
            data = filtered_data
        
        if file_format == self.FORMAT_CSV:
            if data:
                columns = list(data[0].keys())
                return self.file_helper.write_csv(data, columns)
            return b""
        elif file_format == self.FORMAT_EXCEL:
            if data:
                return self.file_helper.write_excel(data, "Data")
            return b""
        elif file_format == self.FORMAT_JSON:
            return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        elif file_format == self.FORMAT_PDF:
            return self.generate_pdf_report({"details": data}, "导出数据")
        else:
            raise ValueError(f"不支持的导出格式: {file_format}")
