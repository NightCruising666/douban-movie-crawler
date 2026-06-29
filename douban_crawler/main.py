"""
豆瓣电影数据采集 - 主程序入口
===============================

用法:
    python main.py

特性:
  - 边爬边存（每部电影详情/短评即时写入CSV，不怕中途崩溃）
  - 遇阻自动暂停（连续请求失败后自动延长等待时间）
  - 断点续传（重跑时自动跳过已采集的电影）

采集流程:
    阶段一 → 搜索API获取电影列表
    阶段二 → Rexxar API获取电影详情（10字段），边爬边存
    阶段三 → Rexxar API获取短评（6字段），边爬边存
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.crawler import fetch_all_movies_for_tag, extract_movie_id
from src.parser import parse_movie_detail, parse_movie_reviews
from src.saver import save_to_csv, append_to_csv


# 输出字段
MOVIE_FIELDS = [
    "电影名称", "导演", "主演", "上映年份", "类型",
    "国家/地区", "片长", "豆瓣评分", "评价人数", "五星占比"
]

REVIEW_FIELDS = [
    "电影名称", "用户名称", "评分", "短评正文", "有用数", "评论时间"
]


def load_existing_ids(csv_path):
    """
    断点续传：读取已有CSV中已采集的电影名，返回 set。
    这样重跑时不会重复采集同一部电影。
    """
    import csv as csv_module

    if not os.path.exists(csv_path):
        return set()

    collected = set()
    try:
        with open(csv_path, "r", encoding=config.CSV_ENCODING) as f:
            reader = csv_module.DictReader(f)
            for row in reader:
                name = row.get("电影名称", "").strip()
                if name:
                    collected.add(name)
    except Exception:
        pass

    return collected


def adaptive_delay(fail_count):
    """
    自适应延迟：连续失败越多，等待越久。

    失败次数  等待时间
    --------  --------
    1-2次     正常延迟 (2s)
    3-5次     5秒
    6-10次    15秒
    >10次     60秒（可能是IP被封，需要长暂停）
    """
    if fail_count <= 2:
        return config.DELAY_SECONDS
    elif fail_count <= 5:
        return 5.0
    elif fail_count <= 10:
        return 15.0
    else:
        return 60.0


def main():
    print("=" * 60)
    print("  豆瓣电影数据采集系统（API版 v2）")
    print("  边爬边存 · 遇阻暂停 · 断点续传")
    print("=" * 60)

    # ========== 阶段一：采集电影列表 ==========
    print("\n[阶段一] 通过搜索API采集电影列表\n")

    all_movies = []
    seen_ids = set()

    for tag in config.MOVIE_TAGS:
        movies = fetch_all_movies_for_tag(tag)
        for movie in movies:
            movie_id = extract_movie_id(movie.get("url", ""))
            if movie_id and movie_id not in seen_ids:
                seen_ids.add(movie_id)
                all_movies.append(movie)
        print(f"  累计去重后: {len(all_movies)} 部\n")

    print(f"共获取 {len(all_movies)} 部独立电影")

    if len(all_movies) == 0:
        print("未获取到任何电影，请检查网络。")
        return

    target = min(config.TARGET_MOVIES, len(all_movies))
    all_movies = all_movies[:target]
    print(f"选取前 {target} 部进行详细采集\n")

    # ========== 阶段二：采集电影详情（边爬边存） ==========
    print("\n[阶段二] 采集电影详情（10字段）—— 边爬边存\n")

    # 断点续传：跳过已采集的电影
    movies_csv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config.MOVIES_CSV
    )
    collected_movies = load_existing_ids(movies_csv_path)

    if collected_movies:
        print(f"  发现已有 {len(collected_movies)} 部电影数据，将跳过重复采集\n")

    fail_count = 0
    saved_count = len(collected_movies)

    for i, movie in enumerate(all_movies, 1):
        movie_id = extract_movie_id(movie.get("url", ""))
        movie_title = movie.get("title", "")

        if not movie_id:
            continue

        # 断点续传：跳过已有的
        if movie_title in collected_movies:
            print(f"[{i}/{target}] 跳过（已采集）: 《{movie_title}》")
            continue

        # 自适应延迟：连续失败多就多等
        delay = adaptive_delay(fail_count) if fail_count > 0 else config.DELAY_SECONDS
        if delay != config.DELAY_SECONDS:
            print(f"  [冷却] 连续失败{fail_count}次，等待{delay:.0f}秒...")
            time.sleep(delay)

        print(f"[{i}/{target}]", end=" ")
        detail = parse_movie_detail(movie_id)

        if detail:
            # 成功：边爬边存，即时写入CSV
            append_to_csv([detail], config.MOVIES_CSV, MOVIE_FIELDS)
            saved_count += 1
            collected_movies.add(movie_title)
            fail_count = 0  # 重置失败计数
        else:
            fail_count += 1
            print(f"  ⚠ 连续失败 {fail_count} 次")

            # 连续失败超10次 → 暂停60秒再试
            if fail_count >= 10:
                print(f"  🛑 连续失败 {fail_count} 次，暂停 60 秒...")
                time.sleep(60)
                fail_count = 0

        time.sleep(config.DELAY_SECONDS)

    print(f"\n电影详情采集完成: 本次新增 {saved_count - len(collected_movies) + len(collected_movies)} 部 → {config.MOVIES_CSV}\n")

    # ========== 阶段三：采集短评（边爬边存） ==========
    print("\n[阶段三] 采集短评（6字段）—— 边爬边存\n")

    reviews_csv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config.REVIEWS_CSV
    )
    collected_review_movies = load_existing_ids(reviews_csv_path)

    # 只对已成功采集详情的电影拉短评
    fail_count = 0
    total_reviews = 0

    for i, movie in enumerate(all_movies, 1):
        movie_id = extract_movie_id(movie.get("url", ""))
        movie_title = movie.get("title", "")

        if not movie_id or not movie_title:
            continue

        # 跳过已有短评的电影
        if movie_title in collected_review_movies:
            print(f"[{i}/{target}] 跳过短评（已有）: 《{movie_title}》")
            continue

        delay = adaptive_delay(fail_count) if fail_count > 0 else config.DELAY_SECONDS
        if delay != config.DELAY_SECONDS:
            print(f"  [冷却] 连续失败{fail_count}次，等待{delay:.0f}秒...")
            time.sleep(delay)

        print(f"[{i}/{target}]", end=" ")
        reviews = parse_movie_reviews(movie_id, movie_title)

        if reviews:
            append_to_csv(reviews, config.REVIEWS_CSV, REVIEW_FIELDS)
            total_reviews += len(reviews)
            collected_review_movies.add(movie_title)
            fail_count = 0
        else:
            fail_count += 1
            print(f"  ⚠ 连续失败 {fail_count} 次")

            if fail_count >= 10:
                print(f"  🛑 连续失败 {fail_count} 次，暂停 60 秒...")
                time.sleep(60)
                fail_count = 0

        time.sleep(config.DELAY_SECONDS)

    print(f"\n短评采集完成: 本次新增 {total_reviews} 条 → {config.REVIEWS_CSV}")

    # ========== 完成 ==========
    print("\n" + "=" * 60)
    print("  采集完成!")
    print(f"  电影详情: {len(load_existing_ids(movies_csv_path))} 部 → {config.MOVIES_CSV}")
    print(f"  短评数据: 写入 {config.REVIEWS_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
