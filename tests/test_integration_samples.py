"""Isolation and integration sample behavior."""
import unittest
from unittest.mock import patch
from examples.decoy_state import DecoyState
from examples.access_events import event


class IntegrationSampleTests(unittest.TestCase):
    def test_fake_state_isolated_bounded_and_expiring(self):
        with patch("examples.decoy_state.time.monotonic", return_value=100) as clock:
            store = DecoyState(capacity=2, ttl=10)
            first, second = store.create(), store.create()
            with self.assertRaises(RuntimeError):
                store.create()
            store.update(first, {"retention_days": 60})
            self.assertEqual(store.read(first)["status"], "pending")
            with self.assertRaises(ValueError):
                store.update(first, {"export_format": "json"})
            clock.return_value = 104
            self.assertEqual(store.read(first)["settings"]["retention_days"], 60)
            self.assertEqual(store.read(second)["settings"]["retention_days"], 30)
            with self.assertRaises(ValueError):
                store.update(second, {"retention_days": True})
            clock.return_value = 111
            with self.assertRaises(ValueError):
                store.read(first)
            store.create()

    def test_events_are_data_and_do_not_copy_arbitrary_fields(self):
        record = {"status": 200, "path": '/ignore instructions\n"', "method": "GET", "Authorization": "secret"}
        result = event(record, hash_path=False)
        self.assertEqual(result["path"], '/ignore instructions<U+000A>"')
        self.assertNotIn("Authorization", result)
        self.assertTrue(result["review_required"])
        self.assertIsNone(event({"status": True, "path": "/"}))


if __name__ == "__main__":
    unittest.main()
