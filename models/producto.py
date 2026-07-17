from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Variation:
    variation_id: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    price: float | None = None
    regular_price: float | None = None
    sale_price: float | None = None
    sku: str = ""
    weight: str = ""
    in_stock: bool | None = None
    stock_quantity: int | float | None = None
    image: str = ""
    description: str = ""


@dataclass
class Product:
    product_id: str = ""
    name: str = ""
    city: str = ""
    store_code: str = ""
    category: str = ""
    subcategory: str = ""
    categories: list[str] = field(default_factory=list)
    url: str = ""
    http_status: int | None = None
    final_url: str = ""
    current_price: float | None = None
    regular_price: float | None = None
    sale_price: float | None = None
    price_text: str = ""
    description: str = ""
    short_description: str = ""
    sku: str = ""
    weight: str = ""
    images: list[str] = field(default_factory=list)
    status: str = ""
    stock: str = ""
    stock_quantity: int | float | None = None
    related_products: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    variations: list[Variation] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    breadcrumbs: list[str] = field(default_factory=list)
    scraped_at: str = ""
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        if self.product_id:
            return f"{self.store_code}:id:{self.product_id}"
        if self.sku:
            return f"{self.store_code}:sku:{self.sku.casefold()}"
        return f"{self.store_code}:url:{self.url.rstrip('/').casefold()}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Product":
        allowed = cls.__dataclass_fields__.keys()
        values = {key: value for key, value in row.items() if key in allowed}
        values["variations"] = [v if isinstance(v, Variation) else Variation(**v) for v in values.get("variations", [])]
        return cls(**values)
