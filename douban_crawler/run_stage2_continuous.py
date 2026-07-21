"""阶段二持续监督器。

每轮只采集 ``movies.csv`` 中尚不存在的豆瓣ID。请求失败时由
``run_batch`` 长冷却、有限重试并暂时跳过；一轮结束后，本脚本会等待
并自动开始下一轮补采，直到全部完成或收到人工中断信号。
"""

from __future__ import annotations

import argparse
import time

import run_batch
from src import config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="持续低速采集阶段二电影详情")
    parser.add_argument("--delay-base", type=float, default=12.0)
    parser.add_argument("--cooldown-every", type=int, default=10)
    parser.add_argument("--cooldown-seconds", type=float, default=60.0)
    parser.add_argument("--failure-cooldown-base", type=float, default=900.0)
    parser.add_argument("--failure-retries", type=int, default=1)
    parser.add_argument("--round-cooldown-base", type=float, default=1800.0)
    parser.add_argument("--stagnant-cooldown-base", type=float, default=3600.0)
    return parser.parse_args()


def progress() -> tuple[int, int]:
    total = len(run_batch.load_raw_movies())
    collected = len(run_batch.load_collected_ids())
    return collected, total


def main() -> int:
    args = parse_args()
    if min(
        args.delay_base,
        args.cooldown_seconds,
        args.failure_cooldown_base,
        args.round_cooldown_base,
        args.stagnant_cooldown_base,
    ) < 0 or args.cooldown_every <= 0 or args.failure_retries < 0:
        raise SystemExit("等待秒数不能小于0，冷却间隔必须大于0。")

    round_number = 0
    while True:
        before, total = progress()
        if before >= total:
            print(f"阶段二全部完成：{before}/{total}")
            return 0

        round_number += 1
        print(f"\n[持续监督] 第 {round_number} 轮开始：{before}/{total}")
        run_batch.main(
            [
                "--batch-size", str(total),
                "--delay-base", str(args.delay_base),
                "--cooldown-every", str(args.cooldown_every),
                "--cooldown-seconds", str(args.cooldown_seconds),
                "--failure-cooldown-base", str(args.failure_cooldown_base),
                "--failure-retries", str(args.failure_retries),
                "--never-stop-on-failure",
            ]
        )

        after, total = progress()
        if after >= total:
            print(f"阶段二全部完成：{after}/{total}")
            return 0

        made_progress = after > before
        base = args.round_cooldown_base if made_progress else args.stagnant_cooldown_base
        pause = config.random_delay(base)
        reason = "本轮有新增" if made_progress else "本轮无新增"
        print(
            f"[持续监督] {reason}，当前 {after}/{total}；"
            f"等待 {pause / 60:.1f} 分钟后自动补采缺失ID"
        )
        time.sleep(pause)


if __name__ == "__main__":
    raise SystemExit(main())
