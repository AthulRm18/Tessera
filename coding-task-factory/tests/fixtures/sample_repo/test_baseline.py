"""Existing test suite for the fixture repo — baseline tests.

These must all pass on the unmodified repo.  Gates use them to
detect regressions (G3) and confirm the baseline is green.
"""

import pytest
from calculator import add, subtract, multiply, divide
from cart import Cart


# ── calculator tests ───────────────────────────────────────────────────────

class TestAdd:
    def test_positive(self) -> None:
        assert add(2, 3) == 5

    def test_negative(self) -> None:
        assert add(-1, -1) == -2

    def test_zero(self) -> None:
        assert add(0, 0) == 0


class TestSubtract:
    def test_basic(self) -> None:
        assert subtract(10, 4) == 6

    def test_negative_result(self) -> None:
        assert subtract(3, 7) == -4


class TestMultiply:
    def test_basic(self) -> None:
        assert multiply(3, 4) == 12

    def test_by_zero(self) -> None:
        assert multiply(5, 0) == 0


class TestDivide:
    def test_basic(self) -> None:
        assert divide(10, 2) == 5.0

    def test_by_zero(self) -> None:
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(1, 0)


# ── cart tests ─────────────────────────────────────────────────────────────

class TestCart:
    def test_empty_cart(self) -> None:
        cart = Cart()
        assert cart.subtotal == 0
        assert cart.item_count == 0

    def test_add_item(self) -> None:
        cart = Cart()
        cart.add_item("Widget", 9.99, 2)
        assert cart.item_count == 2
        assert cart.subtotal == pytest.approx(19.98)

    def test_add_duplicate_item(self) -> None:
        cart = Cart()
        cart.add_item("Widget", 9.99, 1)
        cart.add_item("Widget", 9.99, 3)
        assert cart.item_count == 4
        assert len(cart.items) == 1  # merged into one entry

    def test_remove_item(self) -> None:
        cart = Cart()
        cart.add_item("Widget", 9.99)
        cart.remove_item("Widget")
        assert cart.item_count == 0

    def test_remove_missing_item(self) -> None:
        cart = Cart()
        with pytest.raises(KeyError, match="Item not found"):
            cart.remove_item("Ghost")

    def test_negative_price_rejected(self) -> None:
        cart = Cart()
        with pytest.raises(ValueError, match="Price cannot be negative"):
            cart.add_item("Bad", -1.0)

    def test_zero_quantity_rejected(self) -> None:
        cart = Cart()
        with pytest.raises(ValueError, match="Quantity must be at least 1"):
            cart.add_item("Bad", 5.0, 0)

    def test_clear(self) -> None:
        cart = Cart()
        cart.add_item("A", 1.0)
        cart.add_item("B", 2.0)
        cart.clear()
        assert cart.item_count == 0
        assert cart.subtotal == 0

    def test_multiple_items_subtotal(self) -> None:
        cart = Cart()
        cart.add_item("A", 10.0, 2)
        cart.add_item("B", 5.0, 3)
        assert cart.subtotal == pytest.approx(35.0)
