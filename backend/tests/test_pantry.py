import unittest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock
from app.services.pantry import (
    normalize_name,
    _sanitize_quantity,
    _sanitize_category,
    _days_until_expiry,
    update_pantry_item,
)


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


class TestUpdatePantryItem(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.pantry.update_record_status", new_callable=AsyncMock)
    @patch("app.services.pantry._find_records_by_normalized_name", new_callable=AsyncMock)
    async def test_update_quantity_preserves_expiry_and_category(self, mock_find, mock_update):
        """Updating quantity and unit must preserve existing expiry and category."""
        mock_find.return_value = [
            {
                "id": "rec_123",
                "title": "chicken thigh",
                "data": {
                    "name": "chicken thigh",
                    "quantity": 1.0,
                    "unit": "items",
                    "category": "meat",
                    "expiry": "2026-09-10",
                },
            }
        ]
        result = await update_pantry_item(name="chicken thigh", quantity=700, unit="g")
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantity"], 700.0)
        self.assertEqual(result["unit"], "g")
        self.assertEqual(result["category"], "meat")
        self.assertEqual(result["expiry"], "2026-09-10")

        mock_update.assert_awaited_once()
        _, kwargs = mock_update.call_args
        updates = kwargs["updates"]
        self.assertEqual(updates["quantity"], 700.0)
        self.assertEqual(updates["unit"], "g")
        self.assertEqual(updates["category"], "meat")
        self.assertEqual(updates["expiry"], "2026-09-10")

    @patch("app.services.pantry.update_record_status", new_callable=AsyncMock)
    @patch("app.services.pantry._find_records_by_normalized_name", new_callable=AsyncMock)
    async def test_update_expiry_only(self, mock_find, mock_update):
        """Updating expiry date must preserve existing quantity, unit, and category."""
        mock_find.return_value = [
            {
                "id": "rec_456",
                "title": "milk",
                "data": {
                    "name": "milk",
                    "quantity": 2.0,
                    "unit": "l",
                    "category": "dairy",
                },
            }
        ]
        result = await update_pantry_item(name="milk", expiry="2026-09-15")
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantity"], 2.0)
        self.assertEqual(result["unit"], "l")
        self.assertEqual(result["expiry"], "2026-09-15")

    @patch("app.services.pantry._find_records_by_normalized_name", new_callable=AsyncMock)
    async def test_update_not_found(self, mock_find):
        """Attempting to update an item not in the pantry returns a graceful error."""
        mock_find.return_value = []
        result = await update_pantry_item(name="nonexistent item", quantity=5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not_found")

    @patch("app.services.pantry.delete_record", new_callable=AsyncMock)
    @patch("app.services.pantry.update_record_status", new_callable=AsyncMock)
    @patch("app.services.pantry._find_records_by_normalized_name", new_callable=AsyncMock)
    async def test_update_consolidates_duplicates(self, mock_find, mock_update, mock_delete):
        """If duplicates exist, extra records are consolidated/deleted."""
        mock_find.return_value = [
            {
                "id": "rec_1",
                "title": "tomato",
                "data": {"name": "tomato", "quantity": 2, "unit": "items"},
            },
            {
                "id": "rec_2",
                "title": "tomato",
                "data": {"name": "tomato", "quantity": 1, "unit": "items"},
            },
        ]
        result = await update_pantry_item(name="tomato", quantity=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["quantity"], 10.0)
        mock_delete.assert_awaited_once_with(record_id="rec_2", user_id="default_user")


class TestUpdatePantryTool(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.pantry.update_pantry_item", new_callable=AsyncMock)
    async def test_tool_ainvoke(self, mock_svc_update):
        from app.services.tools import update_pantry_item as tool_update
        mock_svc_update.return_value = {
            "ok": True,
            "action": "updated",
            "name": "chicken thigh",
            "quantity": 700.0,
            "unit": "g",
            "category": "meat",
            "expiry": "2026-09-10",
            "message": "Updated 'chicken thigh' in pantry (now 700.0 g).",
        }
        res = await tool_update.ainvoke({"name": "chicken thigh", "quantity": 700, "unit": "g"})
        self.assertIn("Updated 'chicken thigh' in pantry", res)
        self.assertIn("700.0 g", res)
        self.assertIn("expiry 2026-09-10", res)


if __name__ == "__main__":
    unittest.main()