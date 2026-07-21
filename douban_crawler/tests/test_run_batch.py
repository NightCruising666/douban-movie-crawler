import unittest
from unittest import mock

from douban_crawler import run_batch


class RunBatchTests(unittest.TestCase):
    @mock.patch.object(run_batch.time, "sleep")
    @mock.patch.object(run_batch.config, "random_delay", return_value=123.0)
    @mock.patch.object(run_batch, "parse_movie_detail")
    def test_failure_cools_down_then_retries(self, parse_detail, random_delay, sleep):
        expected = {"豆瓣ID": "1"}
        parse_detail.side_effect = [None, expected]

        actual = run_batch.fetch_detail_with_cooldown(
            "1", failure_retries=1, failure_cooldown_base=900
        )

        self.assertEqual(actual, expected)
        self.assertEqual(parse_detail.call_count, 2)
        random_delay.assert_called_once_with(900)
        sleep.assert_called_once_with(123.0)

    @mock.patch.object(run_batch.time, "sleep")
    @mock.patch.object(run_batch, "parse_movie_detail", return_value=None)
    def test_zero_retries_returns_without_sleeping(self, parse_detail, sleep):
        actual = run_batch.fetch_detail_with_cooldown(
            "1", failure_retries=0, failure_cooldown_base=900
        )

        self.assertIsNone(actual)
        parse_detail.assert_called_once_with("1")
        sleep.assert_not_called()

    def test_failure_limit_does_not_stop_inside_protection_window(self):
        self.assertFalse(run_batch.should_stop_after_failures(3, 3, 2.9 * 3600, 3))

    def test_failure_limit_stops_after_protection_window(self):
        self.assertTrue(run_batch.should_stop_after_failures(3, 3, 3 * 3600, 3))


if __name__ == "__main__":
    unittest.main()
