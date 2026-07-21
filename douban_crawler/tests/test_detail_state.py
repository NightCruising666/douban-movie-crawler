import tempfile
import unittest
from pathlib import Path
from unittest import mock

from douban_crawler.src import detail_state


class DetailStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.data_dir_patch = mock.patch.object(detail_state, "DATA_DIR", Path(self.tempdir.name))
        self.data_dir_patch.start()

    def tearDown(self):
        self.data_dir_patch.stop()
        self.tempdir.cleanup()

    def test_two_distinct_permanent_failure_rounds_mark_unavailable(self):
        first = detail_state.record_failure("1", "电影", "HTTP 400", 1, "2026-01-01T00:00:00+08:00")
        repeated = detail_state.record_failure("1", "电影", "HTTP 400", 1, "2026-01-01T00:10:00+08:00")
        second = detail_state.record_failure("1", "电影", "HTTP 400", 2, "2026-01-02T00:00:00+08:00")

        self.assertEqual(first["状态"], "待复核")
        self.assertEqual(repeated["失败轮次数"], "1")
        self.assertEqual(second["永久失败轮次数"], "2")
        self.assertEqual(second["状态"], "不可用")
        self.assertEqual(detail_state.load_unavailable_ids(), {"1"})

    def test_temporary_errors_never_become_permanently_unavailable(self):
        detail_state.record_failure("2", "电影", "HTTP 429", 1, "2026-01-01T00:00:00+08:00")
        state = detail_state.record_failure("2", "电影", "网络请求失败", 2, "2026-01-02T00:00:00+08:00")

        self.assertEqual(state["永久失败轮次数"], "0")
        self.assertEqual(state["状态"], "待复核")
        self.assertNotIn("2", detail_state.load_unavailable_ids())

    def test_success_marks_previous_failure_as_recovered(self):
        detail_state.record_failure("3", "电影", "HTTP 400", 1, "2026-01-01T00:00:00+08:00")
        detail_state.mark_success("3", "2026-01-01T01:00:00+08:00")

        record = detail_state.load_failure_records()["3"]
        self.assertEqual(record["状态"], "已恢复")
        self.assertNotIn("3", detail_state.load_unavailable_ids())

    def test_temporary_round_breaks_permanent_failure_streak(self):
        detail_state.record_failure("5", "电影", "HTTP 400", 1, "2026-01-01T00:00:00+08:00")
        detail_state.record_failure("5", "电影", "HTTP 429", 2, "2026-01-02T00:00:00+08:00")
        state = detail_state.record_failure("5", "电影", "HTTP 400", 3, "2026-01-03T00:00:00+08:00")

        self.assertEqual(state["永久失败轮次数"], "2")
        self.assertEqual(state["连续永久失败轮次数"], "1")
        self.assertEqual(state["状态"], "待复核")

    def test_next_round_number_survives_restart(self):
        self.assertEqual(detail_state.next_round_number(), 1)
        detail_state.record_failure("4", "电影", "HTTP 400", 3, "2026-01-01T00:00:00+08:00")
        self.assertEqual(detail_state.next_round_number(), 4)


if __name__ == "__main__":
    unittest.main()
