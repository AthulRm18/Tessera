"""A simple shopping cart for testing feature additions and regressions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CartItem:
    """A single item in the cart."""

    name: str
    price: float
    quantity: int = 1


class Cart:
    """A basic shopping cart that tracks items and computes totals."""

    def __init__(self) -> None:
        self._items: list[CartItem] = []

    def add_item(self, name: str, price: float, quantity: int = 1) -> None:
        """Add an item to the cart."""
        if price < 0:
            raise ValueError("Price cannot be negative")
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        # Check if item already exists; if so, increase quantity
        for item in self._items:
            if item.name == name and item.price == price:
                item.quantity += quantity
                return
        self._items.append(CartItem(name=name, price=price, quantity=quantity))

    def remove_item(self, name: str) -> None:
        """Remove all units of an item by name."""
        before = len(self._items)
        self._items = [i for i in self._items if i.name != name]
        if len(self._items) == before:
            raise KeyError(f"Item not found: {name}")

    @property
    def items(self) -> list[CartItem]:
        """Return a copy of the items list."""
        return list(self._items)

    @property
    def subtotal(self) -> float:
        """Sum of price * quantity for all items."""
        return sum(item.price * item.quantity for item in self._items)

    @property
    def item_count(self) -> int:
        """Total number of individual items (sum of quantities)."""
        return sum(item.quantity for item in self._items)

    def clear(self) -> None:
        """Remove all items from the cart."""
        self._items.clear()
