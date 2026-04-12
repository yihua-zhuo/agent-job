"""
示例模块 - 基础数学运算
"""


def add(a, b):
    """加法运算"""
    return a + b


def subtract(a, b):
    """减法运算"""
    return a - b


def multiply(a, b):
    """乘法运算"""
    return a * b


def divide(a, b):
    """除法运算"""
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b


def power(base, exponent):
    """幂运算"""
    return base ** exponent


def sqrt(value):
    """平方根"""
    if value < 0:
        raise ValueError("不能对负数求平方根")
    return value ** 0.5
