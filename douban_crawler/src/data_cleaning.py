"""
数据清洗模块
===========
对豆瓣电影采集数据进行清洗、转换、标准化。

清洗流程:
  1. 加载CSV → DataFrame
  2. 缺失值检测与处理
  3. 数据类型转换（字符串→数字）
  4. 异常值检测（评分超出范围、年份异常等）
  5. 重复记录检测
  6. 字段标准化（年份格式统一、类型拆分等）
  7. 输出清洗报告 + 保存清洗后CSV

知识点:
  - pandas.read_csv: 加载CSV
  - df.isnull().sum(): 统计缺失值
  - df.astype(): 类型转换
  - df.duplicated(): 重复检测
  - df.describe(): 描述性统计
"""

import pandas as pd
import numpy as np
import os
import sys

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")


def load_data(csv_path=None):
    """
    加载采集的CSV数据。

    参数:
        csv_path: CSV文件路径，默认为 data/movies.csv

    返回:
        pd.DataFrame
    """
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, "movies.csv")
    elif not os.path.isabs(csv_path):
        csv_path = os.path.join(DATA_DIR, csv_path)

    print(f"加载数据: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    print(f"  行数: {len(df)}, 列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")
    return df


def inspect_missing(df):
    """
    检查缺失值。

    豆瓣API返回的数据可能包含:
    - 空字符串 ""（某些字段无数据）
    - NaN（pandas解析时的空值）
    - "未知" 等占位文本

    返回:
        dict: 每列的缺失统计
    """
    print("\n" + "=" * 50)
    print("缺失值检查")
    print("=" * 50)

    report = {}
    for col in df.columns:
        # 空字符串 + NaN 都算缺失
        null_count = df[col].isna().sum()
        empty_count = (df[col].astype(str).str.strip() == "").sum()
        total_missing = null_count + empty_count

        report[col] = {
            "NaN": null_count,
            "空字符串": empty_count,
            "缺失合计": total_missing,
            "缺失比例": f"{total_missing / len(df) * 100:.1f}%"
        }

        if total_missing > 0:
            print(f"  ✗ {col}: 缺失 {total_missing} 条 ({total_missing / len(df) * 100:.1f}%)")

    if all(v["缺失合计"] == 0 for v in report.values()):
        print("  ✓ 无缺失值")

    return report


def clean_movies(df):
    """
    清洗电影数据。

    处理:
    - 豆瓣评分 → float
    - 评价人数 → int
    - 上映年份 → int
    - 导演/主演/类型中的空值 → "未知"
    - 五星占比 → 暂保留（API未返回）

    返回:
        pd.DataFrame: 清洗后的数据
    """
    print("\n" + "=" * 50)
    print("数据清洗")
    print("=" * 50)

    df = df.copy()

    # ---- 1. 豆瓣评分 → float ----
    # 原始格式: "7.7"（字符串）
    df["豆瓣评分"] = pd.to_numeric(df["豆瓣评分"], errors="coerce")
    invalid_scores = df[df["豆瓣评分"].isna() & (df["电影名称"].notna())]
    if len(invalid_scores) > 0:
        print(f"  ⚠ {len(invalid_scores)} 条评分为无效值，已置为 NaN")

    # 评分范围检查：豆瓣评分 1.0 ~ 10.0
    out_of_range = df[(df["豆瓣评分"] < 1.0) | (df["豆瓣评分"] > 10.0)]
    if len(out_of_range) > 0:
        print(f"  ⚠ {len(out_of_range)} 条评分超出范围(1-10)，标记为异常")

    # ---- 2. 评价人数 → int ----
    # 原始格式: "15087"（字符串）
    df["评价人数"] = pd.to_numeric(df["评价人数"], errors="coerce").astype("Int64")
    # Int64 支持 NaN，普通 int 不支持

    # ---- 3. 上映年份 → int ----
    df["上映年份"] = pd.to_numeric(df["上映年份"], errors="coerce").astype("Int64")
    # 年份范围检查：合理范围 1900 ~ 当前
    current_year = 2026
    bad_years = df[(df["上映年份"] < 1900) | (df["上映年份"] > current_year)]
    if len(bad_years) > 0:
        print(f"  ⚠ {len(bad_years)} 条年份异常（<1900 或 >{current_year}）")

    # ---- 4. 空字符串 → "未知" ----
    for col in ["导演", "主演", "类型", "国家/地区", "片长"]:
        empty_mask = df[col].astype(str).str.strip().isin(["", "nan", "NaN", "None"])
        count = empty_mask.sum()
        if count > 0:
            df.loc[empty_mask, col] = "未知"
            print(f"  {col}: {count} 条空值 → '未知'")

    print(f"  ✓ 清洗完成")
    return df


def clean_reviews(df):
    """
    清洗短评数据。

    处理:
    - 有用数 → int
    - 评论时间 → datetime
    - 评分 → 数值（"5星" → 5）
    - 空短评正文 → 标记

    返回:
        pd.DataFrame: 清洗后的数据
    """
    print("\n清洗短评数据...")
    df = df.copy()

    # ---- 1. 有用数 → int ----
    df["有用数"] = pd.to_numeric(df["有用数"], errors="coerce").astype("Int64")

    # ---- 2. 评分 → 数值 ----
    # "5星" → 5, "未评分" → NaN
    df["评分值"] = df["评分"].str.extract(r"(\d+)").astype("Int64")

    # ---- 3. 评论时间 → datetime ----
    df["评论时间"] = pd.to_datetime(df["评论时间"], errors="coerce")

    # ---- 4. 空短评 ----
    empty_reviews = (df["短评正文"].astype(str).str.strip() == "").sum()
    if empty_reviews > 0:
        print(f"  ⚠ {empty_reviews} 条短评正文为空")

    print(f"  ✓ 短评清洗完成")
    return df


def detect_duplicates(df, subset=None):
    """
    检测重复记录。

    参数:
        df:     DataFrame
        subset: 按哪些列判断重复（默认全部列）

    返回:
        int: 重复行数
    """
    print("\n" + "=" * 50)
    print("重复检测")
    print("=" * 50)

    if subset:
        dup_count = df.duplicated(subset=subset, keep="first").sum()
        print(f"  按 {subset} 检测: {dup_count} 条重复")
    else:
        dup_count = df.duplicated(keep="first").sum()
        print(f"  完全重复: {dup_count} 条")

    if dup_count == 0:
        print("  ✓ 无重复记录")

    return dup_count


def summary_statistics(df):
    """
    生成描述性统计。

    针对数值列计算: 均值、中位数、标准差、最小/最大值、四分位数。
    """
    print("\n" + "=" * 50)
    print("描述性统计")
    print("=" * 50)

    numeric_cols = df.select_dtypes(include=["int64", "float64", "Int64"]).columns
    if len(numeric_cols) > 0:
        stats = df[numeric_cols].describe()
        print(stats.to_string())
        return stats
    else:
        print("  无数值列可统计")
        return None


def save_cleaned(df, filename):
    """
    保存清洗后的数据。

    参数:
        df:       DataFrame
        filename: 输出文件名（如 "movies_cleaned.csv"）
    """
    filepath = os.path.join(DATA_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"\n已保存清洗数据: {filepath} ({len(df)} 条)")
    return filepath


def run_full_cleaning():
    """
    一键运行完整清洗流程。

    流程:
      movies.csv  → 清洗 → movies_cleaned.csv
      reviews.csv → 清洗 → reviews_cleaned.csv
    """
    print("=" * 60)
    print("  豆瓣电影数据清洗流程")
    print("=" * 60)

    # ---- 电影数据 ----
    movies_path = os.path.join(DATA_DIR, "movies.csv")
    if os.path.exists(movies_path):
        df_movies = load_data(movies_path)
        inspect_missing(df_movies)
        detect_duplicates(df_movies, subset=["电影名称"])
        df_movies = clean_movies(df_movies)
        summary_statistics(df_movies)
        save_cleaned(df_movies, "movies_cleaned.csv")
    else:
        print(f"\n⚠ {movies_path} 不存在，跳过电影数据清洗")

    # ---- 短评数据 ----
    reviews_path = os.path.join(DATA_DIR, "reviews.csv")
    if os.path.exists(reviews_path):
        print("\n" + "-" * 40)
        df_reviews = load_data(reviews_path)
        inspect_missing(df_reviews)
        detect_duplicates(df_reviews)
        df_reviews = clean_reviews(df_reviews)
        summary_statistics(df_reviews)
        save_cleaned(df_reviews, "reviews_cleaned.csv")
    else:
        print(f"\n⚠ {reviews_path} 不存在，跳过短评数据清洗")

    print("\n" + "=" * 60)
    print("  清洗流程完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_full_cleaning()
