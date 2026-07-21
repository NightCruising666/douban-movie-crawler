import csv
import os
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import saver


class SaverTests(unittest.TestCase):
    def test_append_rejects_old_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "movies.csv")
            with open(path, "w", encoding="utf-8-sig", newline="") as file:
                csv.writer(file).writerow(["电影名称"])
            with mock.patch.object(saver, "ensure_data_dir", return_value=directory):
                with self.assertRaises(ValueError):
                    saver.append_to_csv(
                        [{"豆瓣ID": "1", "电影名称": "A"}],
                        "data/movies.csv",
                        ["豆瓣ID", "电影名称"],
                    )

    def test_append_writes_header_once(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(saver, "ensure_data_dir", return_value=directory):
                fields = ["豆瓣ID", "电影名称"]
                saver.append_to_csv([{"豆瓣ID": "1", "电影名称": "A"}], "movies.csv", fields)
                saver.append_to_csv([{"豆瓣ID": "2", "电影名称": "B"}], "movies.csv", fields)
                with open(os.path.join(directory, "movies.csv"), encoding="utf-8-sig") as file:
                    rows = list(csv.reader(file))
                self.assertEqual(rows, [fields, ["1", "A"], ["2", "B"]])


if __name__ == "__main__":
    unittest.main()
