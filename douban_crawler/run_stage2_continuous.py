"""阶段二持续监督器。

每轮只采集 ``movies.csv`` 中尚不存在的豆瓣ID。请求失败时由
``run_batch`` 长冷却、有限重试并暂时跳过；一轮结束后，本脚本会等待
并自动开始下一轮补采，直到全部完成或收到人工中断信号。
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

try:
    from . import run_batch
    from .src import config, detail_state
except ImportError:  # 直接执行脚本时使用当前目录导入
    import run_batch
    from src import config, detail_state


LOCK_PATH = Path(__file__).resolve().parent / "data" / ".stage2_continuous.lock"


class SingleInstanceLock:
    """防止两个阶段二监督器并发改写CSV。"""

    def __init__(self, path: Path = LOCK_PATH):
        self.path = path
        self.acquired = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    existing_pid = int(self.path.read_text(encoding="utf-8").strip())
                    os.kill(existing_pid, 0)
                except (OSError, ValueError):
                    self.path.unlink(missing_ok=True)
                    continue
                raise RuntimeError(f"阶段二持续监督器已在运行，PID={existing_pid}")
            else:
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    file.write(str(os.getpid()))
                self.acquired = True
                return self
        raise RuntimeError("无法获取阶段二单实例锁")

    def __exit__(self, exc_type, exc_value, traceback):
        if self.acquired:
            self.path.unlink(missing_ok=True)
        self.acquired = False


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


def progress() -> tuple[int, int, int]:
    total = len(run_batch.load_raw_movies())
    collected = len(run_batch.load_collected_ids())
    unavailable = len(run_batch.load_unavailable_ids())
    return collected, unavailable, total


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

    with SingleInstanceLock():
        return run_continuous(args)


def run_continuous(args: argparse.Namespace) -> int:
    round_number = detail_state.next_round_number() - 1
    while True:
        before_success, before_unavailable, total = progress()
        before_completed = before_success + before_unavailable
        if before_completed >= total:
            print(
                f"阶段二全部完成：成功 {before_success}，"
                f"确认不可用 {before_unavailable}，总计 {before_completed}/{total}"
            )
            return 0

        round_number += 1
        print(
            f"\n[持续监督] 第 {round_number} 轮开始：成功 {before_success}，"
            f"确认不可用 {before_unavailable}，已处理 {before_completed}/{total}"
        )
        run_batch.main(
            [
                "--batch-size", str(total),
                "--delay-base", str(args.delay_base),
                "--cooldown-every", str(args.cooldown_every),
                "--cooldown-seconds", str(args.cooldown_seconds),
                "--failure-cooldown-base", str(args.failure_cooldown_base),
                "--failure-retries", str(args.failure_retries),
                "--never-stop-on-failure",
                "--round-number", str(round_number),
            ]
        )

        after_success, after_unavailable, total = progress()
        after_completed = after_success + after_unavailable
        if after_completed >= total:
            print(
                f"阶段二全部完成：成功 {after_success}，"
                f"确认不可用 {after_unavailable}，总计 {after_completed}/{total}"
            )
            return 0

        made_progress = after_completed > before_completed
        base = args.round_cooldown_base if made_progress else args.stagnant_cooldown_base
        pause = config.random_delay(base)
        reason = "本轮有新增" if made_progress else "本轮无新增"
        print(
            f"[持续监督] {reason}，当前成功 {after_success}、"
            f"确认不可用 {after_unavailable}、已处理 {after_completed}/{total}；"
            f"等待 {pause / 60:.1f} 分钟后自动补采缺失ID"
        )
        time.sleep(pause)


if __name__ == "__main__":
    raise SystemExit(main())
