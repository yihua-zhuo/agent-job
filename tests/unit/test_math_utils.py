"""
math_utils 单元测试
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.math_utils import add, subtract, multiply, divide, power, sqrt


class TestBasicOperations:
    """基础运算测试"""
    
    def test_add(self):
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0
    
    def test_subtract(self):
        assert subtract(5, 3) == 2
        assert subtract(3, 5) == -2
        assert subtract(0, 0) == 0
    
    def test_multiply(self):
        assert multiply(2, 3) == 6
        assert multiply(-2, 3) == -6
        assert multiply(0, 100) == 0
    
    def test_divide(self):
        assert divide(6, 3) == 2
        assert divide(5, 2) == 2.5
        assert divide(0, 5) == 0
    
    def test_divide_by_zero(self):
        with pytest.raises(ValueError, match="除数不能为零"):
            divide(1, 0)


class TestAdvancedOperations:
    """高级运算测试"""
    
    def test_power(self):
        assert power(2, 3) == 8
        assert power(2, 0) == 1
        assert power(2, -1) == 0.5
    
    def test_sqrt(self):
        assert sqrt(4) == 2
        assert sqrt(9) == 3
        assert sqrt(0) == 0
    
    def test_sqrt_negative(self):
        with pytest.raises(ValueError, match="不能对负数求平方根"):
            sqrt(-1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
