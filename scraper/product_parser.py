from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from config.settings import StoreConfig
from models.producto import Product, Variation
from utils.text import clean_text, parse_price, unique


def _text(node: Tag | None) -> str:
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _meta(soup: BeautifulSoup, *, prop: str = "", name: str = "") -> str:
    selector = f'meta[property="{prop}"]' if prop else f'meta[name="{name}"]'
    node = soup.select_one(selector)
    return clean_text(node.get("content", "")) if node else ""


def _money_values(container: Tag | BeautifulSoup | None) -> list[float]:
    if not container:
        return []
    values: list[float] = []
    for node in container.select(".woocommerce-Price-amount, .amount"):
        parsed = parse_price(_text(node))
        if parsed is not None and parsed not in values:
            values.append(parsed)
    return values


def _json_ld_product(soup: BeautifulSoup) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = data.get("@graph", []) if isinstance(data, dict) and "@graph" in data else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return {}


def _taxonomy(soup: BeautifulSoup, store: StoreConfig, category_links: dict[str, str] | None = None) -> tuple[list[str], str, str]:
    anchors = soup.select(".posted_in a[href], a[rel='tag'][href*='/categoria-producto/']")
    paths: list[tuple[list[str], str]] = []
    labels: dict[str, str] = {}
    for url, label in (category_links or {}).items():
        relative = urlsplit(url).path.split("/categoria-producto/", 1)[-1].strip("/")
        slugs = [unquote(s) for s in relative.split("/") if s]
        if slugs and label:
            labels[slugs[-1]] = label
    for anchor in anchors:
        if "/categoria-producto/" not in anchor.get("href", ""):
            continue
        label = _text(anchor)
        relative = urlsplit(anchor["href"]).path.split("/categoria-producto/", 1)[-1].strip("/")
        slugs = [unquote(s) for s in relative.split("/") if s]
        if label and slugs:
            labels[slugs[-1]] = label
            paths.append((slugs, label))
    if not paths:
        return [], "", ""
    longest = max(paths, key=lambda pair: len(pair[0]))[0]
    city_slugs = {store.code.casefold(), store.city.casefold()}
    hierarchy_slugs = [slug for slug in longest if slug.casefold() not in city_slugs]
    hierarchy = [labels.get(slug, slug.replace("-", " ").title()) for slug in hierarchy_slugs]
    all_labels = unique(labels.get(slugs[-1], label) for slugs, label in paths if slugs[-1].casefold() not in city_slugs)
    categories = unique(hierarchy + all_labels)
    category = hierarchy[0] if hierarchy else (categories[0] if categories else "")
    subcategory = hierarchy[-1] if len(hierarchy) > 1 else (categories[1] if len(categories) > 1 else "")
    return categories, category, subcategory


def _parse_variations(soup: BeautifulSoup) -> list[Variation]:
    form = soup.select_one("form.variations_form[data-product_variations]")
    if not form:
        return []
    raw = html.unescape(form.get("data-product_variations", ""))
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    result: list[Variation] = []
    for row in rows if isinstance(rows, list) else []:
        availability = BeautifulSoup(row.get("availability_html", ""), "html.parser").get_text(" ", strip=True)
        quantity_match = re.search(r"\d+(?:[.,]\d+)?", availability)
        regular = row.get("display_regular_price")
        current = row.get("display_price")
        sale = current if current is not None and regular is not None and current < regular else None
        image_data = row.get("image") or {}
        result.append(
            Variation(
                variation_id=str(row.get("variation_id", "")),
                attributes={k.removeprefix("attribute_").replace("pa_", ""): clean_text(v) for k, v in (row.get("attributes") or {}).items()},
                price=current,
                regular_price=regular,
                sale_price=sale,
                sku=clean_text(row.get("sku")),
                weight=clean_text(row.get("weight")),
                in_stock=row.get("is_in_stock"),
                stock_quantity=float(quantity_match.group(0).replace(",", ".")) if quantity_match else row.get("max_qty"),
                image=clean_text(image_data.get("full_src") or image_data.get("url") or image_data.get("src")),
                description=clean_text(BeautifulSoup(row.get("variation_description", ""), "html.parser").get_text(" ", strip=True)),
            )
        )
    return result


def parse_product(
    html_text: str,
    requested_url: str,
    final_url: str,
    status_code: int,
    store: StoreConfig,
    category_links: dict[str, str] | None = None,
) -> Product:
    soup = BeautifulSoup(html_text, "html.parser")
    structured = _json_ld_product(soup)
    product = Product(city=store.city, store_code=store.code, url=requested_url, final_url=final_url, http_status=status_code)
    product.scraped_at = datetime.now(timezone.utc).isoformat()
    product.status = "404" if status_code == 404 else ("activo" if 200 <= status_code < 400 else f"http_{status_code}")
    if status_code == 404:
        product.error = "La URL devolvió 404."
        return product

    title = soup.select_one("h1.product_title, h3.product_title, .product_title")
    product.name = _text(title) or clean_text(structured.get("name")) or _meta(soup, prop="og:title")
    id_source = soup.select_one("form.cart[data-product_id], form.cart input[name='add-to-cart'][value], form.cart button[name='add-to-cart'][value]")
    if id_source:
        product.product_id = clean_text(id_source.get("data-product_id") or id_source.get("value"))
    if not product.product_id:
        body = soup.body
        match = re.search(r"(?:postid-|post-)(\d+)", " ".join(body.get("class", [])) if body else "")
        product.product_id = match.group(1) if match else ""

    summary = soup.select_one(".summary.entry-summary, .summary, .elementor-widget-woocommerce-product-price") or soup
    price_node = summary.select_one("p.price, .price")
    product.price_text = _text(price_node)
    regular_node = price_node.select_one("del .amount") if price_node else None
    sale_node = price_node.select_one("ins .amount") if price_node else None
    values = _money_values(price_node)
    product.regular_price = parse_price(_text(regular_node)) if regular_node else (values[0] if values else None)
    product.sale_price = parse_price(_text(sale_node)) if sale_node else None
    product.current_price = product.sale_price if product.sale_price is not None else (values[-1] if values else None)

    short = soup.select_one(".woocommerce-product-details__short-description, .product-short-description")
    description = soup.select_one("#tab-description, .woocommerce-Tabs-panel--description, .woocommerce-product-details__description")
    product.short_description = _text(short) or clean_text(_meta(soup, name="description"))
    product.description = _text(description) or clean_text(structured.get("description"))

    sku_node = soup.select_one(".sku")
    product.sku = _text(sku_node) or clean_text(structured.get("sku"))
    weight_row = soup.select_one(".woocommerce-product-attributes-item--weight td, tr[class*='weight'] td")
    product.weight = _text(weight_row)
    stock_node = soup.select_one("p.stock, .stock")
    product.stock = _text(stock_node)
    if stock_node:
        product.status = "agotado" if "out-of-stock" in stock_node.get("class", []) else product.status
        quantity_match = re.search(r"\d+(?:[.,]\d+)?", product.stock)
        product.stock_quantity = float(quantity_match.group(0).replace(",", ".")) if quantity_match else None

    product.images = unique(
        [node.get("data-large_image") or node.get("href") or node.get("src", "") for node in soup.select(".woocommerce-product-gallery a[href], .woocommerce-product-gallery img")]
        + ([clean_text(structured.get("image"))] if isinstance(structured.get("image"), str) else [])
        + [_meta(soup, prop="og:image")]
    )
    product.categories, product.category, product.subcategory = _taxonomy(soup, store, category_links)
    product.tags = unique(_text(a) for a in soup.select(".tagged_as a, a[rel='tag']:not([href*='/categoria-producto/'])"))
    product.breadcrumbs = unique(_text(a) for a in soup.select(".woocommerce-breadcrumb a, nav.breadcrumb a"))
    product.related_products = [
        {"name": _text(item.select_one(".woocommerce-loop-product__title, h2")), "url": urljoin(final_url, link["href"])}
        for item in soup.select(".related.products li.product, section.related li.product")
        if (link := item.select_one("a[href]"))
    ]
    for row in soup.select("table.woocommerce-product-attributes tr"):
        label = _text(row.select_one("th"))
        value = _text(row.select_one("td"))
        if label and value:
            product.attributes[label] = value
    product.variations = _parse_variations(soup)
    if not product.weight:
        product.weight = next((v.weight for v in product.variations if v.weight), "")
    if not product.stock and product.variations:
        states = [v.in_stock for v in product.variations if v.in_stock is not None]
        product.stock = "Con stock" if any(states) else ("Agotado" if states else "")
    if product.current_price is None and product.variations:
        prices = [v.price for v in product.variations if v.price is not None]
        if prices:
            product.current_price = min(prices)
            product.regular_price = max(prices) if len(set(prices)) > 1 else prices[0]
            product.price_text = f"${min(prices):.2f} - ${max(prices):.2f}" if len(set(prices)) > 1 else f"${prices[0]:.2f}"
    product.extra = {
        "brand": structured.get("brand", ""),
        "gtin": structured.get("gtin", structured.get("gtin13", "")),
        "mpn": structured.get("mpn", ""),
    }
    return product
