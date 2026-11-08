"""Shared value objects for the DAO contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class OrderItemInput:
    product_id: str
    quantity: int
