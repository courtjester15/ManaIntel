import unittest
from unittest.mock import patch, Mock
from ffw.capacity import CapacityStopped
from tools.quality_comparison import request_cap


class QualityBudgetTests(unittest.TestCase):
    def test_schema_and_split_calls_share_one_cap_and_restore_normal_guard(self):
        from ffw import capacity
        normal = Mock(return_value="ticket")
        with patch.object(capacity, "reserve", normal):
            with request_cap(2):
                capacity.reserve("lite")
                capacity.reserve("flash")
                capacity.reserve("lite", check_only=True)
                with self.assertRaisesRegex(CapacityStopped, "aggregate"):
                    capacity.reserve("lite")
            self.assertIs(normal, capacity.reserve)
            self.assertEqual(3, normal.call_count)

    def test_original_daily_capacity_refusal_does_not_consume_a_request(self):
        from ffw import capacity
        with patch.object(capacity, "reserve", side_effect=[CapacityStopped("daily"), "ticket"]):
            with request_cap(1):
                with self.assertRaisesRegex(CapacityStopped, "daily"):
                    capacity.reserve("lite")
                self.assertEqual("ticket", capacity.reserve("lite"))
