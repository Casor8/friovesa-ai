from __future__ import annotations

from xml.etree import ElementTree

from scraper.discovery import canonical_url
from scraper.http_client import HttpClient


def read_product_lastmods(client: HttpClient, sitemap_url: str) -> dict[str, str]:
    if not sitemap_url:
        return {}
    response = client.get(sitemap_url)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    result: dict[str, str] = {}
    for node in root.findall("{*}url"):
        loc = node.find("{*}loc")
        lastmod = node.find("{*}lastmod")
        if loc is not None and loc.text:
            result[canonical_url(loc.text.strip())] = lastmod.text.strip() if lastmod is not None and lastmod.text else ""
    return result
