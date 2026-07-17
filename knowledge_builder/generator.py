from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from models.producto import Product
from utils.text import clean_text, slugify, unique


class KnowledgeGenerator:
    """Proyecto 2: transforma exclusivamente la salida del crawler en documentos para IA."""

    def __init__(self, directory: Path, brand_name: str = "Friovesa", base_url: str = "https://friovesa.com/"):
        self.directory = directory
        self.brand_name = brand_name
        self.base_url = base_url

    def generate(self, products: list[Product], site_documents: dict[str, str] | None = None) -> None:
        site_documents = site_documents or {}
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._write_instructions()
        self._write_site_document("01_empresa.md", "Empresa", site_documents.get("empresa", ""))
        self._write_site_document("02_politicas.md", "Políticas", site_documents.get("politicas", ""))
        self._write_site_document("03_faq.md", "Preguntas frecuentes", site_documents.get("faq", ""))
        grouped: dict[tuple[str, str], list[Product]] = defaultdict(list)
        for product in products:
            grouped[(product.store_code, product.category or "Sin categoría")].append(product)
        for (store_code, category), rows in sorted(grouped.items()):
            city_dir = self.directory / slugify(rows[0].city if rows else store_code)
            city_dir.mkdir(parents=True, exist_ok=True)
            self._write_category(city_dir / f"{slugify(category)}.md", category, rows)
        self._write_index(products)

    def _write_instructions(self) -> None:
        text = f"""# Instrucciones de uso

Esta base de {self.brand_name} se genera automáticamente desde `{self.base_url}`. No editar manualmente.

- La web es la única fuente oficial de productos, precios, disponibilidad y descripciones.
- Responder siempre con la ciudad o tienda correspondiente; no mezclar inventarios.
- Si un campo está vacío, indicar que no está publicado en la web. No inferir ni inventar.
- Citar el enlace del producto y recomendar verificar precio y disponibilidad antes de comprar.
- Regenerar ejecutando `python actualizar_catalogo.py`.
"""
        (self.directory / "00_instrucciones.md").write_text(text, encoding="utf-8")

    def _write_site_document(self, name: str, title: str, content: str) -> None:
        body = clean_text(content)
        if not body:
            body = "No se encontró contenido público específico para esta sección durante la última ejecución."
        (self.directory / name).write_text(f"# {title}\n\n{body}\n", encoding="utf-8")

    def _write_category(self, path: Path, category: str, products: Iterable[Product]) -> None:
        rows = sorted(products, key=lambda p: (p.subcategory.casefold(), p.name.casefold()))
        lines = [f"# {category}", "", "## Índice", ""]
        for p in rows:
            lines.append(f"- [{p.name or 'Sin nombre'}](#{slugify(p.name)})")
        lines.append("")
        for p in rows:
            keywords = unique([p.name, p.category, p.subcategory, *p.tags, *p.attributes.values()])
            related = ", ".join(f"[{r.get('name')}]({r.get('url')})" for r in p.related_products) or "No publicados"
            lines.extend([
                f"## {p.name or 'Sin nombre'}", "",
                f"- **Descripción:** {p.description or p.short_description or 'No publicada'}",
                f"- **Precio:** {p.price_text or ('USD ' + format(p.current_price, '.2f') if p.current_price is not None else 'No publicado')}",
                f"- **Enlace:** {p.url}", f"- **Peso:** {p.weight or 'No publicado'}",
                f"- **SKU:** {p.sku or 'No publicado'}", f"- **Palabras clave:** {', '.join(keywords)}",
                f"- **Categoría:** {p.category or 'No publicada'}", f"- **Subcategoría:** {p.subcategory or 'No publicada'}",
                f"- **Productos relacionados:** {related}", f"- **Estado:** {p.status or 'No publicado'}",
                f"- **Stock:** {p.stock or 'No publicado'}", "",
            ])
            if p.variations:
                lines.extend(["### Variantes", ""])
                for variation in p.variations:
                    attrs = ", ".join(f"{k}: {v}" for k, v in variation.attributes.items()) or "Sin atributos"
                    price = f"USD {variation.price:.2f}" if variation.price is not None else "No publicado"
                    lines.append(f"- {attrs} — {price} — SKU: {variation.sku or 'No publicado'} — Stock: {variation.stock_quantity if variation.stock_quantity is not None else 'No publicado'}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_index(self, products: list[Product]) -> None:
        lines = ["# Índice general", "", "| Ciudad | Categoría | Subcategoría | Producto | Enlace |", "|---|---|---|---|---|"]
        for p in sorted(products, key=lambda x: (x.city, x.category, x.subcategory, x.name)):
            safe = lambda value: clean_text(value).replace("|", "\\|")
            lines.append(f"| {safe(p.city)} | {safe(p.category)} | {safe(p.subcategory)} | {safe(p.name)} | [Abrir]({p.url}) |")
        (self.directory / "INDICE_GENERAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
