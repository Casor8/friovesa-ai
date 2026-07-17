from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from config.settings import Settings, StoreConfig
from models.producto import Product
from scraper.discovery import DiscoveryResult, StoreDiscovery
from scraper.http_client import HttpClient
from scraper.product_parser import parse_product
from utils.text import clean_text


class FriovesaCrawler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = HttpClient(settings)
        self.discovery = StoreDiscovery(self.client)
        self.log = logging.getLogger(__name__)

    def crawl_store(
        self,
        store: StoreConfig,
        previous: list[dict] | None = None,
        lastmods: dict[str, str] | None = None,
        force_full: bool = False,
    ) -> tuple[list[Product], DiscoveryResult, dict[str, int]]:
        discovered = self.discovery.discover(store)
        previous = previous or []
        lastmods = lastmods or {}
        old_by_url = {row.get("url", "").rstrip("/"): row for row in previous if row.get("store_code") == store.code}
        old_by_id = {str(row.get("product_id")): row for row in previous if row.get("store_code") == store.code and row.get("product_id")}
        products: list[Product] = []
        tasks: dict = {}
        reused: list[tuple[Product, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, self.settings.workers)) as executor:
            for url in discovered.urls:
                listing = discovered.items.get(url, {})
                old = old_by_id.get(listing.get("product_id", "")) or old_by_url.get(url.rstrip("/"))
                sitemap_lastmod = lastmods.get(url, "")
                if self._needs_detail(url, listing, old, sitemap_lastmod, force_full):
                    tasks[executor.submit(self._fetch_product, url, store, sitemap_lastmod, listing, discovered.category_links)] = (url, "detail")
                else:
                    product = Product.from_dict(old)
                    product.url = url
                    product.extra = dict(product.extra or {})
                    product.extra.update({"sitemap_lastmod": sitemap_lastmod, "listing": listing})
                    reused.append((product, url))
                    tasks[executor.submit(self.client.head, url)] = (url, "verify")
            verified_reused: dict[str, Product] = {url: product for product, url in reused}
            for index, future in enumerate(as_completed(tasks), 1):
                url, kind = tasks[future]
                try:
                    if kind == "detail":
                        products.append(future.result())
                    else:
                        response = future.result()
                        product = verified_reused[url]
                        product.http_status = response.status_code
                        product.final_url = response.url
                        product.status = "404" if response.status_code == 404 else (product.status if response.status_code < 400 else f"http_{response.status_code}")
                        product.error = "La URL devolvió 404." if response.status_code == 404 else ("" if response.status_code < 400 else f"La URL devolvió HTTP {response.status_code}.")
                        products.append(product)
                except Exception as exc:  # conserva la URL fallida en el catálogo y el reporte
                    self.log.exception("Error en %s", url)
                    existing = verified_reused.get(url)
                    if existing:
                        existing.status, existing.error = "error_verificacion", str(exc)
                        products.append(existing)
                    else:
                        products.append(Product(city=store.city, store_code=store.code, url=url, status="error", error=str(exc)))
                if index % 20 == 0 or index == len(tasks):
                    self.log.info("%s: procesados %d/%d", store.city, index, len(tasks))
        products.sort(key=lambda p: (p.category.casefold(), p.subcategory.casefold(), p.name.casefold(), p.url))
        stats = {"details_fetched": sum(kind == "detail" for _, kind in tasks.values()), "details_reused": len(reused), "urls_verified": len(tasks)}
        return products, discovered, stats

    def _fetch_product(self, url: str, store: StoreConfig, sitemap_lastmod: str, listing: dict[str, str], category_links: dict[str, str]) -> Product:
        response = self.client.get(url)
        product = parse_product(response.text, url, response.url, response.status_code, store, category_links)
        product.extra = dict(product.extra or {})
        listing_id = clean_text(listing.get("product_id"))
        if listing_id and listing_id != product.product_id:
            product.extra["html_product_id"] = product.product_id
            product.product_id = listing_id
        product.extra.update({"sitemap_lastmod": sitemap_lastmod, "listing": listing})
        return product

    def _needs_detail(self, url: str, listing: dict[str, str], old: dict | None, lastmod: str, force_full: bool) -> bool:
        if force_full or not self.settings.incremental or not old:
            return True
        if old.get("url", "").rstrip("/") != url.rstrip("/") or old.get("error"):
            return True
        old_extra = old.get("extra") or {}
        if lastmod and lastmod != old_extra.get("sitemap_lastmod", ""):
            return True
        old_listing = old_extra.get("listing") or {}
        if any(clean_text(listing.get(key)) != clean_text(old_listing.get(key)) for key in ("product_id", "name", "price_text")):
            return True
        try:
            scraped = datetime.fromisoformat(str(old.get("scraped_at", "")).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - scraped > timedelta(days=self.settings.full_refresh_days):
                return True
        except ValueError:
            return True
        return False
