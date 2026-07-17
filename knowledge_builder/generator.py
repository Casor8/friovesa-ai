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
        self._write_whatsapp_files(products, site_documents)

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

    def _write_whatsapp_files(self, products: list[Product], site_documents: dict[str, str]) -> None:
        """Genera archivos TXT con estructura Markdown compatibles con WhatsApp Business AI."""
        target = self.directory / "whatsapp"
        target.mkdir(parents=True, exist_ok=True)

        general = [
            f"# Base oficial de conocimiento de {self.brand_name}",
            "",
            "## Instrucciones obligatorias para el agente",
            "",
            f"- La fuente oficial siempre es {self.base_url}.",
            "- No inventar precios, disponibilidad, características, políticas ni tiempos de entrega.",
            "- Mantener separados Quito y Guayaquil; preguntar la ciudad cuando el cliente no la indique.",
            "- Usar exclusivamente los datos de la ciudad solicitada.",
            "- Si falta un dato, decir que no está publicado y compartir el enlace oficial del producto.",
            "- Informar que precio y disponibilidad deben confirmarse al momento de comprar.",
            "",
        ]
        for key, title in (("empresa", "Empresa"), ("politicas", "Políticas"), ("faq", "Preguntas frecuentes")):
            content = clean_text(site_documents.get(key, ""))
            general.extend([f"## {title}", "", content or "No se encontró información pública específica.", ""])
        (target / "00_instrucciones_empresa.txt").write_text("\n".join(general), encoding="utf-8")

        by_city: dict[str, list[Product]] = defaultdict(list)
        for product in products:
            by_city[product.city or product.store_code or "Sin ciudad"].append(product)

        index_lines = [
            f"# Índice de productos y enlaces oficiales de {self.brand_name}",
            "",
            f"Fuente oficial: {self.base_url}",
            "",
            "Usar el enlace de la misma ciudad solicitada por el cliente. No mezclar Quito y Guayaquil.",
            "",
        ]
        for city, rows in sorted(by_city.items()):
            index_lines.extend([f"## {city} ({len(rows)} productos)", ""])
            for product in sorted(rows, key=lambda item: item.name.casefold()):
                index_lines.append(f"- {product.name or 'Sin nombre'} — {product.url}")
            index_lines.append("")
        (target / "INDICE_PRODUCTOS_ENLACES.txt").write_text("\n".join(index_lines), encoding="utf-8")

        final_lines = [
            f"# CATÁLOGO FINAL DE {self.brand_name.upper()}",
            "",
            "Formato: Producto — Precio — Enlace oficial",
            f"Fuente oficial: {self.base_url}",
            "",
            "Instrucción para el agente: respetar la ciudad solicitada, no mezclar inventarios y no inventar información.",
            "",
        ]
        for city, rows in sorted(by_city.items()):
            final_lines.extend([f"## {city.upper()} ({len(rows)} PRODUCTOS)", ""])
            for product in sorted(rows, key=lambda item: item.name.casefold()):
                price = product.price_text or (
                    f"USD {product.current_price:.2f}" if product.current_price is not None else "Precio no publicado"
                )
                if "Rango de precios:" in price:
                    price = price.split("Rango de precios:", 1)[0].strip()
                final_lines.append(f"- {product.name or 'Sin nombre'} — {price} — {product.url}")
            final_lines.append("")
        (target / "CATALOGO_FINAL_PRODUCTO_PRECIO_LINK.txt").write_text(
            "\n".join(final_lines), encoding="utf-8"
        )

        for city, rows in sorted(by_city.items()):
            lines = [
                f"# Catálogo oficial de {self.brand_name} — {city}",
                "",
                f"Productos registrados: {len(rows)}",
                f"Fuente oficial: {self.base_url}",
                "",
                "Este archivo contiene únicamente productos de esta ciudad. No combinar con inventarios de otra ciudad.",
                "",
                "## Índice rápido de productos y enlaces",
                "",
            ]
            for product in sorted(rows, key=lambda item: item.name.casefold()):
                lines.append(f"- {product.name or 'Sin nombre'} — {product.url}")
            lines.extend(["", "## Fichas completas de productos", ""])
            current_category = None
            for p in sorted(rows, key=lambda item: (item.category.casefold(), item.subcategory.casefold(), item.name.casefold())):
                category = p.category or "Sin categoría publicada"
                if category != current_category:
                    lines.extend([f"## Categoría: {category}", ""])
                    current_category = category
                keywords = unique([p.name, p.category, p.subcategory, *p.tags, *p.attributes.values()])
                related = "; ".join(
                    f"{item.get('name', 'Sin nombre')} ({item.get('url', '')})" for item in p.related_products
                ) or "No publicados"
                lines.extend([
                    f"### Producto: {p.name or 'Sin nombre'}",
                    "",
                    f"- Ciudad: {p.city or 'No publicada'}",
                    f"- Categoría: {category}",
                    f"- Subcategoría: {p.subcategory or 'No publicada'}",
                    f"- Precio actual: {p.price_text or ('USD ' + format(p.current_price, '.2f') if p.current_price is not None else 'No publicado')}",
                    f"- Precio de oferta: {'USD ' + format(p.sale_price, '.2f') if p.sale_price is not None else 'No publicado'}",
                    f"- Descripción: {p.description or 'No publicada'}",
                    f"- Descripción corta: {p.short_description or 'No publicada'}",
                    f"- SKU: {p.sku or 'No publicado'}",
                    f"- Peso: {p.weight or 'No publicado'}",
                    f"- Estado: {p.status or 'No publicado'}",
                    f"- Stock: {p.stock or 'No publicado'}",
                    f"- Palabras clave: {', '.join(keywords) or 'No publicadas'}",
                    f"- Productos relacionados: {related}",
                    f"- Enlace oficial: {p.url}",
                ])
                if p.variations:
                    lines.append("- Variantes:")
                    for variation in p.variations:
                        attrs = ", ".join(f"{key}: {value}" for key, value in variation.attributes.items()) or "Sin atributos"
                        price = f"USD {variation.price:.2f}" if variation.price is not None else "Precio no publicado"
                        stock = variation.stock_quantity if variation.stock_quantity is not None else "No publicado"
                        lines.append(f"  - {attrs}; {price}; SKU: {variation.sku or 'No publicado'}; stock: {stock}")
                else:
                    lines.append("- Variantes: No publicadas")
                lines.append("")

            filename = f"catalogo_{slugify(city)}.txt"
            (target / filename).write_text("\n".join(lines), encoding="utf-8")
