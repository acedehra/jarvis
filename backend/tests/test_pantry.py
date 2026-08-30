import unittest
from datetime import date, timedelta
from app.services.pantry import normalize_name, _sanitize_quantity, _sanitize_category, _days_until_expiry


class TestPantryNormalization(unittest.TestCase):
    def test_pluralization_dedupes(self):
        """SAME ingredient entered with different plural forms must collapse to one key."""
        self.assertEqual(normalize_name("tomatoes"), normalize_name("tomato"))
        self.assertEqual(normalize_name("potatoes"), normalize_name("potato"))
        self.assertEqual(normalize_name("berries"), normalize_name("berry"))
        self.assertEqual(normalize_name("onions"), normalize_name("onion"))
        self.assertEqual(normalize_name("apples"), normalize_name("apple"))
        self.assertEqual(normalize_name("eggs"), normalize_name("egg"))
        self.assertEqual(normalize_name("slices"), normalize_name("slice"))
        self.assertEqual(normalize_name("boxes"), normalize_name("box"))
        self.assertEqual(normalize_name("dishes"), normalize_name("dish"))

    def test_case_and_whitespace(self):
        self.assertEqual(normalize_name("  TOMATO "), "tomato")
        self.assertEqual(normalize_name("Chicken Breast"), "chicken breast")
        self.assertEqual(normalize_name("olive   oil"), "olive oil")

    def test_singular_unchanged_and_special_endings(self):
        self.assertEqual(normalize_name("basil"), "basil")
        self.assertEqual(normalize_name("rice"), "rice")          # not stripped to "ric"
        self.assertEqual(normalize_name("class"), "class")        # ss preserved
        self.assertEqual(normalize_name("salsa"), "salsa")        # ends in 'a'

    def test_posters_plural_exceptions(self):
        # 'sauce' should not collapse to anything weird
        self.assertEqual(normalize_name("sauces"), "sauce")


class TestPantrySanitizers(unittest.TestCase):
    def test_quantity(self):
        self.assertEqual(_sanitize_quantity(None), 0.0)
        self.assertEqual(_sanitize_quantity(""), 0.0)
        self.assertEqual(_sanitize_quantity("2"), 2.0)
        self.assertEqual(_sanitize_quantity(0.5), 0.5)
        self.assertEqual(_sanitize_quantity(-5), 0.0)
        self.assertEqual(_sanitize_quantity("abc"), 0.0)

    def test_category(self):
        self.assertEqual(_sanitize_category(None), "other")
        self.assertEqual(_sanitize_category("Dairy"), "dairy")
        self.assertEqual(_sanitize_category("not-a-category"), "other")


class TestPantryExpiry(unittest.TestCase):
    def test_days_until_expiry(self):
        today = date.today()
        self.assertEqual(_days_until_expiry((today + timedelta(days=2)).isoformat()), 2)
        self.assertEqual(_days_until_expiry(today.isoformat()), 0)
        self.assertEqual(_days_until_expiry((today - timedelta(days=5)).isoformat()), -5)

    def test_days_until_expiry_none_for_missing_or_garbage(self):
        self.assertIsNone(_days_until_expiry(None))
        self.assertIsNone(_days_until_expiry(""))
        with self.assertLogs("tracker", level="WARNING"):
            self.assertIsNone(_days_until_expiry("not-a-date"))


if __name__ == "__main__":
    unittest.main()