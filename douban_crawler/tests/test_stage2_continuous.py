import unittest
import tempfile
from pathlib import Path
from unittest import mock

from douban_crawler import run_stage2_continuous
from douban_crawler.src import detail_state


class Stage2ContinuousTests(unittest.TestCase):
    @mock.patch.object(run_stage2_continuous.run_batch, "load_unavailable_ids", return_value={"2"})
    @mock.patch.object(run_stage2_continuous.run_batch, "load_collected_ids", return_value={"1"})
    @mock.patch.object(
        run_stage2_continuous.run_batch,
        "load_raw_movies",
        return_value=[{"豆瓣ID": "1"}, {"豆瓣ID": "2"}, {"豆瓣ID": "3"}],
    )
    def test_progress_separates_success_and_unavailable(self, raw, collected, unavailable):
        self.assertEqual(run_stage2_continuous.progress(), (1, 1, 3))

    def test_single_instance_lock_rejects_second_live_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stage2.lock"
            with detail_state.Stage2WriteLock(path):
                with self.assertRaises(RuntimeError):
                    with detail_state.Stage2WriteLock(path):
                        pass


if __name__ == "__main__":
    unittest.main()
