"""
豆瓣电影数据采集 - 主程序入口
===============================

用法:
    python main.py

采集流程:
    阶段一 → 遍历标签，搜索API获取电影列表
    阶段二 → 调用Rexxar API获取每部电影详情（10字段）
    阶段三 → 调用Rexxar API获取每部电影短评（6字段）
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.crawler import fetch_all_movies_for_tag, extract_movie_id
from src.parser import parse_movie_detail, parse_movie_reviews
from src.saver import save_to_csv, append_to_csv


def main():
    print("=" * 60)
    print("  豆瓣电影数据采集系统（API版）")
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

    # 只采集前 TARGET_MOVIES 部
    target = min(config.TARGET_MOVIES, len(all_movies))
    all_movies = all_movies[:target]
    print(f"选取前 {target} 部进行详细采集\n")

    # ========== 阶段二：采集电影详情 ==========
    print("\n[阶段二] 通过Rexxar API采集电影详情（10字段）\n")

    MOVIE_FIELDS = [
        "电影名称", "导演", "主演", "上映年份", "类型",
        "国家/地区", "片长", "豆瓣评分", "评价人数", "五星占比"
    ]

    movie_details = []
    for i, movie in enumerate(all_movies, 1):
        movie_id = extract_movie_id(movie.get("url", ""))
        if not movie_id:
            continue

        print(f"[{i}/{target}]", end=" ")
        detail = parse_movie_detail(movie_id)

        if detail:
            movie_details.append(detail)

        time.sleep(config.DELAY_SECONDS)

    # 保存电影详情
    save_to_csv(movie_details, config.MOVIES_CSV, MOVIE_FIELDS)
    print(f"\n电影详情采集完成: {len(movie_details)} 部\n")

    # ========== 阶段三：采集短评 ==========
    print("\n[阶段三] 通过Rexxar API采集短评（6字段）\n")

    REVIEW_FIELDS = [
        "电影名称", "用户名称", "评分", "短评正文", "有用数", "评论时间"
    ]

    total_reviews = 0
    for i, movie in enumerate(all_movies, 1):
        movie_id = extract_movie_id(movie.get("url", ""))
        movie_title = movie.get("title", "")

        if not movie_id or not movie_title:
            continue

        print(f"[{i}/{target}]", end=" ")
        reviews = parse_movie_reviews(movie_id, movie_title)

        if reviews:
            append_to_csv(reviews, config.REVIEWS_CSV, REVIEW_FIELDS)
            total_reviews += len(reviews)

        time.sleep(config.DELAY_SECONDS)

    print(f"\n短评采集完成: {total_reviews} 条")

    # ========== 完成 ==========
    print("\n" + "=" * 60)
    print("  采集完成!")
    print(f"  电影详情: {len(movie_details)} 部 → data/{config.MOVIES_CSV}")
    print(f"  短评数据: {total_reviews} 条 → data/{config.REVIEWS_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
