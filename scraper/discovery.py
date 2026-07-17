from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from config.settings import StoreConfig
from scraper.http_client import HttpClient
from utils.text import unique


@dataclass
class DiscoveryResult:
    urls: list[str]
    pages: int
    expected_count: int | None
    category_links: dict[str, str]
    items: dict[str, dict[str, str]]


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


class StoreDiscovery:
    def __init__(self, client: HttpClient):
        self.client = client
        self.log = logging.getLogger(__name__)

    def discover(self, store: StoreConfig) -> DiscoveryResult:
        page_url: str | None = store.url
        seen_pages: set[str] = set()
        product_urls: list[str] = []
        categories: dict[str, str] = {}
        items: dict[str, dict[str, str]] = {}
        expected: int | None = None

        while page_url:
            page_url = canonical_url(page_url)
            if page_url in seen_pages:
                break
            seen_pages.add(page_url)
            response = self.client.get(page_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            if expected is None:
                result_text = soup.select_one(".woocommerce-result-count")
                if result_text:
                    numbers = re.findall(r"\d+", result_text.get_text(" ", strip=True))
                    if numbers:
                        expected = int(numbers[-1])

            links = []
            for card in soup.select("ul.products li.product, li.product"):
                anchor = card.select_one("a.woocommerce-LoopProduct-link[href], a.woocommerce-loop-product__link[href], a[href*='/product/']")
                if not anchor:
                    continue
                url = canonical_url(urljoin(page_url, anchor["href"]))
                if "/product/" not in urlsplit(url).path:
                    continue
                links.append(url)
                id_node = card.select_one("[data-product-id], [data-product_id]")
                title = card.select_one(".woocommerce-loop-product__title, h2")
                price = card.select_one(".price")
                items[url] = {
                    "product_id": str((id_node.get("data-product-id") or id_node.get("data-product_id")) if id_node else ""),
                    "name": title.get_text(" ", strip=True) if title else "",
                    "price_text": price.get_text(" ", strip=True) if price else "",
                }
            if not links:
                links = [canonical_url(urljoin(page_url, a["href"])) for a in soup.select("a[href*='/product/']")]
                links = [u for u in links if "/product/" in urlsplit(u).path]
                for url in links:
                    items.setdefault(url, {"product_id": "", "name": "", "price_text": ""})
            product_urls.extend(links)

            for anchor in soup.select("a[href*='/categoria-producto/']"):
                label = anchor.get_text(" ", strip=True)
                if label:
                    categories[canonical_url(urljoin(page_url, anchor["href"]))] = label

            next_link = soup.select_one("a.next.page-numbers[href], a[rel='next'][href]")
            page_url = urljoin(page_url, next_link["href"]) if next_link else None
            self.log.info("%s: página %d, %d productos únicos", store.city, len(seen_pages), len(unique(product_urls)))

        urls = unique(product_urls)
        if expected is not None and len(urls) != expected:
            raise RuntimeError(
                f"Descubrimiento incompleto para {store.city}: la web anuncia {expected} productos y se encontraron {len(urls)}."
            )
        return DiscoveryResult(urls=urls, pages=len(seen_pages), expected_count=expected, category_links=categories, items=items)
