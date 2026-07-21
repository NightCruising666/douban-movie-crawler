import unittest
from unittest import mock

from douban_crawler import main


class MainTests(unittest.TestCase):
    @mock.patch.object(main, "run_stage1_locked")
    @mock.patch.object(main.detail_state, "Stage2WriteLock")
    def test_stage1_uses_shared_stage2_lock(self, lock, run_stage1_locked):
        main.run_stage1(rebuild=True)

        lock.assert_called_once_with()
        run_stage1_locked.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
