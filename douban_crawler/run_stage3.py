"""
阶段三批处理 — 短评采集
======================
从 movies.csv 中逐部电影拉取短评（6字段），边爬边存。

用法:
    python run_stage3.py           → 跑一批（遇拒即停）
    python run_stage3.py --status  → 看进度

反爬策略同阶段二：随机延迟 + 主动冷却 + 遇拒即停
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.parser import parse_movie_reviews
from src.saver import append_to_csv

REVIEWS_PER_MOVIE = 20      # 每部电影拉多少条短评
COOLDOWN_EVERY_MOVIES = 3   # 每 N 部电影后主动冷却
COOLDOWN_SECONDS = 45       # 冷却秒数
PAUSE_AT_TOTAL = 200        # 达到此总数时暂停（0=不暂停）

REVIEW_FIELDS = [
    "电影名称", "用户名称", "评分", "短评正文", "有用数", "评论时间"
]

# ---- 加载已采集详情的电影 ----
import csv as csv_module
movies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MOVIES_CSV)
movies_to_review = []
with open(movies_path, "r", encoding=config.CSV_ENCODING) as f:
    for row in csv_module.DictReader(f):
        mid = row.get("电影名称", "").strip()
        if mid:
            movies_to_review.append(mid)

# ---- 断点：已有短评的电影 ----
reviews_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.REVIEWS_CSV)
done_movies = set()
if os.path.exists(reviews_path):
    with open(reviews_path, "r", encoding=config.CSV_ENCODING) as f:
        for row in csv_module.DictReader(f):
            n = row.get("电影名称", "").strip()
            if n:
                done_movies.add(n)

# ---- 加载原始电影ID映射 ----
raw_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.MOVIES_RAW_CSV)
movie_id_map = {}
with open(raw_path, "r", encoding=config.CSV_ENCODING) as f:
    for row in csv_module.DictReader(f):
        movie_id_map[row["电影名称"]] = row["豆瓣ID"]

# --status 模式
if "--status" in sys.argv:
    total = len(movies_to_review)
    done = len(done_movies)
    remaining = total - done
    # 估算已有短评数
    rc = sum(1 for _ in open(reviews_path, "r", encoding=config.CSV_ENCODING)) - 1 if os.path.exists(reviews_path) else 0
    print(f"电影: {done}/{total} 部已采集短评  |  剩余: {remaining} 部")
    print(f"短评: ~{rc} 条  →  {config.REVIEWS_CSV}")
    print(f"每部采集: {REVIEWS_PER_MOVIE} 条短评")
    sys.exit(0)

# ---- 跑一批 ----
pending = [m for m in movies_to_review if m not in done_movies]
if not pending:
    print(f"全部完成! {len(done_movies)}/{len(movies_to_review)} 部已采集短评")
    sys.exit(0)

print(f"待采集: {len(pending)} 部  |  已采集: {len(done_movies)} 部")
print(f"每部: {REVIEWS_PER_MOVIE} 条短评  |  预计总数据: {len(movies_to_review) * REVIEWS_PER_MOVIE} 条")
print()

new_movies = 0
total_reviews = 0
fail_count = 0

for i, title in enumerate(pending, 1):
    mid = movie_id_map.get(title, "")
    if not mid:
        continue

    # 主动冷却
    if new_movies > 0 and new_movies % COOLDOWN_EVERY_MOVIES == 0:
        print(f"\n  [主动冷却] 已采{new_movies}部，休息{COOLDOWN_SECONDS}秒...")
        time.sleep(COOLDOWN_SECONDS)

    delay = config.random_delay(config.DETAIL_DELAY_BASE)
    print(f"[{i}/{len(pending)}] 《{title}》({delay:.1f}s)", end=" ")
    reviews = parse_movie_reviews(mid, title, max_reviews=REVIEWS_PER_MOVIE)

    if reviews:
        append_to_csv(reviews, config.REVIEWS_CSV, REVIEW_FIELDS)
        new_movies += 1
        total_reviews += len(reviews)
        fail_count = 0
        time.sleep(delay)

        # 达到目标总数时自动暂停
        done_now = len(done_movies) + new_movies
        if PAUSE_AT_TOTAL > 0 and done_now >= PAUSE_AT_TOTAL:
            rc = sum(1 for _ in open(reviews_path, "r", encoding=config.CSV_ENCODING)) - 1
            print(f"\n\n{'='*50}")
            print(f"  ⏸  已达到目标: {done_now}/{len(movies_to_review)} 部")
            print(f"  短评: ~{rc} 条  →  {config.REVIEWS_CSV}")
            print(f"  {'='*50}")
            print(f"  修改 PAUSE_AT_TOTAL 后运行 python run_stage3.py 继续")
            sys.exit(0)
    else:
        fail_count += 1
        if fail_count <= 2:
            print(f"  等10s重试...")
            time.sleep(10)
        elif fail_count <= 4:
            print(f"\n  ⚠ 连续{fail_count}次失败，等60s...")
            time.sleep(60)
        else:
            done = len(done_movies) + new_movies
            rc = sum(1 for _ in open(reviews_path, "r", encoding=config.CSV_ENCODING)) - 1
            print(f"\n\n🛑 连续 {fail_count} 次失败，IP被限。")
            print(f"   本批: +{new_movies}部 / +{total_reviews}条短评")
            print(f"   累计: {done}部电影 / ~{rc}条短评")
            print(f"   建议: 切换IP后运行 python run_stage3.py")
            sys.exit(0)

done = len(done_movies) + new_movies
rc = sum(1 for _ in open(reviews_path, "r", encoding=config.CSV_ENCODING)) - 1
print(f"\n本批完成: +{new_movies}部 / +{total_reviews}条短评")
print(f"累计: {done}/{len(movies_to_review)} 部电影 / ~{rc}条短评")
if done < len(movies_to_review):
    print(f"运行 python run_stage3.py 继续")
else:
    print("🎉 阶段三全部完成!")
