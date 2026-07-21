"""
小规模试采脚本
=============
只采 10 部电影 + 每部 20 条短评，验证全流程。
输出文件: data/movies_test.csv + data/reviews_test.csv
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.crawler import fetch_all_movies_for_tag, extract_movie_id
from src.parser import parse_movie_detail, parse_movie_reviews
from src.saver import save_to_csv, append_to_csv

# ---- 覆盖配置 ----
config.TARGET_MOVIES = 10
config.MAX_REVIEWS_PER_MOVIE = 20
config.DELAY_SECONDS = 1.5
config.MOVIES_CSV = "data/movies_test.csv"
config.REVIEWS_CSV = "data/reviews_test.csv"
# 只用两个标签就够了
config.MOVIE_TAGS = ["热门", "经典"]
config.MAX_PER_TAG = 60  # 每个标签翻3页

MOVIE_FIELDS = [
    "电影名称", "导演", "主演", "上映年份", "类型",
    "国家/地区", "片长", "豆瓣评分", "评价人数", "五星占比"
]

REVIEW_FIELDS = [
    "电影名称", "用户名称", "评分", "短评正文", "有用数", "评论时间"
]

print("=" * 50)
print("小规模试采 (10部电影 × 20条短评)")
print("=" * 50)

# ---- 阶段一：电影列表 ----
print("\n[阶段一] 搜索API获取电影列表\n")
all_movies = []
seen_ids = set()
for tag in config.MOVIE_TAGS:
    movies = fetch_all_movies_for_tag(tag)
    for m in movies:
        mid = extract_movie_id(m.get("url", ""))
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            all_movies.append(m)
    print(f"  累计去重: {len(all_movies)} 部\n")

target = min(config.TARGET_MOVIES, len(all_movies))
all_movies = all_movies[:target]
print(f"选取 {target} 部\n")

# ---- 阶段二：电影详情 ----
print("[阶段二] 详情API\n")
details = []
for i, m in enumerate(all_movies, 1):
    mid = extract_movie_id(m.get("url", ""))
    print(f"[{i}/{target}]", end=" ")
    d = parse_movie_detail(mid)
    if d:
        details.append(d)
    time.sleep(config.DELAY_SECONDS)

save_to_csv(details, config.MOVIES_CSV, MOVIE_FIELDS)
print(f"详情: {len(details)} 部 → {config.MOVIES_CSV}\n")

# ---- 阶段三：短评 ----
print("[阶段三] 短评API\n")
total = 0
for i, m in enumerate(all_movies, 1):
    mid = extract_movie_id(m.get("url", ""))
    title = m.get("title", "")
    print(f"[{i}/{target}]", end=" ")
    reviews = parse_movie_reviews(mid, title)
    if reviews:
        append_to_csv(reviews, config.REVIEWS_CSV, REVIEW_FIELDS)
        total += len(reviews)
    time.sleep(config.DELAY_SECONDS)

print(f"短评: {total} 条 → {config.REVIEWS_CSV}")

print("\n" + "=" * 50)
print("试采完成！请检查 data/ 目录下的文件。")
print("=" * 50)
