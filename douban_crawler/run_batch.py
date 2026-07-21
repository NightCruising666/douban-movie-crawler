"""阶段二：分批采集电影详情。

用法：
    python run_batch.py
    python run_batch.py --status
    python run_batch.py --batch-size 50
    python run_batch.py --batch-size 2601 --delay-base 12 --cooldown-every 10 --cooldown-seconds 60
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分批采集豆瓣电影详情")
    parser.add_argument("--status", action="store_true", help="只显示进度")
    parser.add_argument("--batch-size", type=int, default=config.BATCH_SIZE, help="本次最多采集数")
    parser.add_argument(
        "--delay-base",
        type=float,
        default=config.DETAIL_DELAY_BASE,
        help="每部成功后等待的基准秒数，实际随机浮动±30%%",
    )
    parser.add_argument(
        "--cooldown-every",
        type=int,
        default=config.COOLDOWN_EVERY_N,
        help="每成功采集多少部主动冷却一次",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=config.COOLDOWN_SECONDS,
        help="每次主动冷却秒数",
    )
    parser.add_argument(
        "--failure-cooldown-base",
        type=float,
        default=config.FAILURE_COOLDOWN_BASE,
        help="请求失败后的基准冷却秒数，实际随机浮动±30%%",
    )
    parser.add_argument(
        "--failure-retries",
        type=int,
        default=config.FAILURE_RETRIES,
        help="单部电影在长冷却后的重试次数",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=config.MAX_CONSECUTIVE_FAILURES,
        help="连续多少部电影在冷却重试后仍失败才停止",
    )
    parser.add_argument(
        "--minimum-runtime-hours",
        type=float,
        default=config.MINIMUM_RUNTIME_HOURS,
        help="运行未满该时长时，连续失败只触发冷却而不停止",
    )
    parser.add_argument(
        "--never-stop-on-failure",
        action="store_true",
        help="失败只冷却和跳过，不因连续失败退出；供持续监督模式使用",
    )
    return parser.parse_args(argv)


def fetch_detail_with_cooldown(
    movie_id: str,
    *,
    failure_retries: int,
    failure_cooldown_base: float,
) -> dict | None:
    """请求详情；失败时长冷却后有限重试，避免连续冲击接口。"""
    for attempt in range(failure_retries + 1):
        detail = parse_movie_detail(movie_id)
        if detail is not None:
            return detail
        if attempt < failure_retries:
            pause = config.random_delay(failure_cooldown_base)
            print(
                f"  请求失败，冷却 {pause / 60:.1f} 分钟后"
                f"进行第 {attempt + 1}/{failure_retries} 次重试"
            )
            time.sleep(pause)
    return None


def should_stop_after_failures(
    consecutive_failures: int,
    failure_limit: int,
    elapsed_seconds: float,
    minimum_runtime_hours: float,
) -> bool:
    """只有超过保护运行时长且达到连续失败上限时才停止。"""
    return (
        consecutive_failures >= failure_limit
        and elapsed_seconds >= minimum_runtime_hours * 3600
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if (
        args.batch_size <= 0
        or args.delay_base < 0
        or args.cooldown_every <= 0
        or args.cooldown_seconds < 0
        or args.failure_cooldown_base < 0
        or args.failure_retries < 0
        or args.max_consecutive_failures <= 0
        or args.minimum_runtime_hours < 0
    ):
        raise SystemExit("批量数、冷却间隔和失败上限必须大于0，等待秒数与重试数不能小于0。")
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
    consecutive_failed_movies = 0
    run_started_at = time.monotonic()
    for index, movie in enumerate(batch, 1):
        if new_count and new_count % args.cooldown_every == 0:
            print(f"\n  [主动冷却] 已采 {new_count} 部，休息 {args.cooldown_seconds:g} 秒")
            time.sleep(args.cooldown_seconds)

        movie_id = movie.get("豆瓣ID", "").strip()
        delay = config.random_delay(args.delay_base)
        print(f"[{index}/{len(batch)}] ({delay:.1f}s)", end=" ")
        detail = fetch_detail_with_cooldown(
            movie_id,
            failure_retries=args.failure_retries,
            failure_cooldown_base=args.failure_cooldown_base,
        )

        if detail:
            append_to_csv([detail], config.MOVIES_CSV, config.MOVIE_FIELDS)
            collected.add(movie_id)
            new_count += 1
            consecutive_failed_movies = 0
            time.sleep(delay)
            continue

        consecutive_failed_movies += 1
        print(
            f"  该电影冷却重试后仍失败，暂时跳过；"
            f"连续失败电影 {consecutive_failed_movies}/{args.max_consecutive_failures}"
        )
        elapsed_seconds = time.monotonic() - run_started_at
        if not args.never_stop_on_failure and should_stop_after_failures(
            consecutive_failed_movies,
            args.max_consecutive_failures,
            elapsed_seconds,
            args.minimum_runtime_hours,
        ):
            print("\n连续失败达到上限，本批停止，未成功电影会在下次运行补采。")
            break

        if consecutive_failed_movies >= args.max_consecutive_failures:
            if args.never_stop_on_failure:
                print("  持续监督模式已启用，连续失败只触发冷却，不停止")
            else:
                remaining_hours = max(0.0, args.minimum_runtime_hours - elapsed_seconds / 3600)
                print(
                    f"  尚在 {args.minimum_runtime_hours:g} 小时保护窗口内"
                    f"（剩余约 {remaining_hours:.1f} 小时），冷却后继续"
                )
            consecutive_failed_movies = 0

        pause = config.random_delay(args.failure_cooldown_base)
        print(f"  继续下一部前再冷却 {pause / 60:.1f} 分钟")
        time.sleep(pause)

    remaining = len(all_movies) - len(collected)
    print(f"\n本批新增: {new_count} 部  |  累计: {len(collected)}/{len(all_movies)}  |  剩余: {remaining} 部")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
