import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.data_cleaning import classify_origin, clean_movies, clean_reviews, review_metrics


class CleaningTests(unittest.TestCase):
    def test_origin_classification(self):
        self.assertEqual(classify_origin("中国大陆"), "中国大陆")
        self.assertEqual(classify_origin("中国大陆 / 美国"), "合拍")
        self.assertEqual(classify_origin("中国香港"), "港澳台")
        self.assertEqual(classify_origin("日本"), "进口")

    def test_cleaning_and_metrics(self):
        movies = pd.DataFrame(
            [
                {
                    "豆瓣ID": "1", "电影名称": "A", "原始片名": "A", "导演": "D", "主演": "C",
                    "上映年份": "2020", "首映日期": "2020-01-01", "类型": "剧情", "国家/地区": "中国大陆",
                    "片长": "120分钟", "豆瓣评分": "8.0", "评价人数": "100", "短评总数": "20",
                    "长评总数": "2", "采集时间": "2026-01-01T00:00:00+08:00",
                },
                {
                    "豆瓣ID": "2", "电影名称": "B", "原始片名": "B", "导演": "D", "主演": "C",
                    "上映年份": "2021", "首映日期": "2021-01-01", "类型": "喜剧", "国家/地区": "美国",
                    "片长": "90分钟", "豆瓣评分": "6.0", "评价人数": "10", "短评总数": "5",
                    "长评总数": "1", "采集时间": "2026-01-01T00:00:00+08:00",
                },
            ]
        )
        cleaned_movies = clean_movies(movies)
        self.assertAlmostEqual(cleaned_movies.loc[0, "短评参与率"], 0.2)
        self.assertIn("贝叶斯加权评分", cleaned_movies)

        reviews = pd.DataFrame(
            [
                {"短评ID": "r1", "豆瓣ID": "1", "电影名称": "A", "用户匿名标识": "x", "评分": "5星", "短评正文": "x", "有用数": "9", "评论时间": "2025-01-01", "采样方式": "热门", "排序位置": "1", "采集时间": "2026-01-01T00:00:00+08:00"},
                {"短评ID": "r2", "豆瓣ID": "1", "电影名称": "A", "用户匿名标识": "y", "评分": "3星", "短评正文": "y", "有用数": "0", "评论时间": "2025-01-02", "采样方式": "热门", "排序位置": "2", "采集时间": "2026-01-01T00:00:00+08:00"},
            ]
        )
        metrics = review_metrics(clean_reviews(reviews))
        self.assertEqual(len(metrics), 1)
        self.assertGreater(metrics.loc[0, "原始有用数加权星级"], metrics.loc[0, "平均星级"])


if __name__ == "__main__":
    unittest.main()
