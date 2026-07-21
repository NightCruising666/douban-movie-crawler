import unittest
from unittest import mock

from douban_crawler import run_batch


class RunBatchTests(unittest.TestCase):
    @mock.patch.object(run_batch.time, "sleep")
    @mock.patch.object(run_batch.config, "random_delay", return_value=123.0)
    @mock.patch.object(run_batch, "parse_movie_detail_with_reason")
    def test_failure_cools_down_then_retries(self, parse_detail, random_delay, sleep):
        expected = {"豆瓣ID": "1"}
        parse_detail.side_effect = [(None, "HTTP 400"), (expected, "")]

        actual, attempts = run_batch.fetch_detail_with_cooldown(
            "1", failure_retries=1, failure_cooldown_base=900
        )

        self.assertEqual(actual, expected)
        self.assertEqual([row["失败原因"] for row in attempts], ["HTTP 400"])
        self.assertEqual(parse_detail.call_count, 2)
        random_delay.assert_called_once_with(900)
        sleep.assert_called_once_with(123.0)

    @mock.patch.object(run_batch.time, "sleep")
    @mock.patch.object(
        run_batch, "parse_movie_detail_with_reason", return_value=(None, "网络请求失败")
    )
    def test_zero_retries_returns_without_sleeping(self, parse_detail, sleep):
        actual, attempts = run_batch.fetch_detail_with_cooldown(
            "1", failure_retries=0, failure_cooldown_base=900
        )

        self.assertIsNone(actual)
        self.assertEqual([row["失败原因"] for row in attempts], ["网络请求失败"])
        parse_detail.assert_called_once()
        self.assertEqual(parse_detail.call_args.args, ("1",))
        self.assertIn("failure_audit", parse_detail.call_args.kwargs)
        sleep.assert_not_called()

    @mock.patch.object(run_batch.time, "sleep", side_effect=KeyboardInterrupt)
    @mock.patch.object(
        run_batch, "parse_movie_detail_with_reason", return_value=(None, "HTTP 400")
    )
    def test_failure_is_persisted_before_long_cooldown(self, parse_detail, sleep):
        recorder = mock.Mock()

        with self.assertRaises(KeyboardInterrupt):
            run_batch.fetch_detail_with_cooldown(
                "1",
                failure_retries=1,
                failure_cooldown_base=900,
                on_failed_attempt=recorder,
            )

        recorder.assert_called_once()
        self.assertEqual(recorder.call_args.args[0], 1)
        self.assertEqual(recorder.call_args.args[1]["失败原因"], "HTTP 400")

    def test_failure_limit_does_not_stop_inside_protection_window(self):
        self.assertFalse(run_batch.should_stop_after_failures(3, 3, 2.9 * 3600, 3))

    def test_failure_limit_stops_after_protection_window(self):
        self.assertTrue(run_batch.should_stop_after_failures(3, 3, 3 * 3600, 3))

    def test_continuous_flag_is_accepted(self):
        args = run_batch.parse_args(["--never-stop-on-failure"])
        self.assertTrue(args.never_stop_on_failure)

    def test_round_number_defaults_to_persistent_auto_assignment(self):
        args = run_batch.parse_args([])
        self.assertIsNone(args.round_number)

    @mock.patch.object(run_batch, "run_one_batch", return_value=0)
    @mock.patch.object(run_batch.detail_state, "Stage2WriteLock")
    def test_write_mode_acquires_shared_stage2_lock(self, lock, run_one_batch):
        self.assertEqual(run_batch.main([]), 0)
        lock.assert_called_once_with()
        run_one_batch.assert_called_once()

    @mock.patch.object(run_batch, "run_one_batch", return_value=0)
    @mock.patch.object(run_batch.detail_state, "Stage2WriteLock")
    def test_status_mode_is_read_only_and_does_not_lock(self, lock, run_one_batch):
        self.assertEqual(run_batch.main(["--status"]), 0)
        lock.assert_not_called()
        run_one_batch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
