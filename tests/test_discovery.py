from __future__ import annotations

import unittest

from config.settings import StoreConfig
from scraper.discovery import StoreDiscovery


class Response:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


class Client:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def get(self, url: str):
        return Response(self.pages[url])


class DiscoveryTests(unittest.TestCase):
    def test_follows_next_without_fixed_page_count(self):
        first = '''<p class="woocommerce-result-count">Mostrando 1–1 de 2 resultados</p>
        <ul class="products"><li class="product"><div data-product-id="1"></div><a class="woocommerce-LoopProduct-link" href="https://x.test/product/a/"><h2 class="woocommerce-loop-product__title">A</h2></a></li></ul>
        <a class="next page-numbers" href="https://x.test/store/uio/page/2/">→</a>'''
        second = '''<ul class="products"><li class="product"><div data-product-id="2"></div><a class="woocommerce-LoopProduct-link" href="https://x.test/product/b/"><h2 class="woocommerce-loop-product__title">B</h2></a></li></ul>'''
        client = Client({"https://x.test/store/uio/": first, "https://x.test/store/uio/page/2/": second})
        result = StoreDiscovery(client).discover(StoreConfig("uio", "Quito", "https://x.test/store/uio/"))
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.expected_count, 2)
        self.assertEqual(len(result.urls), 2)
        self.assertEqual(result.items["https://x.test/product/b/"]["product_id"], "2")


if __name__ == "__main__":
    unittest.main()
