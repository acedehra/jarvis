import unittest
import json
from app.services.tools import random_picker


class TestRandomPickerTool(unittest.TestCase):
    def test_single_selection(self):
        options = ["Alice", "Bob", "Charlie", "David", "Emma"]
        result = random_picker.invoke({"options": options, "count": 1})
        self.assertTrue(result.startswith("🎉 Selected: "))
        selected = result.replace("🎉 Selected: ", "").strip()
        self.assertIn(selected, options)

    def test_single_string_comma_separated(self):
        options_str = "Alice, Bob, Charlie, David"
        result = random_picker.invoke({"options": options_str, "count": 1})
        self.assertTrue(result.startswith("🎉 Selected: "))
        selected = result.replace("🎉 Selected: ", "").strip()
        self.assertIn(selected, ["Alice", "Bob", "Charlie", "David"])

    def test_single_string_json_array(self):
        options_json = '["Pizza", "Sushi", "Tacos"]'
        result = random_picker.invoke({"options": options_json, "count": 1})
        self.assertTrue(result.startswith("🎉 Selected: "))
        selected = result.replace("🎉 Selected: ", "").strip()
        self.assertIn(selected, ["Pizza", "Sushi", "Tacos"])

    def test_multiple_selection_without_replacement(self):
        options = ["Alice", "Bob", "Charlie", "David"]
        result = random_picker.invoke({"options": options, "count": 2, "with_replacement": False})
        self.assertIn("🎉 Selected (2 distinct items):", result)
        lines = result.strip().split("\n")[1:]
        self.assertEqual(len(lines), 2)
        winners = [line.split(". ", 1)[1].strip() for line in lines]
        self.assertEqual(len(set(winners)), 2)
        for w in winners:
            self.assertIn(w, options)

    def test_multiple_selection_with_replacement(self):
        options = ["Option A", "Option B"]
        result = random_picker.invoke({"options": options, "count": 5, "with_replacement": True})
        self.assertIn("🎉 Selected (5 items with replacement):", result)
        lines = result.strip().split("\n")[1:]
        self.assertEqual(len(lines), 5)
        for line in lines:
            choice = line.split(". ", 1)[1].strip()
            self.assertIn(choice, options)

    def test_shuffle(self):
        options = ["1", "2", "3", "4", "5", "6", "7", "8"]
        result = random_picker.invoke({"options": options, "shuffle": True})
        self.assertIn("🔀 Shuffled Order (8 items):", result)
        lines = result.strip().split("\n")[1:]
        self.assertEqual(len(lines), 8)
        items = [line.split(". ", 1)[1].strip() for line in lines]
        self.assertEqual(sorted(items), sorted(options))

    def test_weighted_selection(self):
        options = ["Common", "Rare"]
        weights = [1.0, 0.0]  # Only Common can be picked
        result = random_picker.invoke({"options": options, "weights": weights, "count": 1})
        self.assertEqual(result, "🎯 Weighted Selection: Common")

    def test_numeric_range_single(self):
        result = random_picker.invoke({"min_value": 1, "max_value": 6})
        self.assertTrue(result.startswith("🎲 Random Number (1 to 6): "))
        val_str = result.replace("🎲 Random Number (1 to 6): ", "").strip()
        val = int(val_str)
        self.assertTrue(1 <= val <= 6)

    def test_numeric_range_multiple(self):
        result = random_picker.invoke({"min_value": 10, "max_value": 20, "count": 3})
        self.assertIn("🎲 Random Numbers (3 drawn from 10 to 20):", result)

    def test_error_handling_empty_options(self):
        result = random_picker.invoke({"options": []})
        self.assertIn("Error: No options provided", result)

    def test_error_handling_exceeding_sample_size(self):
        options = ["A", "B"]
        result = random_picker.invoke({"options": options, "count": 5, "with_replacement": False})
        self.assertIn("Error: Requested 5 items without replacement", result)

    def test_error_handling_weights_mismatch(self):
        options = ["A", "B"]
        result = random_picker.invoke({"options": options, "weights": [0.5]})
        self.assertIn("Error: 'weights' length", result)
