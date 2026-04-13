"""
Unit tests for sample_module
"""

import pytest
from sample_module import add, subtract, multiply, divide, greet, process_data

class TestMathOperations:
    def test_add(self):
        assert add(2, 3) == 5
        assert add(-1, 1) == 0
        assert add(0, 0) == 0

    def test_subtract(self):
        assert subtract(5, 3) == 2
        assert subtract(1, 1) == 0
        assert subtract(-1, -1) == 0

    def test_multiply(self):
        assert multiply(2, 3) == 6
        assert multiply(0, 100) == 0
        assert multiply(-2, 3) == -6

    def test_divide(self):
        assert divide(10, 2) == 5.0
        assert divide(9, 3) == 3.0
        assert divide(5, 2) == 2.5

    def test_divide_by_zero(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(1, 0)

class TestStringOperations:
    def test_greet(self):
        assert greet("World") == "Hello, World!"
        assert greet("OpenClaw") == "Hello, OpenClaw!"

class TestDataProcessing:
    def test_process_data(self):
        result = process_data([1, 2, 3, 4, 5])
        assert result["count"] == 5
        assert result["sum"] == 15
        assert result["average"] == 3.0

    def test_process_empty_data(self):
        result = process_data([])
        assert result["count"] == 0
        assert result["sum"] == 0
        assert result["average"] == 0