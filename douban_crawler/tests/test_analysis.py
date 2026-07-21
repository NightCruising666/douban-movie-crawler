import unittest

import pandas as pd

from douban_crawler.run_analysis import cohens_d, spearman_without_scipy, weighted_genre_rows


class AnalysisTests(unittest.TestCase):
    def test_genre_weights_sum_to_one_per_movie(self):
        movies = pd.DataFrame(
            [
                {
                    "豆瓣ID": "1",
                    "上映年份": 2020,
                    "类型": "剧情 / 喜剧",
                    "产地分类": "中国大陆",
                    "豆瓣评分": 8.0,
                    "评价人数": 100,
                },
                {
                    "豆瓣ID": "2",
                    "上映年份": 2021,
                    "类型": "",
                    "产地分类": "进口",
                    "豆瓣评分": 7.0,
                    "评价人数": 50,
                },
            ]
        )
        expanded = weighted_genre_rows(movies)
        totals = expanded.groupby("豆瓣ID")["类型权重"].sum()
        self.assertAlmostEqual(totals["1"], 1.0)
        self.assertAlmostEqual(totals["2"], 1.0)
        self.assertIn("未知", set(expanded["类型"]))

    def test_spearman_is_monotonic(self):
        value = spearman_without_scipy(pd.Series([1, 2, 3]), pd.Series([10, 20, 30]))
        self.assertAlmostEqual(value, 1.0)

    def test_cohens_d_requires_two_values_per_group(self):
        self.assertTrue(pd.isna(cohens_d(pd.Series([1]), pd.Series([2, 3]))))


if __name__ == "__main__":
    unittest.main()
