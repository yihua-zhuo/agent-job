"""
通用工具函数
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def generate_id(*parts: str) -> str:
    """生成唯一ID"""
    combined = "_".join(str(p) for p in parts)
    # Truncated to 16 hex chars (64-bit space) for use as a short display ID.
    # Birthday paradox: 50% collision at ~2.7B IDs; negligible at <1M.
    # Acceptable for internal, non-URL/non-log use.
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不安全字符"""
    filename = Path(filename).name
    filename = re.sub(r"[^\w\s.-]", "", filename)
    filename = re.sub(r"[-\s]+", "-", filename)
    return filename.strip("- .")


def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def parse_datetime(date_string: str) -> datetime | None:
    """解析日期时间字符串"""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    return None


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间"""
    if dt is None:
        return ""
    return dt.strftime(format_str)


def get_date_range(days: int = 30) -> tuple:
    """获取日期范围"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def calculate_age(birth_date: datetime) -> int:
    """计算年龄"""
    today = datetime.now()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age


def is_valid_phone(phone: str) -> bool:
    """验证手机号"""
    pattern = r"^1[3-9]\d{9}$"
    return bool(re.match(pattern, phone))


def is_valid_url(url: str) -> bool:
    """验证URL"""
    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(pattern, url))


def is_valid_ip(ip: str) -> bool:
    """验证IP地址"""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    parts = ip.split(".")
    return all(0 <= int(part) <= 255 for part in parts)


def deep_get(dictionary: dict, *keys, default=None) -> Any:
    """安全获取嵌套字典值"""
    result = dictionary
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        elif isinstance(result, list) and isinstance(key, int):
            result = result[key] if key < len(result) else None
        else:
            return default
        if result is None:
            return default
    return result if result is not None else default


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """扁平化嵌套字典"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}[{i}]", sep=sep).items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """将列表分块"""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def remove_duplicates(items: list, key=None) -> list:
    """移除列表重复项"""
    if key is None:
        return list(dict.fromkeys(items))
    seen = set()
    result = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def safe_json_loads(json_string: str, default=None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default=str, **kwargs) -> str:
    """安全的JSON序列化"""
    return json.dumps(obj, default=default, **kwargs)


class Pagination:
    """分页工具类"""

    def __init__(self, items: list, page: int = 1, page_size: int = 20):
        self.items = items
        self.page = page
        self.page_size = page_size
        self.total = len(items)
        self.total_pages = (self.total + page_size - 1) // page_size

    @property
    def start_index(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def end_index(self) -> int:
        return min(self.start_index + self.page_size, self.total)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def get_page_items(self) -> list:
        return self.items[self.start_index : self.end_index]

    def to_dict(self) -> dict:
        return {
            "items": self.get_page_items(),
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }
