"""阶段二：分批采集电影详情。

用法：
    python run_batch.py
    python run_batch.py --status
    python run_batch.py --batch-size 50
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.parser import parse_movie_detail
from src.saver import append_to_csv


ROOT = os.path.dirname(os.path.abspath(__file__))


def project_path(relative_path: str) -> str:
    return os.path.join(ROOT, relative_path)


def load_raw_movies() -> list[dict]:
    path = project_path(config.MOVIES_RAW_CSV)
    with open(path, "r", encoding=config.CSV_ENCODING, newline="") as file:
        rows = list(csv.DictReader(file))

    if config.TARGET_MOVIES is not None:
        rows = rows[: config.TARGET_MOVIES]
    return rows


def load_collected_ids() -> set[str]:
    path = project_path(config.MOVIES_CSV)
    if not os.path.exists(path):
        return set()

    with open(path, "r", encoding=config.CSV_ENCODING, newline="") as file:
        reader = csv.DictReader(file)
        if "豆瓣ID" not in (reader.fieldnames or []):
            raise RuntimeError(
                "movies.csv 为旧版表头，请先移入 data/archive 后再运行新版采集。"
            )
        return {row["豆瓣ID"].strip() for row in reader if row.get("豆瓣ID", "").strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分批采集豆瓣电影详情")
    parser.add_argument("--status", action="store_true", help="只显示进度")
    parser.add_argument("--batch-size", type=int, default=config.BATCH_SIZE, help="本次最多采集数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    all_movies = load_raw_movies()
    collected = load_collected_ids()
    pending = [row for row in all_movies if row.get("豆瓣ID", "").strip() not in collected]

    if args.status:
        print(f"总目标: {len(all_movies)} 部  |  已采集: {len(collected)} 部  |  待采集: {len(pending)} 部")
        return 0

    if not pending:
        print(f"全部完成：{len(collected)}/{len(all_movies)} 部")
        return 0

    batch = pending[: max(1, args.batch_size)]
    print(f"本批: {len(batch)} 部  |  累计: {len(collected)}/{len(all_movies)}")

    new_count = 0
    fail_count = 0
    for index, movie in enumerate(batch, 1):
        if new_count and new_count % config.COOLDOWN_EVERY_N == 0:
            print(f"\n  [主动冷却] 已采 {new_count} 部，休息 {config.COOLDOWN_SECONDS} 秒")
            time.sleep(config.COOLDOWN_SECONDS)

        movie_id = movie.get("豆瓣ID", "").strip()
        delay = config.random_delay(config.DETAIL_DELAY_BASE)
        print(f"[{index}/{len(batch)}] ({delay:.1f}s)", end=" ")
        detail = parse_movie_detail(movie_id)

        if detail:
            append_to_csv([detail], config.MOVIES_CSV, config.MOVIE_FIELDS)
            collected.add(movie_id)
            new_count += 1
            fail_count = 0
            time.sleep(delay)
            continue

        fail_count += 1
        if fail_count <= 2:
            pause = config.FAIL_PAUSE_SHORT
            print(f"  等待 {pause} 秒后继续")
            time.sleep(pause)
        elif fail_count <= 5:
            pause = config.FAIL_PAUSE_MEDIUM
            print(f"  连续失败 {fail_count} 次，等待 {pause} 秒")
            time.sleep(pause)
        else:
            print("\n连续失败 6 次，本批停止，保留已写入数据。")
            break

    remaining = len(all_movies) - len(collected)
    print(f"\n本批新增: {new_count} 部  |  累计: {len(collected)}/{len(all_movies)}  |  剩余: {remaining} 部")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
