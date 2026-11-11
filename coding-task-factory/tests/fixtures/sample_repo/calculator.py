"""A tiny calculator module used as a fixture repo for gate testing.

This is intentionally small: add, subtract, multiply, divide, plus
a simple cart with totals.  The existing test suite covers current
behaviour so gates can detect regressions and fail-to-pass.
"""


def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of two numbers."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient; raises ValueError on division by zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
