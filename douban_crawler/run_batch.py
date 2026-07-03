"""
阶段二批处理
===========
每批采集 100 部电影详情，采集完自动停止。
运行前自动跳过已采集的电影。

用法:
    python run_batch.py      → 跑一批（100部）
    python run_batch.py --status → 只看进度不跑
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.parser import parse_movie_detail
from src.saver import append_to_csv

BATCH_SIZE = 100
MOVIE_FIELDS = [
    "电影名称", "导演", "主演", "上映年份", "类型",
    "国家/地区", "片长", "豆瓣评分", "评价人数", "五星占比",
    "短评总数", "长评总数"
]

# ---- 加载阶段一数据 ----
import csv as csv_module
raw_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MOVIES_RAW_CSV)
all_movies = []
with open(raw_path, "r", encoding=config.CSV_ENCODING) as f:
    for row in csv_module.DictReader(f):
        all_movies.append({
            "title": row["电影名称"], "url": row["URL"],
            "rate": row["评分"], "id": row["豆瓣ID"],
        })

target = min(config.TARGET_MOVIES, len(all_movies))
selected = all_movies[:target]

# ---- 断点：已采集 ----
collected_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MOVIES_CSV)
collected = set()
if os.path.exists(collected_path):
    with open(collected_path, "r", encoding=config.CSV_ENCODING) as f:
        for row in csv_module.DictReader(f):
            n = row.get("电影名称", "").strip()
            if n:
                collected.add(n)

# --status 模式
if "--status" in sys.argv:
    print(f"总目标: {target} 部  |  已采集: {len(collected)} 部  |  待采集: {target - len(collected)} 部")
    sys.exit(0)

# ---- 跑一个批次 ----
pending = [m for m in selected if m["title"] not in collected]
if not pending:
    print(f"全部完成! {len(collected)}/{target} 部已采集")
    sys.exit(0)

batch = pending[:BATCH_SIZE]
print(f"本批: {len(batch)} 部  |  累计: {len(collected)}/{target}")
print()

new_count = 0
fail_count = 0

for i, m in enumerate(batch, 1):
    # 主动冷却：每 N 部成功就休息
    if new_count > 0 and new_count % config.COOLDOWN_EVERY_N == 0:
        print(f"\n  [主动冷却] 已采{new_count}部，休息{config.COOLDOWN_SECONDS}秒...")
        time.sleep(config.COOLDOWN_SECONDS)

    delay = config.random_delay(config.DETAIL_DELAY_BASE)
    print(f"[{i}/{len(batch)}] ({delay:.1f}s)", end=" ")
    detail = parse_movie_detail(m["id"])

    if detail:
        append_to_csv([detail], config.MOVIES_CSV, MOVIE_FIELDS)
        new_count += 1
        fail_count = 0
        time.sleep(delay)
    else:
        fail_count += 1
        # 单次失败不立即停，给几次重试机会
        if fail_count <= 2:
            pause = config.FAIL_PAUSE_SHORT
            print(f"  等{pause}s重试...", end=" ")
            time.sleep(pause)
        elif fail_count <= 5:
            pause = config.FAIL_PAUSE_MEDIUM
            print(f"\n  ⚠ 连续{fail_count}次失败，等{pause}s...")
            time.sleep(pause)
        else:
            # 真的被限了
            print(f"\n\n🛑 连续 {fail_count} 次失败，IP已被限制。")
            print(f"   本批新增: {new_count} 部  |  累计: {len(collected) + new_count}/{target}")
            remaining = target - len(collected) - new_count
            print(f"   剩余: {remaining} 部  |  建议: 切换IP后运行 python run_batch.py")
            sys.exit(0)

remaining = target - len(collected) - new_count
print(f"\n本批完成: 新增 {new_count} 部  |  累计: {len(collected) + new_count}/{target}")
if remaining > 0:
    print(f"剩余: {remaining} 部  |  运行 python run_batch.py 继续")
else:
    print("全部完成!")
