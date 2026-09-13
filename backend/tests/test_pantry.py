import unittest
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock
from app.services.pantry import (
    normalize_name,
    _sanitize_quantity,
    _sanitize_category,
    _days_until_expiry,
    update_pantry_item,
    get_expiring_items,
    mark_expiry_alerted,
    reset_pantry_alert,
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


class TestPantryAlerts(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.pantry._all_pantry_records", new_callable=AsyncMock)
    async def test_alert_lifecycle_decoupled(self, mock_all):
        """
        Verify decoupled alert behavior:
        - If last_alerted_expiry == expiry, item is alerted.
        - If expiry changes and does not match last_alerted_expiry, alerted is False.
        - If unalerted, alerted is False.
        """
        today = date.today()
        exp_soon = (today + timedelta(days=1)).isoformat()
        exp_old = (today + timedelta(days=-1)).isoformat()

        mock_all.return_value = [
            # Item 1: Alerted for its current expiry
            {
                "id": "item_1",
                "title": "milk",
                "data": {
                    "name": "milk",
                    "quantity": 1,
                    "unit": "carton",
                    "expiry": exp_soon,
                    "last_alerted_expiry": exp_soon,
                    "last_alerted_at": "2026-09-12T10:00:00Z",
                },
            },
            # Item 2: Alerted for an OLD expiry date, but user updated expiry to exp_soon -> alert is rearmed!
            {
                "id": "item_2",
                "title": "yogurt",
                "data": {
                    "name": "yogurt",
                    "quantity": 2,
                    "unit": "cups",
                    "expiry": exp_soon,
                    "last_alerted_expiry": exp_old,
                    "last_alerted_at": "2026-09-10T10:00:00Z",
                },
            },
            # Item 3: Brand new / never alerted
            {
                "id": "item_3",
                "title": "spinach",
                "data": {
                    "name": "spinach",
                    "quantity": 1,
                    "unit": "bunch",
                    "expiry": exp_soon,
                },
            },
            # Item 4: Legacy alert format (expiry_alerted=True, no last_alerted_expiry)
            {
                "id": "item_4",
                "title": "cheese",
                "data": {
                    "name": "cheese",
                    "quantity": 1,
                    "unit": "block",
                    "expiry": exp_soon,
                    "expiry_alerted": True,
                },
            },
        ]

        items = await get_expiring_items(within_days=3)
        item_map = {i["name"]: i for i in items}

        self.assertTrue(item_map["milk"]["alerted"])
        self.assertEqual(item_map["milk"]["alert_status"], "alerted")

        # Yogurt should NOT be considered alerted for the new expiry date!
        self.assertFalse(item_map["yogurt"]["alerted"])
        self.assertEqual(item_map["yogurt"]["alert_status"], "stale_alert")

        # Spinach was never alerted
        self.assertFalse(item_map["spinach"]["alerted"])
        self.assertEqual(item_map["spinach"]["alert_status"], "pending")

        # Cheese has legacy boolean
        self.assertTrue(item_map["cheese"]["alerted"])
        self.assertEqual(item_map["cheese"]["alert_status"], "alerted")

    @patch("app.services.pantry.update_record_status", new_callable=AsyncMock)
    async def test_mark_expiry_alerted_records_expiry(self, mock_update):
        """mark_expiry_alerted must save last_alerted_expiry."""
        mock_update.return_value = {"id": "rec_123", "data": {}}
        await mark_expiry_alerted(record_id="rec_123", expiry="2026-09-20")

        mock_update.assert_awaited_once()
        _, kwargs = mock_update.call_args
        updates = kwargs["updates"]
        self.assertEqual(updates["last_alerted_expiry"], "2026-09-20")
        self.assertTrue(updates["expiry_alerted"])
        self.assertIsNotNone(updates["last_alerted_at"])

    @patch("app.services.pantry.update_record_status", new_callable=AsyncMock)
    @patch("app.services.pantry._find_records_by_normalized_name", new_callable=AsyncMock)
    async def test_reset_pantry_alert(self, mock_find, mock_update):
        """reset_pantry_alert clears last_alerted_expiry and expiry_alerted."""
        mock_find.return_value = [
            {"id": "rec_999", "title": "milk", "data": {"expiry_alerted": True, "last_alerted_expiry": "2026-09-15"}}
        ]
        result = await reset_pantry_alert(name="milk")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "alert_reset")

        mock_update.assert_awaited_once_with(
            record_id="rec_999",
            user_id="default_user",
            updates={
                "expiry_alerted": False,
                "expiry_alerted_at": None,
                "last_alerted_expiry": None,
                "last_alerted_at": None,
            },
        )


class TestResetPantryAlertTool(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.pantry.reset_pantry_alert", new_callable=AsyncMock)
    async def test_reset_tool_ainvoke(self, mock_svc_reset):
        from app.services.tools import reset_pantry_alert as tool_reset
        mock_svc_reset.return_value = {
            "ok": True,
            "action": "alert_reset",
            "name": "milk",
            "message": "Expiry alert reset for 'milk'. It will alert again when near expiry.",
        }
        res = await tool_reset.ainvoke({"name": "milk"})
        self.assertIn("Expiry alert reset for 'milk'", res)
        self.assertIn("✅", res)


if __name__ == "__main__":
    unittest.main()