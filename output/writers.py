from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from models.producto import Product
from utils.change_detector import ChangeSet


CSV_COLUMNS = [
    "product_id", "name", "city", "store_code", "category", "subcategory", "categories", "url",
    "http_status", "final_url", "current_price", "regular_price", "sale_price", "price_text",
    "description", "short_description", "sku", "weight", "images", "status", "stock",
    "stock_quantity", "related_products", "tags", "variations", "attributes", "breadcrumbs",
    "scraped_at", "error", "extra",
]


def _flat(product: Product) -> dict[str, Any]:
    row = product.to_dict()
    for key in ("categories", "images", "related_products", "tags", "variations", "attributes", "breadcrumbs", "extra"):
        row[key] = json.dumps(row[key], ensure_ascii=False, sort_keys=True)
    return row


def write_catalogs(products: list[Product], output_dir: Path, metadata: dict[str, Any]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_flat(p) for p in products]
    frame = pd.DataFrame(rows, columns=CSV_COLUMNS)
    paths = {
        "completo": output_dir / "catalogo_completo.csv",
        "json": output_dir / "catalogo.json",
        "markdown": output_dir / "catalogo.md",
    }
    for city in sorted(frame["city"].dropna().unique()):
        key = city.casefold().replace(" ", "_")
        paths[key] = output_dir / f"catalogo_{key}.csv"
        frame[frame["city"] == city].to_csv(paths[key], index=False, encoding="utf-8-sig")
    frame.to_csv(paths["completo"], index=False, encoding="utf-8-sig")
    payload = {"metadata": metadata, "products": [p.to_dict() for p in products]}
    paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(products, paths["markdown"], metadata)
    return paths


def snapshot_version(output_dir: Path, run_id: str) -> Path:
    target = output_dir / "versiones" / run_id
    target.mkdir(parents=True, exist_ok=True)
    for source in output_dir.glob("catalogo*.*"):
        if source.is_file():
            shutil.copy2(source, target / source.name)
    return target


def archive_current(output_dir: Path) -> Path | None:
    current = output_dir / "catalogo.json"
    if not current.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = output_dir / "historico" / stamp
    target.mkdir(parents=True, exist_ok=True)
    for name in ("catalogo_quito.csv", "catalogo_guayaquil.csv", "catalogo_completo.csv", "catalogo.json", "catalogo.md"):
        source = output_dir / name
        if source.exists():
            shutil.copy2(source, target / name)
    return target


def load_previous(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / "catalogo.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("products", payload if isinstance(payload, list) else [])
    except (OSError, json.JSONDecodeError):
        return []


def write_change_report(changes: ChangeSet, report_dir: Path, run_at: str, output_dir: Path | None = None) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"cambios_{stamp}.md"
    lines = [
        "# Reporte de cambios del catálogo", "", f"- Ejecución: {run_at}",
        f"- Productos nuevos: {len(changes.new)}", f"- Productos eliminados: {len(changes.removed)}",
        f"- Productos modificados: {len(changes.modified)}", "",
    ]
    lines.extend(_change_section("Productos nuevos", changes.new))
    lines.extend(_change_section("Productos eliminados", changes.removed))
    lines.extend(["## Productos modificados", ""])
    if not changes.modified:
        lines.extend(["Sin cambios.", ""])
    for row in changes.modified:
        lines.extend([f"### [{row.get('name') or 'Sin nombre'}]({row.get('url')}) — {row.get('city')}", ""])
        for change in row["changes"]:
            lines.append(f"- {change['label']}: `{_brief(change['before'])}` → `{_brief(change['after'])}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    (report_dir / "ULTIMO_REPORTE_CAMBIOS.md").write_text("\n".join(lines), encoding="utf-8")
    if output_dir:
        (output_dir / "ULTIMO_REPORTE_CAMBIOS.md").write_text("\n".join(lines), encoding="utf-8")
    return path


def _change_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + ["Sin cambios.", ""]
    return lines + [f"- **{row.get('city')}** — [{row.get('name') or 'Sin nombre'}]({row.get('url')})" for row in rows] + [""]


def _brief(value: Any, limit: int = 180) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    text = " ".join(text.split()).replace("`", "'")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _write_markdown(products: list[Product], path: Path, metadata: dict[str, Any]) -> None:
    lines = [f"# Catálogo oficial {metadata.get('brand_name', 'Friovesa')}", "", f"Actualizado: {metadata.get('run_at', '')}", ""]
    for city in sorted({p.city for p in products}):
        city_products = [p for p in products if p.city == city]
        lines.extend([f"## {city} ({len(city_products)} productos)", ""])
        for product in city_products:
            lines.append(f"- [{product.name or 'Sin nombre'}]({product.url}) — {product.price_text or 'Precio no publicado'} — {product.category or 'Sin categoría'}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
