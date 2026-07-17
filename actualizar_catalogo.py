from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.settings import PROJECT_ROOT, SETTINGS
from knowledge_builder.generator import KnowledgeGenerator
from output.writers import archive_current, load_previous, snapshot_version, write_catalogs, write_change_report
from scraper.crawler import FriovesaCrawler
from scraper.sitemap import read_product_lastmods
from scraper.site_content import SiteContentCrawler
from utils.change_detector import detect_changes
from utils.logging_setup import setup_logging


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Actualiza el catálogo y la base de conocimiento oficial de Friovesa.")
    parser.add_argument("--solo-ciudad", choices=("uio", "gye"), help="Uso diagnóstico; una ejecución oficial debe recorrer ambas.")
    parser.add_argument("--csv-antiguo", type=Path, help="CSV opcional para comparar; nunca se usa como fuente del catálogo.")
    parser.add_argument("--full", action="store_true", help="Fuerza la descarga completa de todas las fichas.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def compare_legacy_csv(path: Path, products: list, output_dir: Path) -> Path:
    old = pd.read_csv(path, dtype=str).fillna("")
    current = pd.DataFrame([p.to_dict() for p in products])
    old.columns = [str(c).strip().casefold() for c in old.columns]
    candidate = next((c for c in ("sku", "codigo", "código") if c in old.columns), None)
    if not candidate:
        raise ValueError("El CSV antiguo no tiene una columna SKU/código para una comparación segura.")
    merged = old.merge(current, left_on=candidate, right_on="sku", how="outer", indicator=True, suffixes=("_csv_antiguo", "_web_actual"))
    target = output_dir / "comparacion_csv_antiguo.csv"
    merged.to_csv(target, index=False, encoding="utf-8-sig")
    return target


def main() -> int:
    args = arguments()
    log_path = setup_logging(SETTINGS.logs_dir, args.verbose)
    log = logging.getLogger("actualizar_catalogo")
    run_at = datetime.now(timezone.utc).isoformat()
    try:
        previous = load_previous(SETTINGS.output_dir)
        crawler = FriovesaCrawler(SETTINGS)
        try:
            lastmods = read_product_lastmods(crawler.client, SETTINGS.sitemap_url)
        except Exception:
            log.exception("No se pudo leer el sitemap; se hará actualización completa por seguridad.")
            lastmods = {}
            args.full = True
        products = []
        discovery = {}
        stores = [s for s in SETTINGS.stores if not args.solo_ciudad or s.code == args.solo_ciudad]
        for store in stores:
            log.info("Recorriendo %s desde %s", store.city, store.url)
            city_products, info, stats = crawler.crawl_store(store, previous, lastmods, args.full)
            products.extend(city_products)
            discovery[store.code] = {"pages": info.pages, "expected_count": info.expected_count, "found": len(info.urls), "categories_seen": info.category_links, **stats}

        if not args.solo_ciudad and {p.store_code for p in products} != {s.code for s in SETTINGS.stores}:
            raise RuntimeError("La ejecución oficial no contiene las dos ciudades; no se publicarán salidas parciales.")

        changes = detect_changes(previous, products)
        site_documents = SiteContentCrawler(crawler.client, SETTINGS.base_url).crawl()
        archive = archive_current(SETTINGS.output_dir)
        metadata = {
            "run_at": run_at, "source": SETTINGS.base_url, "brand_code": SETTINGS.brand_code, "brand_name": SETTINGS.brand_name, "stores": discovery,
            "product_count": len(products), "errors": sum(bool(p.error) for p in products),
            "previous_archive": str(archive) if archive else None,
        }
        paths = write_catalogs(products, SETTINGS.output_dir, metadata)
        site_content_path = SETTINGS.output_dir / "contenido_web.json"
        site_content_path.write_text(json.dumps(site_documents, ensure_ascii=False, indent=2), encoding="utf-8")
        KnowledgeGenerator(SETTINGS.knowledge_dir, SETTINGS.brand_name, SETTINGS.base_url).generate(products, site_documents)
        version = snapshot_version(SETTINGS.output_dir, datetime.now().strftime("%Y%m%d_%H%M%S"))
        report = write_change_report(changes, SETTINGS.reports_dir, run_at, SETTINGS.output_dir)
        legacy = compare_legacy_csv(args.csv_antiguo, products, SETTINGS.output_dir) if args.csv_antiguo else None
        summary = {
            "status": "ok", "products": len(products), "new": len(changes.new), "removed": len(changes.removed),
            "modified": len(changes.modified), "errors": metadata["errors"], "report": str(report),
            "catalog": str(paths["json"]), "knowledge": str(SETTINGS.knowledge_dir), "legacy_comparison": str(legacy) if legacy else None,
            "log": str(log_path),
            "version": str(version), "details_fetched": sum(v["details_fetched"] for v in discovery.values()),
            "details_reused": sum(v["details_reused"] for v in discovery.values()), "urls_verified": sum(v["urls_verified"] for v in discovery.values()),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        log.exception("La actualización falló; se conservaron las salidas publicadas anteriores cuando existían.")
        print(json.dumps({"status": "error", "error": str(exc), "log": str(log_path)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
