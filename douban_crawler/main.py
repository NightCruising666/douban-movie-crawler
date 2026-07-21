"""项目入口：采集阶段一或查看全局进度。

阶段二和阶段三使用独立批处理脚本，避免一条命令连续访问大量页面。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config, detail_state
from src.crawler import extract_movie_id, fetch_all_movies_for_tag_with_status
from src.parser import now_iso
from src.saver import append_to_csv


ROOT = os.path.dirname(os.path.abspath(__file__))


def project_path(relative_path: str) -> str:
    return os.path.join(ROOT, relative_path)


def checkpoint_path() -> str:
    return project_path("data/.checkpoint_stage1_tags")


def load_done_tags() -> set[str]:
    path = checkpoint_path()
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}


def mark_tag_done(tag: str) -> None:
    os.makedirs(os.path.dirname(checkpoint_path()), exist_ok=True)
    with open(checkpoint_path(), "a", encoding="utf-8") as file:
        file.write(f"{tag}\n")


def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding=config.CSV_ENCODING, newline="") as file:
        return list(csv.DictReader(file))


def archive_pipeline_files() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = project_path(f"data/archive/pipeline_rebuild_{stamp}")
    os.makedirs(archive_dir, exist_ok=True)
    for relative_path in (
        config.MOVIES_RAW_CSV,
        config.MOVIE_TAGS_CSV,
        config.MOVIES_CSV,
        config.REVIEWS_CSV,
        config.REVIEW_PROGRESS_CSV,
        config.DETAIL_FAILURES_CSV,
        config.DETAIL_FAILURE_ATTEMPTS_CSV,
        config.UNAVAILABLE_MOVIES_CSV,
        "data/.checkpoint_stage1_tags",
    ):
        source = project_path(relative_path)
        if os.path.exists(source):
            os.replace(source, os.path.join(archive_dir, os.path.basename(source)))
    print(f"旧版全流程数据已移至: {archive_dir}")


def run_stage1(rebuild: bool = False) -> None:
    if rebuild:
        archive_pipeline_files()

    raw_rows = load_csv(project_path(config.MOVIES_RAW_CSV))
    tag_rows = load_csv(project_path(config.MOVIE_TAGS_CSV))
    seen_movie_ids = {row.get("豆瓣ID", "") for row in raw_rows}
    seen_tag_keys = {(row.get("豆瓣ID", ""), row.get("标签", "")) for row in tag_rows}
    done_tags = load_done_tags()
    pending_tags = [tag for tag in config.MOVIE_TAGS if tag not in done_tags]

    if not pending_tags:
        print("阶段一所有标签已完成。")
        if not tag_rows:
            print("注意：movie_tags.csv 不存在，若需标签来源与排名，请运行 --stage1 --rebuild。")
        return

    print(f"阶段一：待采集 {len(pending_tags)} 个标签")
    for tag in pending_tags:
        subjects, complete = fetch_all_movies_for_tag_with_status(tag)
        captured_at = now_iso()
        new_movies = 0
        new_links = 0
        for rank, subject in enumerate(subjects, 1):
            movie_id = extract_movie_id(subject.get("url", ""))
            if not movie_id:
                continue

            if movie_id not in seen_movie_ids:
                append_to_csv(
                    [
                        {
                            "豆瓣ID": movie_id,
                            "电影名称": subject.get("title", ""),
                            "搜索评分": subject.get("rate", ""),
                            "URL": subject.get("url", ""),
                            "采集时间": captured_at,
                        }
                    ],
                    config.MOVIES_RAW_CSV,
                    config.RAW_MOVIE_FIELDS,
                )
                seen_movie_ids.add(movie_id)
                new_movies += 1

            tag_key = (movie_id, tag)
            if tag_key not in seen_tag_keys:
                append_to_csv(
                    [
                        {
                            "豆瓣ID": movie_id,
                            "标签": tag,
                            "标签内排名": str(rank),
                            "采集时间": captured_at,
                        }
                    ],
                    config.MOVIE_TAGS_CSV,
                    config.MOVIE_TAG_FIELDS,
                )
                seen_tag_keys.add(tag_key)
                new_links += 1

        if complete:
            mark_tag_done(tag)
            print(f"  {tag}: 新电影 {new_movies} 部，新标签关联 {new_links} 条，已写断点")
        else:
            print(f"  {tag}: 本次仅取得部分分页，未写断点，下次将重试")
            print("检测到请求失败，为保护当前访问状态，阶段一立即停止。")
            break

    print(f"阶段一完成：{len(seen_movie_ids)} 部独立电影")


def count_rows(relative_path: str) -> int:
    return len(load_csv(project_path(relative_path)))


def print_status() -> None:
    raw_count = count_rows(config.MOVIES_RAW_CSV)
    movie_count = count_rows(config.MOVIES_CSV)
    unavailable_count = len(detail_state.load_unavailable_ids())
    review_count = count_rows(config.REVIEWS_CSV)
    print("项目进度")
    print(f"  阶段一电影池: {raw_count} 部")
    print(
        f"  阶段二详情:   成功 {movie_count} 部，确认不可用 {unavailable_count} 部，"
        f"已处理 {movie_count + unavailable_count}/{raw_count} 部"
    )
    print(f"  阶段三短评:   {review_count} 条")
    print("\n继续采集：")
    print("  python douban_crawler/run_batch.py")
    print("  python douban_crawler/run_stage3.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="豆瓣电影数据采集项目")
    parser.add_argument("--stage1", action="store_true", help="采集标签电影池")
    parser.add_argument("--rebuild", action="store_true", help="归档并重建阶段一数据")
    parser.add_argument("--status", action="store_true", help="显示全局进度")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stage1:
        run_stage1(rebuild=args.rebuild)
    else:
        print_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
