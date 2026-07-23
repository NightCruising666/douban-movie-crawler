import os
import sys
import unittest

import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.data_cleaning import (
    classify_origin,
    clean_movies,
    clean_movies_with_audit,
    clean_reviews,
    review_metrics,
)


def movie_row(**overrides) -> dict:
    row = {
        "豆瓣ID": "1",
        "电影名称": " A ",
        "原始片名": "A",
        "导演": "D",
        "主演": "C",
        "上映年份": "2020",
        "首映日期": "2020-01-01",
        "类型": "剧情 / 剧情 / 爱情",
        "国家/地区": "中国大陆 / 美国",
        "片长": "120分钟",
        "豆瓣评分": "8.0",
        "评价人数": "100",
        "短评总数": "20",
        "长评总数": "2",
        "采集时间": "2026-01-01T00:00:00+08:00",
    }
    row.update(overrides)
    return row


class CleaningTests(unittest.TestCase):
    def test_origin_classification(self):
        self.assertEqual(classify_origin("中国大陆"), "中国大陆")
        self.assertEqual(classify_origin("中国大陆 / 美国"), "合拍")
        self.assertEqual(classify_origin("中国大陆 / 中国香港"), "合拍")
        self.assertEqual(classify_origin("中国香港"), "港澳台")
        self.assertEqual(classify_origin("中国台湾 / 日本"), "合拍")
        self.assertEqual(classify_origin("日本"), "进口")
        self.assertEqual(classify_origin(pd.NA), "未知")

    def test_schema_validation_lists_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "缺少必需字段.*评价人数"):
            clean_movies(pd.DataFrame([movie_row()]).drop(columns=["评价人数"]))

    def test_duplicate_id_keeps_latest_capture_and_normalizes_multivalue_fields(self):
        old = movie_row(电影名称="旧名称", 采集时间="2025-01-01T00:00:00+08:00")
        latest = movie_row(电影名称=" 新名称 ", 采集时间="2026-01-01T00:00:00+08:00")

        cleaned, report, rules = clean_movies_with_audit(pd.DataFrame([latest, old]))

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned.iloc[0]["电影名称"], "新名称")
        self.assertEqual(cleaned.iloc[0]["类型"], "剧情 / 爱情")
        self.assertEqual(cleaned.iloc[0]["类型数"], 2)
        self.assertEqual(cleaned.iloc[0]["主类型"], "剧情")
        self.assertEqual(cleaned.iloc[0]["产地分类"], "合拍")
        self.assertEqual(
            int(report.loc[report["指标"] == "重复豆瓣ID记录数", "数量"].iloc[0]), 1
        )
        self.assertEqual(
            int(rules.loc[rules["规则ID"] == "R02", "命中记录数"].iloc[0]), 1
        )

    def test_zero_rating_is_missing_not_zero_or_mean_imputed(self):
        frame = pd.DataFrame(
            [
                movie_row(
                    豆瓣ID="1",
                    豆瓣评分="0",
                    评价人数="0",
                    短评总数="10",
                    长评总数="1",
                ),
                movie_row(豆瓣ID="2", 豆瓣评分="8.0", 评价人数="100"),
            ]
        )

        cleaned, report, _ = clean_movies_with_audit(frame)
        unrated = cleaned.loc[cleaned["豆瓣ID"] == "1"].iloc[0]

        self.assertTrue(pd.isna(unrated["豆瓣评分"]))
        self.assertFalse(bool(unrated["纳入评分分析"]))
        self.assertTrue(pd.isna(unrated["短评参与率"]))
        self.assertIn("无有效评分", unrated["数据质量标记"])
        self.assertIn("无评分但有短评", unrated["数据质量标记"])
        self.assertEqual(
            int(report.loc[report["指标"] == "无有效评分记录数", "数量"].iloc[0]), 1
        )

    def test_invalid_counts_are_missing_instead_of_rounded_or_clipped(self):
        frame = pd.DataFrame(
            [
                movie_row(
                    评价人数="-1",
                    短评总数="1.5",
                    长评总数="not-a-number",
                )
            ]
        )

        cleaned = clean_movies(frame)

        self.assertTrue(pd.isna(cleaned.iloc[0]["评价人数"]))
        self.assertTrue(pd.isna(cleaned.iloc[0]["短评总数"]))
        self.assertTrue(pd.isna(cleaned.iloc[0]["长评总数"]))
        self.assertIn("计数字段异常", cleaned.iloc[0]["数据质量标记"])

    def test_missing_runtime_is_reported_and_not_invented(self):
        cleaned, report, _ = clean_movies_with_audit(
            pd.DataFrame([movie_row(片长=pd.NA)])
        )

        self.assertTrue(pd.isna(cleaned.iloc[0]["片长分钟"]))
        self.assertIn("片长缺失或异常", cleaned.iloc[0]["数据质量标记"])
        self.assertEqual(
            int(
                report.loc[
                    report["指标"] == "片长缺失或异常记录数", "数量"
                ].iloc[0]
            ),
            1,
        )

    def test_release_date_precision_is_preserved_without_inventing_day(self):
        frame = pd.DataFrame(
            [
                movie_row(豆瓣ID="1", 首映日期="2020-01-02"),
                movie_row(豆瓣ID="2", 首映日期="2020-01"),
                movie_row(豆瓣ID="3", 首映日期="2020"),
                movie_row(豆瓣ID="4", 首映日期="unknown"),
                movie_row(豆瓣ID="5", 首映日期="0000"),
                movie_row(豆瓣ID="6", 首映日期="9999-01"),
            ]
        )

        cleaned = clean_movies(frame).set_index("豆瓣ID")

        self.assertEqual(cleaned.loc["1", "首映日期精度"], "日")
        self.assertEqual(cleaned.loc["1", "首映日期标准化"], "2020-01-02")
        self.assertEqual(cleaned.loc["2", "首映日期精度"], "月")
        self.assertTrue(pd.isna(cleaned.loc["2", "首映日期标准化"]))
        self.assertEqual(cleaned.loc["3", "首映日期精度"], "年")
        self.assertEqual(cleaned.loc["4", "首映日期精度"], "异常")
        self.assertEqual(cleaned.loc["5", "首映日期精度"], "异常")
        self.assertEqual(cleaned.loc["6", "首映日期精度"], "异常")

    def test_missing_and_invalid_years_are_reported_separately(self):
        frame = pd.DataFrame(
            [
                movie_row(豆瓣ID="1", 上映年份=pd.NA),
                movie_row(豆瓣ID="2", 上映年份="1800"),
            ]
        )

        cleaned, report, _ = clean_movies_with_audit(frame)

        self.assertIn("上映年份缺失", cleaned.iloc[0]["数据质量标记"])
        self.assertNotIn("上映年份异常", cleaned.iloc[0]["数据质量标记"])
        self.assertIn("上映年份异常", cleaned.iloc[1]["数据质量标记"])
        self.assertEqual(
            int(report.loc[report["指标"] == "上映年份缺失记录数", "数量"].iloc[0]),
            1,
        )
        self.assertEqual(
            int(report.loc[report["指标"] == "上映年份异常记录数", "数量"].iloc[0]),
            1,
        )

    def test_invalid_capture_time_is_flagged_and_valid_time_wins_deduplication(self):
        frame = pd.DataFrame(
            [
                movie_row(电影名称="无效时间", 采集时间="not-a-time"),
                movie_row(电影名称="有效时间", 采集时间="2026-01-01T00:00:00+08:00"),
                movie_row(豆瓣ID="2", 采集时间="not-a-time"),
                movie_row(豆瓣ID="3", 采集时间="2026-01-01 12:00:00"),
                movie_row(豆瓣ID="4", 采集时间=pd.NA),
            ]
        )

        cleaned, report, rules = clean_movies_with_audit(frame)

        self.assertEqual(cleaned.loc[cleaned["豆瓣ID"] == "1", "电影名称"].iloc[0], "有效时间")
        invalid = cleaned.loc[cleaned["豆瓣ID"] == "2"].iloc[0]
        self.assertIn("采集时间异常", invalid["数据质量标记"])
        naive = cleaned.loc[cleaned["豆瓣ID"] == "3"].iloc[0]
        self.assertIn("采集时间异常", naive["数据质量标记"])
        missing = cleaned.loc[cleaned["豆瓣ID"] == "4"].iloc[0]
        self.assertIn("采集时间缺失", missing["数据质量标记"])
        self.assertEqual(
            int(report.loc[report["指标"] == "采集时间异常记录数", "数量"].iloc[0]),
            2,
        )
        self.assertEqual(
            int(report.loc[report["指标"] == "采集时间缺失记录数", "数量"].iloc[0]),
            1,
        )
        self.assertIn("统计口径", report.columns)
        self.assertIn("命中类型", rules.columns)

    def test_release_year_limit_uses_source_local_year_not_utc_year(self):
        frame = pd.DataFrame(
            [
                movie_row(
                    豆瓣ID="1",
                    上映年份="2025",
                    采集时间="2024-01-01T00:00:00+08:00",
                ),
                movie_row(
                    豆瓣ID="2",
                    上映年份="2026",
                    采集时间="2024-12-31T23:30:00-08:00",
                ),
            ]
        )

        cleaned = clean_movies(frame).set_index("豆瓣ID")

        self.assertEqual(cleaned.loc["1", "上映年份"], 2025)
        self.assertTrue(pd.isna(cleaned.loc["2", "上映年份"]))
        self.assertIn("上映年份异常", cleaned.loc["2", "数据质量标记"])

    def test_all_invalid_capture_times_use_documented_secondary_fallback(self):
        frame = pd.DataFrame(
            [
                movie_row(豆瓣ID="1", 上映年份="2027", 采集时间="invalid"),
                movie_row(豆瓣ID="2", 上映年份="2028", 采集时间="invalid"),
            ]
        )

        cleaned = clean_movies(frame).set_index("豆瓣ID")

        self.assertEqual(cleaned.loc["1", "上映年份"], 2027)
        self.assertTrue(pd.isna(cleaned.loc["2", "上映年份"]))

    def test_analysis_scope_flags_and_bayesian_shrinkage(self):
        frame = pd.DataFrame(
            [
                movie_row(豆瓣ID="1", 上映年份="2020", 豆瓣评分="9", 评价人数="10"),
                movie_row(豆瓣ID="2", 上映年份="1990", 豆瓣评分="8", 评价人数="1000"),
                movie_row(豆瓣ID="3", 上映年份="2021", 豆瓣评分="7", 评价人数="1000"),
            ]
        )

        cleaned = clean_movies(frame).set_index("豆瓣ID")

        self.assertTrue(bool(cleaned.loc["1", "纳入评分分析"]))
        self.assertTrue(bool(cleaned.loc["1", "纳入类型趋势分析"]))
        self.assertFalse(bool(cleaned.loc["2", "纳入类型趋势分析"]))
        self.assertLess(cleaned.loc["1", "贝叶斯加权评分"], cleaned.loc["1", "豆瓣评分"])
        self.assertAlmostEqual(cleaned.loc["1", "短评参与率"], 2.0)

    def test_review_cleaning_and_metrics(self):
        reviews = pd.DataFrame(
            [
                {
                    "短评ID": "r1", "豆瓣ID": "1", "电影名称": "A", "评分": "5星",
                    "短评正文": "x", "有用数": "9", "评论时间": "2025-01-01",
                    "采样方式": "热门", "排序位置": "1",
                    "采集时间": "2026-01-01T00:00:00+08:00",
                },
                {
                    "短评ID": "r2", "豆瓣ID": "1", "电影名称": "A", "评分": "3星",
                    "短评正文": "y", "有用数": "0", "评论时间": "2025-01-02",
                    "采样方式": "热门", "排序位置": "2",
                    "采集时间": "2026-01-01T00:00:00+08:00",
                },
            ]
        )

        metrics = review_metrics(clean_reviews(reviews))

        self.assertEqual(len(metrics), 1)
        self.assertGreater(
            metrics.loc[0, "原始有用数加权星级"], metrics.loc[0, "平均星级"]
        )


if __name__ == "__main__":
    unittest.main()
