import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import config
from src.parser import anonymize_user, transform_movie_detail, transform_review_item


class ParserTests(unittest.TestCase):
    def test_movie_detail_contract(self):
        data = {
            "title": "测试电影",
            "original_title": "Test Film",
            "year": 2020,
            "release_date": "2020-01-02",
            "genres": ["剧情", "科幻"],
            "countries": ["中国大陆", "美国"],
            "durations": ["120分钟"],
            "directors": [{"name": "导演A"}],
            "actors": [{"name": "演员A"}],
            "rating": {"value": 8.2, "count": 12345},
            "comment_count": 456,
            "review_count": 78,
        }
        record = transform_movie_detail("123", data, "2026-01-01T00:00:00+08:00")
        self.assertEqual(list(record), config.MOVIE_FIELDS)
        self.assertEqual(record["豆瓣ID"], "123")
        self.assertEqual(record["首映日期"], "2020-01-02")
        self.assertEqual(record["短评总数"], "456")

    def test_review_is_anonymized_and_has_composite_key_fields(self):
        item = {
            "id": "review-1",
            "user": {"name": "public-name"},
            "rating": {"value": 5},
            "comment": "很好",
            "vote_count": 12,
            "create_time": "2025-01-01 12:00:00",
        }
        record = transform_review_item(
            "123", "测试电影", item, "热门", 1, "2026-01-01T00:00:00+08:00"
        )
        self.assertEqual(list(record), config.REVIEW_FIELDS)
        self.assertEqual(record["短评ID"], "review-1")
        self.assertNotEqual(record["用户匿名标识"], "public-name")
        self.assertEqual(len(record["用户匿名标识"]), 16)

    def test_anonymization_is_stable(self):
        user = {"id": "u-1", "name": "name"}
        self.assertEqual(anonymize_user(user), anonymize_user(user))


if __name__ == "__main__":
    unittest.main()
