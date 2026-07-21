import unittest
from unittest import mock

from douban_crawler import run_stage2_continuous


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


if __name__ == "__main__":
    unittest.main()
