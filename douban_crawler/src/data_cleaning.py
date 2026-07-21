"""新版电影与短评数据清洗。

输出：
  data/processed/movies_cleaned.csv
  data/processed/reviews_cleaned.csv
  data/processed/review_metrics.csv
"""

from __future__ import annotations

import math
import os
from datetime import datetime

import numpy as np
import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少数据文件: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"豆瓣ID": "string", "短评ID": "string"})


def classify_origin(countries: object) -> str:
    parts = {part.strip() for part in str(countries).split("/") if part.strip() and part.strip() != "nan"}
    mainland = "中国大陆" in parts
    greater_china = bool(parts & {"中国香港", "中国台湾", "中国澳门"})
    foreign = bool(parts - {"中国大陆", "中国香港", "中国台湾", "中国澳门"})
    if mainland and foreign:
        return "合拍"
    if mainland:
        return "中国大陆"
    if greater_china and not foreign:
        return "港澳台"
    if foreign:
        return "进口"
    return "未知"


def clean_movies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates(subset=["豆瓣ID"], keep="last")

    for column in ["豆瓣评分", "评价人数", "短评总数", "长评总数", "上映年份"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df.loc[~df["豆瓣评分"].between(0, 10), "豆瓣评分"] = np.nan
    current_year = datetime.now().year + 1
    df.loc[~df["上映年份"].between(1888, current_year), "上映年份"] = np.nan

    for column in ["评价人数", "短评总数", "长评总数", "上映年份"]:
        df[column] = df[column].round().astype("Int64")

    df["片长分钟"] = pd.to_numeric(
        df["片长"].astype("string").str.extract(r"(\d+)", expand=False), errors="coerce"
    ).astype("Int64")
    df["首映日期"] = pd.to_datetime(df["首映日期"], errors="coerce")
    df["采集时间"] = pd.to_datetime(df["采集时间"], errors="coerce", utc=True)
    df["产地分类"] = df["国家/地区"].map(classify_origin)

    rating_count = df["评价人数"].astype("Float64")
    df["短评参与率"] = df["短评总数"].astype("Float64") / rating_count.replace(0, np.nan)
    df["长评参与率"] = df["长评总数"].astype("Float64") / rating_count.replace(0, np.nan)

    valid = df.dropna(subset=["豆瓣评分", "评价人数"])
    overall_mean = valid["豆瓣评分"].mean()
    minimum_votes = valid["评价人数"].median()
    votes = df["评价人数"].astype("Float64")
    df["贝叶斯加权评分"] = (
        votes / (votes + minimum_votes) * df["豆瓣评分"]
        + minimum_votes / (votes + minimum_votes) * overall_mean
    )
    return df


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates(subset=["短评ID", "采样方式"], keep="last")
    df["评分值"] = pd.to_numeric(df["评分"].astype("string").str.extract(r"(\d+)", expand=False), errors="coerce")
    df.loc[~df["评分值"].between(1, 5), "评分值"] = np.nan
    df["有用数"] = pd.to_numeric(df["有用数"], errors="coerce").fillna(0).clip(lower=0).astype("Int64")
    df["排序位置"] = pd.to_numeric(df["排序位置"], errors="coerce").astype("Int64")
    df["评论时间"] = pd.to_datetime(df["评论时间"], errors="coerce")
    df["采集时间"] = pd.to_datetime(df["采集时间"], errors="coerce", utc=True)
    return df


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (math.nan, math.nan)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (center - margin, center + margin)


def review_metrics(reviews: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = reviews.dropna(subset=["评分值"]).groupby(["豆瓣ID", "电影名称", "采样方式"], dropna=False)
    for (movie_id, title, sample_type), group in grouped:
        ratings = group["评分值"].astype(float)
        useful = group["有用数"].astype(float)
        raw_weights = useful + 1
        log_weights = np.log1p(useful) + 1
        five_stars = int((ratings == 5).sum())
        low, high = wilson_interval(five_stars, len(ratings))
        probabilities = ratings.value_counts(normalize=True)
        entropy = float(-(probabilities * np.log2(probabilities)).sum())
        rows.append(
            {
                "豆瓣ID": movie_id,
                "电影名称": title,
                "采样方式": sample_type,
                "有效评分样本数": len(ratings),
                "平均星级": ratings.mean(),
                "原始有用数加权星级": np.average(ratings, weights=raw_weights),
                "对数有用数加权星级": np.average(ratings, weights=log_weights),
                "五星样本占比": five_stars / len(ratings),
                "五星占比95%CI下限": low,
                "五星占比95%CI上限": high,
                "星级分布熵": entropy,
            }
        )
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, filename: str) -> str:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已保存: {path} ({len(df)} 条)")
    return path


def run_full_cleaning() -> None:
    movies = clean_movies(load_csv("movies.csv"))
    save(movies, "movies_cleaned.csv")

    reviews_path = os.path.join(DATA_DIR, "reviews.csv")
    if os.path.exists(reviews_path):
        reviews = clean_reviews(load_csv("reviews.csv"))
        save(reviews, "reviews_cleaned.csv")
        save(review_metrics(reviews), "review_metrics.csv")
    else:
        print("尚未找到 reviews.csv，本次只清洗电影表。")


if __name__ == "__main__":
    run_full_cleaning()
