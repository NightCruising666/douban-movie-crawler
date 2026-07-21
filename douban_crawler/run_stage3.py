"""阶段三：按采样口径分批采集短评。

默认每部电影采集热门排序前 30 条短评。断点以
``(豆瓣ID, 采样方式)`` 为单位，不会因某部电影已有部分短评就
误判为整部完成。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.parser import fetch_review_sample, now_iso
from src.saver import append_to_csv, save_to_csv


ROOT = os.path.dirname(os.path.abspath(__file__))
FINISHED_STATES = {"完成", "已穷尽"}


def project_path(relative_path: str) -> str:
    return os.path.join(ROOT, relative_path)


def load_movies() -> list[dict]:
    path = project_path(config.MOVIES_CSV)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding=config.CSV_ENCODING, newline="") as file:
        return list(csv.DictReader(file))


def load_review_state() -> tuple[set[tuple[str, str]], Counter, dict[tuple[str, str], str]]:
    existing_keys: set[tuple[str, str]] = set()
    counts: Counter = Counter()
    progress_states: dict[tuple[str, str], str] = {}

    reviews_path = project_path(config.REVIEWS_CSV)
    if os.path.exists(reviews_path):
        with open(reviews_path, "r", encoding=config.CSV_ENCODING, newline="") as file:
            for row in csv.DictReader(file):
                review_id = row.get("短评ID", "").strip()
                movie_id = row.get("豆瓣ID", "").strip()
                label = row.get("采样方式", "").strip()
                if review_id and movie_id and label:
                    existing_keys.add((review_id, label))
                    counts[(movie_id, label)] += 1

    progress_path = project_path(config.REVIEW_PROGRESS_CSV)
    if os.path.exists(progress_path):
        with open(progress_path, "r", encoding=config.CSV_ENCODING, newline="") as file:
            for row in csv.DictReader(file):
                key = (row.get("豆瓣ID", "").strip(), row.get("采样方式", "").strip())
                if all(key):
                    progress_states[key] = row.get("状态", "").strip()

    return existing_keys, counts, progress_states


def is_sample_finished(movie_id: str, plan: dict, counts: Counter, states: dict) -> bool:
    key = (movie_id, plan["label"])
    return counts[key] >= plan["limit"] or states.get(key) == "已穷尽"


def is_movie_finished(movie_id: str, counts: Counter, states: dict) -> bool:
    return all(is_sample_finished(movie_id, plan, counts, states) for plan in config.REVIEW_SAMPLING_PLAN)


def save_progress(movies: list[dict], counts: Counter, states: dict) -> None:
    rows = []
    updated_at = now_iso()
    movie_names = {row.get("豆瓣ID", ""): row.get("电影名称", "") for row in movies}
    for movie_id, title in movie_names.items():
        for plan in config.REVIEW_SAMPLING_PLAN:
            key = (movie_id, plan["label"])
            count = counts[key]
            if count >= plan["limit"]:
                status = "完成"
            else:
                status = states.get(key, "待采集")
            rows.append(
                {
                    "豆瓣ID": movie_id,
                    "电影名称": title,
                    "采样方式": plan["label"],
                    "目标数": str(plan["limit"]),
                    "已采集数": str(count),
                    "状态": status,
                    "更新时间": updated_at,
                }
            )
    save_to_csv(rows, config.REVIEW_PROGRESS_CSV, config.REVIEW_PROGRESS_FIELDS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分层采集豆瓣电影短评")
    parser.add_argument("--status", action="store_true", help="只显示进度")
    parser.add_argument("--batch-size", type=int, default=config.BATCH_SIZE, help="本次最多处理的电影数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    movies = load_movies()
    if not movies:
        print("尚未找到新版 movies.csv 或文件为空，请先运行阶段二。")
        return 0 if args.status else 1
    existing_keys, counts, states = load_review_state()
    pending = [
        movie
        for movie in movies
        if not is_movie_finished(movie.get("豆瓣ID", ""), counts, states)
    ]
    finished_count = len(movies) - len(pending)

    if args.status:
        review_rows = sum(counts.values())
        print(f"电影: {finished_count}/{len(movies)} 部完成全部采样口径")
        print(f"短评样本: {review_rows} 条  |  剩余电影: {len(pending)} 部")
        return 0

    if not pending:
        print(f"阶段三已完成：{finished_count}/{len(movies)} 部")
        return 0

    batch = pending[: max(1, args.batch_size)]
    print(f"本批电影: {len(batch)} 部  |  已完成: {finished_count}/{len(movies)}")

    processed = 0
    for index, movie in enumerate(batch, 1):
        movie_id = movie.get("豆瓣ID", "").strip()
        title = movie.get("电影名称", "").strip()
        print(f"\n[{index}/{len(batch)}] 《{title}》")

        movie_failed = False
        for plan in config.REVIEW_SAMPLING_PLAN:
            key = (movie_id, plan["label"])
            if is_sample_finished(movie_id, plan, counts, states):
                continue

            result = fetch_review_sample(
                movie_id,
                title,
                sample_label=plan["label"],
                order_by=plan["order_by"],
                rank_limit=plan["limit"],
                existing_keys=existing_keys,
            )
            records = result["records"]
            if records:
                append_to_csv(records, config.REVIEWS_CSV, config.REVIEW_FIELDS)
                counts[key] += len(records)

            if result["request_failed"]:
                states[key] = "失败"
                movie_failed = True
                print(f"  {plan['label']}: 请求失败")
                break

            states[key] = "已穷尽" if result["exhausted"] and counts[key] < plan["limit"] else "完成"
            print(f"  {plan['label']}: {counts[key]}/{plan['limit']} 条，状态={states[key]}")
            time.sleep(config.random_delay(config.DETAIL_DELAY_BASE))

        save_progress(movies, counts, states)

        if movie_failed:
            print("\n检测到一次请求失败，本批立即停止，已写入短评和进度可从断点续采。")
            break

        processed += 1
        if processed % config.COOLDOWN_EVERY_N == 0:
            print(f"  [主动冷却] 休息 {config.COOLDOWN_SECONDS} 秒")
            time.sleep(config.COOLDOWN_SECONDS)

    finished_after = sum(
        is_movie_finished(movie.get("豆瓣ID", ""), counts, states) for movie in movies
    )
    print(f"\n本批处理: {processed} 部  |  总进度: {finished_after}/{len(movies)} 部")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
