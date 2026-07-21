"""生成评分稳定性与类型结构分析表、图。

先运行 ``src/data_cleaning.py``。本脚本只读取 ``data/processed``，
所有结果写入 ``data/analysis``，不会修改原始采集文件。
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "data" / "analysis"
YEAR_START = 2005
YEAR_END = 2025


def configure_plots() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams["font.sans-serif"] = [
        "Arial Unicode MS",
        "PingFang SC",
        "Microsoft YaHei",
        "SimHei",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def save_table(frame: pd.DataFrame, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")


def save_figure(filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close()


def spearman_without_scipy(left: pd.Series, right: pd.Series) -> float:
    """通过秩的 Pearson 相关计算 Spearman 系数。"""
    valid = pd.concat([left, right], axis=1).dropna()
    if len(valid) < 2:
        return math.nan
    return float(valid.iloc[:, 0].rank().corr(valid.iloc[:, 1].rank()))


def cohens_d(left: pd.Series, right: pd.Series) -> float:
    """计算两独立样本的 Cohen's d；样本不足时返回 NaN。"""
    left = pd.to_numeric(left, errors="coerce").dropna().astype(float)
    right = pd.to_numeric(right, errors="coerce").dropna().astype(float)
    if len(left) < 2 or len(right) < 2:
        return math.nan
    pooled_var = (
        (len(left) - 1) * left.var(ddof=1) + (len(right) - 1) * right.var(ddof=1)
    ) / (len(left) + len(right) - 2)
    return float((left.mean() - right.mean()) / math.sqrt(pooled_var)) if pooled_var > 0 else math.nan


def weighted_genre_rows(movies: pd.DataFrame) -> pd.DataFrame:
    """将多类型电影展开，并保证每部电影的类型权重之和等于 1。"""
    rows: list[dict] = []
    for _, movie in movies.iterrows():
        genres = [part.strip() for part in str(movie.get("类型", "")).split("/") if part.strip()]
        if not genres:
            genres = ["未知"]
        weight = 1 / len(genres)
        for genre in genres:
            rows.append(
                {
                    "豆瓣ID": movie.get("豆瓣ID"),
                    "上映年份": movie.get("上映年份"),
                    "类型": genre,
                    "类型权重": weight,
                    "产地分类": movie.get("产地分类"),
                    "豆瓣评分": movie.get("豆瓣评分"),
                    "评价人数": movie.get("评价人数"),
                }
            )
    return pd.DataFrame(rows)


def analyze_rating_stability(movies: pd.DataFrame, summary: list[dict]) -> None:
    valid = movies.dropna(subset=["豆瓣评分", "评价人数"]).copy()
    if valid.empty:
        return

    valid["log10评价人数"] = np.log10(valid["评价人数"].astype(float) + 1)
    correlation = spearman_without_scipy(valid["评价人数"], valid["豆瓣评分"])
    summary.extend(
        [
            {"分析模块": "A", "指标": "有效电影数", "数值": len(valid)},
            {"分析模块": "A", "指标": "评分均值", "数值": valid["豆瓣评分"].mean()},
            {"分析模块": "A", "指标": "评分中位数", "数值": valid["豆瓣评分"].median()},
            {"分析模块": "A", "指标": "评价人数与评分Spearman", "数值": correlation},
        ]
    )
    for column in ("短评参与率", "长评参与率"):
        if column in valid:
            summary.extend(
                [
                    {
                        "分析模块": "A",
                        "指标": f"{column}与评分Spearman",
                        "数值": spearman_without_scipy(valid[column], valid["豆瓣评分"]),
                    },
                    {
                        "分析模块": "A",
                        "指标": f"{column}与评价人数Spearman",
                        "数值": spearman_without_scipy(valid[column], valid["评价人数"]),
                    },
                ]
            )

    plt.figure(figsize=(8, 5))
    sns.histplot(valid["豆瓣评分"], bins=20, kde=True)
    plt.xlabel("豆瓣评分")
    plt.title("电影评分分布")
    save_figure("a1_rating_distribution.png")

    plt.figure(figsize=(8, 5))
    sns.scatterplot(data=valid, x="log10评价人数", y="豆瓣评分", alpha=0.45, s=28)
    plt.title(f"评价人数与评分（Spearman ρ={correlation:.3f}）")
    save_figure("a2_votes_vs_rating.png")

    shrink = valid.dropna(subset=["贝叶斯加权评分"]).copy()
    shrink["收缩差值"] = shrink["豆瓣评分"] - shrink["贝叶斯加权评分"]
    save_table(
        shrink[["豆瓣ID", "电影名称", "豆瓣评分", "评价人数", "贝叶斯加权评分", "收缩差值"]]
        .sort_values("收缩差值", ascending=False),
        "bayesian_shrinkage.csv",
    )
    plt.figure(figsize=(8, 5))
    sns.scatterplot(data=shrink, x="log10评价人数", y="收缩差值", alpha=0.5, s=28)
    plt.axhline(0, color="black", linewidth=1)
    plt.title("原评分相对贝叶斯加权评分的收缩差值")
    save_figure("a3_bayesian_shrinkage.png")

    score_cut = float(valid["豆瓣评分"].median())
    vote_cut = float(valid["评价人数"].median())
    valid["评分层"] = np.where(valid["豆瓣评分"] >= score_cut, "较高分", "较低分")
    valid["受众层"] = np.where(valid["评价人数"] >= vote_cut, "大众", "小众")
    valid["四象限"] = valid["评分层"] + "-" + valid["受众层"]
    save_table(
        valid[["豆瓣ID", "电影名称", "豆瓣评分", "评价人数", "四象限"]],
        "movie_quadrants.csv",
    )
    quadrant_counts = valid["四象限"].value_counts().rename_axis("四象限").reset_index(name="电影数")
    save_table(quadrant_counts, "movie_quadrant_counts.csv")

    sensitivity_rows = []
    for score_threshold in (7.5, 8.0, 8.5):
        for vote_quantile in (0.25, 0.50, 0.75):
            threshold = float(valid["评价人数"].quantile(vote_quantile))
            sensitivity_rows.append(
                {
                    "评分阈值": score_threshold,
                    "评价人数分位数": vote_quantile,
                    "评价人数阈值": threshold,
                    "高分小众数": int(
                        ((valid["豆瓣评分"] >= score_threshold) & (valid["评价人数"] < threshold)).sum()
                    ),
                    "高分大众数": int(
                        ((valid["豆瓣评分"] >= score_threshold) & (valid["评价人数"] >= threshold)).sum()
                    ),
                }
            )
    save_table(pd.DataFrame(sensitivity_rows), "quadrant_sensitivity.csv")

    plt.figure(figsize=(8, 5))
    sns.scatterplot(data=valid, x="log10评价人数", y="豆瓣评分", hue="四象限", alpha=0.55, s=30)
    plt.axhline(score_cut, color="grey", linestyle="--")
    plt.axvline(math.log10(vote_cut + 1), color="grey", linestyle="--")
    plt.title("评分—受众规模四象限（按样本中位数划分）")
    save_figure("a4_movie_quadrants.png")


def analyze_review_metrics(movies: pd.DataFrame, summary: list[dict]) -> None:
    path = PROCESSED_DIR / "review_metrics.csv"
    if not path.exists():
        return
    metrics = pd.read_csv(path, encoding="utf-8-sig", dtype={"豆瓣ID": "string"})
    if metrics.empty:
        return
    merged = metrics.merge(movies[["豆瓣ID", "豆瓣评分"]], on="豆瓣ID", how="left")
    merged["样本平均换算十分制"] = merged["平均星级"] * 2
    merged["样本与总体评分差"] = merged["样本平均换算十分制"] - merged["豆瓣评分"]
    save_table(merged, "review_metric_comparison.csv")
    summary.extend(
        [
            {"分析模块": "A", "指标": "有短评评分的电影数", "数值": merged["豆瓣ID"].nunique()},
            {
                "分析模块": "A",
                "指标": "热门短评样本与总体评分平均差",
                "数值": merged["样本与总体评分差"].mean(),
            },
        ]
    )

    plot_data = merged[["电影名称", "平均星级", "原始有用数加权星级", "对数有用数加权星级"]].melt(
        id_vars="电影名称", var_name="评分口径", value_name="星级"
    )
    plt.figure(figsize=(8, 5))
    sns.boxplot(data=plot_data, x="评分口径", y="星级")
    plt.xticks(rotation=15)
    plt.title("热门短评的三种星级统计口径")
    save_figure("a5_review_weight_comparison.png")


def analyze_genre_and_origin(movies: pd.DataFrame, summary: list[dict]) -> None:
    period = movies[movies["上映年份"].between(YEAR_START, YEAR_END)].copy()
    if period.empty:
        return
    period["上映年份"] = period["上映年份"].astype(int)
    yearly_counts = period.groupby("上映年份").size().reindex(range(YEAR_START, YEAR_END + 1), fill_value=0)
    save_table(yearly_counts.rename("电影数").rename_axis("上映年份").reset_index(), "yearly_sample_counts.csv")
    summary.extend(
        [
            {"分析模块": "B", "指标": "2005-2025电影数", "数值": len(period)},
            {"分析模块": "B", "指标": "年度最小样本数", "数值": yearly_counts.min()},
            {"分析模块": "B", "指标": "年度样本数中位数", "数值": yearly_counts.median()},
        ]
    )

    genres = weighted_genre_rows(period)
    genre_weight = genres.groupby(["上映年份", "类型"], as_index=False)["类型权重"].sum()
    genre_weight["类型占比"] = genre_weight["类型权重"] / genre_weight["上映年份"].map(yearly_counts)
    save_table(genre_weight, "yearly_genre_share.csv")
    top_genres = genres.groupby("类型")["类型权重"].sum().nlargest(8).index
    trend = genre_weight[genre_weight["类型"].isin(top_genres)].pivot(
        index="上映年份", columns="类型", values="类型占比"
    ).fillna(0)
    plt.figure(figsize=(11, 6))
    trend.plot.area(ax=plt.gca(), alpha=0.8)
    plt.ylabel("加权类型占比")
    plt.title("2005—2025 主要类型占比（样本内）")
    save_figure("b1_yearly_genre_share.png")

    origin_year = period.groupby(["上映年份", "产地分类"]).size().rename("电影数").reset_index()
    origin_year["产地占比"] = origin_year["电影数"] / origin_year["上映年份"].map(yearly_counts)
    save_table(origin_year, "yearly_origin_share.csv")

    origin_stats = period.groupby("产地分类").agg(
        电影数=("豆瓣ID", "size"),
        评分均值=("豆瓣评分", "mean"),
        评分中位数=("豆瓣评分", "median"),
        评价人数中位数=("评价人数", "median"),
    ).reset_index()
    save_table(origin_stats, "origin_statistics.csv")

    mainland = period.loc[period["产地分类"] == "中国大陆", "豆瓣评分"]
    imported = period.loc[period["产地分类"] == "进口", "豆瓣评分"]
    summary.append(
        {"分析模块": "B", "指标": "中国大陆与进口评分Cohen_d", "数值": cohens_d(mainland, imported)}
    )

    _, axes = plt.subplots(1, 2, figsize=(13, 5))
    order = [name for name in ["中国大陆", "合拍", "港澳台", "进口", "未知"] if name in set(period["产地分类"])]
    sns.boxplot(data=period, x="产地分类", y="豆瓣评分", order=order, ax=axes[0])
    axes[0].set_title("评分分布")
    vote_plot = period.copy()
    vote_plot["log10评价人数"] = np.log10(pd.to_numeric(vote_plot["评价人数"], errors="coerce") + 1)
    sns.boxplot(data=vote_plot, x="产地分类", y="log10评价人数", order=order, ax=axes[1])
    axes[1].set_title("评价人数分布（对数）")
    plt.suptitle("不同产地分类的评分与评价规模（样本内）")
    save_figure("b2_origin_rating_and_votes_boxplot.png")

    cross = genres.pivot_table(
        index="类型", columns="产地分类", values="类型权重", aggfunc="sum", fill_value=0
    )
    cross = cross.loc[cross.sum(axis=1).nlargest(12).index]
    save_table(cross.reset_index(), "genre_origin_crosstab.csv")
    plt.figure(figsize=(9, 7))
    sns.heatmap(cross, cmap="YlGnBu", annot=True, fmt=".1f")
    plt.title("类型—产地加权电影数")
    save_figure("b3_genre_origin_heatmap.png")


def analyze_tag_coverage(movies: pd.DataFrame) -> None:
    """在阶段一标签关联表存在时，输出年度标签覆盖，辅助判断样本偏差。"""
    path = ROOT / "data" / "movie_tags.csv"
    if not path.exists():
        return
    tags = pd.read_csv(path, encoding="utf-8-sig", dtype={"豆瓣ID": "string"})
    if tags.empty:
        return
    links = tags.merge(movies[["豆瓣ID", "上映年份"]], on="豆瓣ID", how="inner")
    links = links[links["上映年份"].between(YEAR_START, YEAR_END)].copy()
    links["上映年份"] = links["上映年份"].astype(int)
    coverage = links.groupby(["上映年份", "标签"])["豆瓣ID"].nunique().rename("独立电影数").reset_index()
    save_table(coverage, "yearly_tag_coverage.csv")


def add_collection_quality(summary: list[dict]) -> None:
    """汇总阶段二不可用条目，供报告披露样本损失。"""
    raw_path = ROOT / "data" / "movies_raw.csv"
    unavailable_path = ROOT / "data" / "unavailable_movies.csv"
    if not raw_path.exists():
        return
    raw_count = len(pd.read_csv(raw_path, encoding="utf-8-sig"))
    unavailable_count = (
        len(pd.read_csv(unavailable_path, encoding="utf-8-sig"))
        if unavailable_path.exists()
        else 0
    )
    summary.extend(
        [
            {"分析模块": "数据质量", "指标": "阶段一候选电影数", "数值": raw_count},
            {"分析模块": "数据质量", "指标": "阶段二确认不可用数", "数值": unavailable_count},
            {
                "分析模块": "数据质量",
                "指标": "阶段二不可用比例",
                "数值": unavailable_count / raw_count if raw_count else math.nan,
            },
        ]
    )


def main() -> int:
    movie_path = PROCESSED_DIR / "movies_cleaned.csv"
    if not movie_path.exists():
        print("缺少 data/processed/movies_cleaned.csv，请先运行 src/data_cleaning.py。")
        return 1

    configure_plots()
    movies = pd.read_csv(movie_path, encoding="utf-8-sig", dtype={"豆瓣ID": "string"})
    summary: list[dict] = []
    analyze_rating_stability(movies, summary)
    analyze_review_metrics(movies, summary)
    analyze_genre_and_origin(movies, summary)
    analyze_tag_coverage(movies)
    add_collection_quality(summary)
    save_table(pd.DataFrame(summary), "analysis_summary.csv")
    print(f"分析完成，结果目录: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
