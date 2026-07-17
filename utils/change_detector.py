from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.producto import Product
from utils.text import normalize_for_compare


TRACKED_FIELDS = {
    "name": "nombre",
    "url": "URL",
    "current_price": "precio",
    "regular_price": "precio regular",
    "sale_price": "precio oferta",
    "description": "descripción",
    "short_description": "descripción corta",
    "sku": "SKU",
    "category": "categoría",
    "subcategory": "subcategoría",
    "stock": "stock",
    "status": "estado",
    "variations": "variantes",
}


@dataclass
class ChangeSet:
    new: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    modified: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.new) + len(self.removed) + len(self.modified)


def detect_changes(previous: list[dict[str, Any]], current: list[Product]) -> ChangeSet:
    old_map = {_identity(row): row for row in previous}
    new_map = {product.identity: product.to_dict() for product in current}
    changes = ChangeSet()
    for identity in sorted(new_map.keys() - old_map.keys()):
        row = new_map[identity]
        changes.new.append({"identity": identity, "city": row.get("city"), "name": row.get("name"), "url": row.get("url")})
    for identity in sorted(old_map.keys() - new_map.keys()):
        row = old_map[identity]
        changes.removed.append({"identity": identity, "city": row.get("city"), "name": row.get("name"), "url": row.get("url")})
    for identity in sorted(new_map.keys() & old_map.keys()):
        before, after = old_map[identity], new_map[identity]
        fields = []
        for field, label in TRACKED_FIELDS.items():
            if normalize_for_compare(before.get(field)) != normalize_for_compare(after.get(field)):
                fields.append({"field": field, "label": label, "before": before.get(field), "after": after.get(field)})
        if fields:
            changes.modified.append({"identity": identity, "city": after.get("city"), "name": after.get("name"), "url": after.get("url"), "changes": fields})
    return changes


def _identity(row: dict[str, Any]) -> str:
    store = row.get("store_code", "")
    if row.get("product_id"):
        return f"{store}:id:{row['product_id']}"
    if row.get("sku"):
        return f"{store}:sku:{str(row['sku']).casefold()}"
    return f"{store}:url:{str(row.get('url', '')).rstrip('/').casefold()}"

