from __future__ import annotations

import unittest

from config.settings import StoreConfig
from scraper.product_parser import parse_product


HTML = '''
<html><body class="single-product postid-80">
<h1 class="product_title">Producto Prueba</h1>
<div class="summary"><p class="price"><del><span class="amount">$ 10,00</span></del><ins><span class="amount">$ 8,50</span></ins></p></div>
<div class="woocommerce-product-details__short-description">Descripción corta oficial.</div>
<div id="tab-description">Descripción larga oficial.</div>
<div class="product_meta"><span class="sku">ABC-1</span><span class="posted_in"><a href="https://friovesa.com/categoria-producto/uio/proteinas/mariscos/" rel="tag">Mariscos</a></span></div>
<p class="stock in-stock">12 disponibles</p>
<form class="variations_form" data-product_id="80" data-product_variations="[{&quot;variation_id&quot;:81,&quot;attributes&quot;:{&quot;attribute_pa_peso&quot;:&quot;1-kg&quot;},&quot;display_price&quot;:8.5,&quot;display_regular_price&quot;:10,&quot;sku&quot;:&quot;ABC-1-1KG&quot;,&quot;is_in_stock&quot;:true,&quot;max_qty&quot;:12,&quot;weight&quot;:&quot;1&quot;,&quot;image&quot;:{&quot;full_src&quot;:&quot;https://example.com/a.jpg&quot;}}]"></form>
</body></html>
'''


class ParserTests(unittest.TestCase):
    def test_core_fields_and_variation(self):
        product = parse_product(HTML, "https://friovesa.com/product/prueba/", "https://friovesa.com/product/prueba/", 200, StoreConfig("uio", "Quito", ""))
        self.assertEqual(product.product_id, "80")
        self.assertEqual(product.name, "Producto Prueba")
        self.assertEqual(product.current_price, 8.5)
        self.assertEqual(product.regular_price, 10.0)
        self.assertEqual(product.category, "Proteinas")
        self.assertEqual(product.subcategory, "Mariscos")
        self.assertEqual(product.stock_quantity, 12.0)
        self.assertEqual(product.variations[0].sku, "ABC-1-1KG")

    def test_404_is_preserved(self):
        product = parse_product("<html></html>", "https://friovesa.com/product/no/", "https://friovesa.com/product/no/", 404, StoreConfig("gye", "Guayaquil", ""))
        self.assertEqual(product.status, "404")
        self.assertTrue(product.error)

    def test_unrelated_widget_product_id_is_ignored(self):
        html = '<body class="single-product postid-777"><div data-product-id="93"></div><h1 class="product_title">Real</h1></body>'
        product = parse_product(html, "https://friovesa.com/product/real/", "https://friovesa.com/product/real/", 200, StoreConfig("uio", "Quito", ""))
        self.assertEqual(product.product_id, "777")


if __name__ == "__main__":
    unittest.main()
