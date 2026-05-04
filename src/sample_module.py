"""
Sample module for development agent system testing
"""

def add(a: int, b: int) -> int:
    """Add two integers"""
    return a + b

def subtract(a: int, b: int) -> int:
    """Subtract two integers"""
    return a - b

def multiply(a: int, b: int) -> int:
    """Multiply two integers"""
    return a * b

def divide(a: int, b: int) -> float:
    """Divide two integers"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def greet(name: str) -> str:
    """Generate a greeting message"""
    return f"Hello, {name}!"

def process_data(data: list) -> dict:
    """Process a list of numbers and return statistics"""
    if not data:
        return {"count": 0, "sum": 0, "average": 0}

    return {
        "count": len(data),
        "sum": sum(data),
        "average": sum(data) / len(data)
    }
