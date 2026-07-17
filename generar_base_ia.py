from __future__ import annotations

import json

from config.settings import SETTINGS
from knowledge_builder.generator import KnowledgeGenerator
from models.producto import Product


def main() -> int:
    catalog_path = SETTINGS.output_dir / "catalogo.json"
    if not catalog_path.exists():
        raise SystemExit("No existe output/catalogo.json. Ejecute primero: python actualizar_catalogo.py")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    products = [Product.from_dict(row) for row in payload.get("products", [])]
    content_path = SETTINGS.output_dir / "contenido_web.json"
    site_documents = json.loads(content_path.read_text(encoding="utf-8")) if content_path.exists() else {}
    KnowledgeGenerator(SETTINGS.knowledge_dir, SETTINGS.brand_name, SETTINGS.base_url).generate(products, site_documents)
    print(f"Base IA regenerada: {SETTINGS.knowledge_dir} ({len(products)} productos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
