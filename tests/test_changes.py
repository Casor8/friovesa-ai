from __future__ import annotations

import unittest

from models.producto import Product
from utils.change_detector import detect_changes


class ChangeTests(unittest.TestCase):
    def test_url_change_uses_stable_product_id(self):
        old = [Product(product_id="10", store_code="uio", city="Quito", name="A", url="https://x/product/a/", current_price=1).to_dict()]
        new = [Product(product_id="10", store_code="uio", city="Quito", name="A", url="https://x/product/nueva/", current_price=1)]
        changes = detect_changes(old, new)
        self.assertEqual(len(changes.modified), 1)
        self.assertEqual(changes.modified[0]["changes"][0]["field"], "url")
        self.assertFalse(changes.new)
        self.assertFalse(changes.removed)

    def test_new_and_removed_are_separate_by_city(self):
        old = [Product(product_id="10", store_code="uio", city="Quito", name="A", url="https://x/a").to_dict()]
        new = [Product(product_id="10", store_code="gye", city="Guayaquil", name="A", url="https://x/a")]
        changes = detect_changes(old, new)
        self.assertEqual(len(changes.new), 1)
        self.assertEqual(len(changes.removed), 1)


if __name__ == "__main__":
    unittest.main()
