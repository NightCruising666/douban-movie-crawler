"""
豆瓣电影数据采集 - 主程序入口（v3）
=====================================

用法:
    python main.py            → 跑阶段一 + 阶段二
    python main.py --stage1   → 只跑阶段一
    python main.py --stage2   → 只跑阶段二（需要阶段一已完成）

特性:
  - 每阶段独立断点，中断重跑不丢数据
  - 阶段一：搜索结果存 movies_raw.csv，按标签断点
  - 阶段二：详情边爬边存 movies.csv，按电影名断点
  - 遇阻自动暂停 + 自适应延迟

数据筛选设计（报告用）:
  阶段一：19个标签 × 200条 → 去重 → 2478部 → movies_raw.csv
    筛选依据: 标签维度覆盖（热门/最新/经典 + 地区 + 类型）
    去重方法: 按URL中的豆瓣ID去重（不同标签可能包含同一部电影）

  阶段一→二：2478部 → 500部
    筛选方法: 保留前500部（按搜索API返回顺序）
    顺序说明: 豆瓣搜索API在每个标签内按相关性排序
              标签顺序: 热门→最新→经典→地区→类型
              前500部覆盖了热门+最新+经典的大部分
    备选方案: 如需要更均衡分布，可改为分层抽样（每标签取N部）
    为何这样选: 豆瓣搜索API的排序已隐含了"热度+时效性"

  阶段二：500部 × Rexxar详情API → movies.csv (10字段)
    无进一步筛选，全部采集
"""

import time
import sys
import os
import csv as csv_module

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.crawler import fetch_all_movies_for_tag, extract_movie_id
from src.parser import parse_movie_detail
from src.saver import save_to_csv, append_to_csv

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))

# 输出字段
MOVIE_FIELDS = [
    "电影名称", "导演", "主演", "上映年份", "类型",
    "国家/地区", "片长", "豆瓣评分", "评价人数", "五星占比"
]


# ==================== 断点辅助函数 ====================

def _checkpoint_path(stage):
    """获取断点文件路径：.checkpoint_stage1 / .checkpoint_stage2"""
    return os.path.join(ROOT, f"data/.checkpoint_{stage}")


def load_done_tags():
    """读取阶段一断点：已完成的标签列表"""
    cp = _checkpoint_path("stage1_tags")
    if not os.path.exists(cp):
        return set()
    with open(cp, "r") as f:
        return set(line.strip() for line in f if line.strip())


def save_done_tag(tag):
    """追加一个标签到断点文件"""
    cp = _checkpoint_path("stage1_tags")
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "a") as f:
        f.write(tag + "\n")


def load_existing_ids(csv_path):
    """读取已有CSV中的电影名 → set（阶段二断点用）"""
    path = os.path.join(ROOT, csv_path)
    if not os.path.exists(path):
        return set()

    collected = set()
    try:
        with open(path, "r", encoding=config.CSV_ENCODING) as f:
            for row in csv_module.DictReader(f):
                name = row.get("电影名称", "").strip()
                if name:
                    collected.add(name)
    except Exception:
        pass
    return collected


def load_existing_raw_movies():
    """
    从已有 movies_raw.csv 中恢复阶段一数据。
    如果阶段一已完成但程序被中断，可以不重新爬搜索API。
    """
    path = os.path.join(ROOT, config.MOVIES_RAW_CSV)
    if not os.path.exists(path):
        return []

    movies = []
    try:
        with open(path, "r", encoding=config.CSV_ENCODING) as f:
            for row in csv_module.DictReader(f):
                movies.append({
                    "title": row.get("电影名称", ""),
                    "url": row.get("URL", ""),
                    "rate": row.get("评分", ""),
                    "id": row.get("豆瓣ID", ""),
                })
    except Exception:
        pass
    return movies


# ==================== 自适应延迟 ====================

def adaptive_delay(fail_count):
    if fail_count <= 2:
        return config.DELAY_SECONDS
    elif fail_count <= 5:
        return 5.0
    elif fail_count <= 10:
        return 15.0
    else:
        return 60.0


# ==================== 阶段一：电影列表采集 ====================

def stage1_search():
    """
    阶段一：通过搜索API采集电影列表。

    断点机制:
      - 每完成一个标签，写入 .checkpoint_stage1_tags
      - 重跑时跳过已完成的标签
      - 数据边爬边追加到 movies_raw.csv

    数据保留:
      - movies_raw.csv: 全部去重后的电影（2478部），含豆瓣ID/名称/评分/URL
      - 这份数据是后续所有筛选的基础，不可删除
    """
    print("=" * 60)
    print("  阶段一：搜索API → 电影列表")
    print("=" * 60)

    raw_csv_path = os.path.join(ROOT, config.MOVIES_RAW_CSV)

    # ---- 断点：已完成的标签 ----
    done_tags = load_done_tags()
    if done_tags:
        print(f"  断点恢复: 已完成 {len(done_tags)} 个标签\n")

    # ---- 断点：已保存的电影（用于去重） ----
    seen_ids = set()
    all_movies = load_existing_raw_movies()
    for m in all_movies:
        mid = m.get("id", "")
        if mid:
            seen_ids.add(mid)
    if all_movies:
        print(f"  从 {config.MOVIES_RAW_CSV} 恢复 {len(all_movies)} 部已有电影\n")

    RAW_FIELDS = ["豆瓣ID", "电影名称", "评分", "URL"]

    pending_tags = [t for t in config.MOVIE_TAGS if t not in done_tags]

    if not pending_tags:
        print("  所有标签已完成，跳过阶段一\n")
    else:
        print(f"  待采集标签: {len(pending_tags)} 个\n")

        for tag in pending_tags:
            movies = fetch_all_movies_for_tag(tag)
            new_count = 0

            for m in movies:
                mid = extract_movie_id(m.get("url", ""))
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    all_movies.append(m)
                    new_count += 1

                    # 边爬边存：每部新电影立即写入
                    row = {
                        "豆瓣ID": mid,
                        "电影名称": m.get("title", ""),
                        "评分": m.get("rate", ""),
                        "URL": m.get("url", ""),
                    }
                    append_to_csv([row], config.MOVIES_RAW_CSV, RAW_FIELDS)

            # 标签完成 → 写断点
            save_done_tag(tag)
            print(f"  标签 '{tag}': 新增 {new_count} 部, 累计 {len(all_movies)} 部\n")

    print(f"  阶段一完成: {len(all_movies)} 部独立电影")
    print(f"  数据: {config.MOVIES_RAW_CSV}")
    return all_movies


# ==================== 阶段一→二 筛选 ====================

def select_movies_for_detail(all_movies, target=None):
    """
    从阶段一全部电影中选取目标数量进入阶段二。

    当前筛选方法: 保留前 N 部（按搜索API返回顺序）

    筛选依据（报告可写）:
      - 豆瓣搜索API在每个标签内按相关性排序
      - 标签顺序: 热门→最新→经典→可播放→豆瓣高分→冷门佳片
                  →华语→欧美→韩国→日本
                  →动作→喜剧→爱情→科幻→悬疑→恐怖→剧情→动画→纪录片
      - 意味着前500部覆盖了: 热门+最新+经典的几乎全部，加上可播放和豆瓣高分的开头部分
      - 这保证了样本在"热度+时效性+口碑"三个维度上都有覆盖

    备选方案（可讨论）:
      A. 前N部（当前方案）: 偏重热度和时效性，简单直接
      B. 分层抽样: 每标签均分配额，分布更均衡但实现复杂
      C. 评分阈值: 只取≥6.0分的，但会丢失低分样本
      D. 随机抽样: 最公平但可能丢失代表性

    选择A的理由:
      - 豆瓣搜索API的排序本身就是一种"综合热度"排序
      - 前500部已经包含了多标签的电影（跨标签重复已去重）
      - 实现简单，报告好解释

    参数:
        all_movies: 阶段一全部电影列表
        target:     目标数量（默认取 config.TARGET_MOVIES）

    返回:
        list[dict]: 筛选后的电影列表
    """
    if target is None:
        target = config.TARGET_MOVIES

    target = min(target, len(all_movies))
    selected = all_movies[:target]

    print(f"\n  === 筛选说明 ===")
    print(f"  原始数量: {len(all_movies)} 部")
    print(f"  筛选方法: 保留前 {target} 部（按搜索API返回顺序）")
    print(f"  筛选原因: 豆瓣搜索API内置了热度+时效性排序")
    print(f"             标签顺序覆盖了热门/最新/经典/地区/类型")
    print(f"             前{target}部已包含多个维度的电影")

    return selected


# ==================== 阶段二：电影详情采集 ====================

def stage2_details(all_movies):
    """
    阶段二：通过 Rexxar API 采集电影详情（10字段）。

    断点机制:
      - 已采集的电影（按名称去重）自动跳过
      - 每部电影即时追加到 movies.csv
      - 连续失败自动延长等待时间

    数据保留:
      - movies.csv: 500部电影的10字段详情
      - 与 movies_raw.csv 形成两级数据层级
    """
    target = len(all_movies)
    collected = load_existing_ids(config.MOVIES_CSV)

    print("=" * 60)
    print("  阶段二：Rexxar API → 电影详情（10字段）")
    print(f"  目标: {target} 部")
    print(f"  已采集: {len(collected)} 部")
    print(f"  待采集: {target - len(collected)} 部")
    print(f"  预计耗时: ~{(target - len(collected)) * config.DELAY_SECONDS / 60:.0f} 分钟")
    print("=" * 60)

    fail_count = 0
    new_count = 0

    for i, movie in enumerate(all_movies, 1):
        movie_id = extract_movie_id(movie.get("url", ""))
        movie_title = movie.get("title", "")

        if not movie_id:
            continue

        # 断点：跳过已采集
        if movie_title in collected:
            continue

        delay = adaptive_delay(fail_count) if fail_count > 0 else config.DELAY_SECONDS
        if fail_count > 2:
            print(f"  [冷却] 连续失败{fail_count}次，等待{delay:.0f}秒...")
            time.sleep(delay)

        print(f"[{i}/{target}]", end=" ")
        detail = parse_movie_detail(movie_id)

        if detail:
            append_to_csv([detail], config.MOVIES_CSV, MOVIE_FIELDS)
            collected.add(movie_title)
            new_count += 1
            fail_count = 0
        else:
            fail_count += 1
            print(f"  ⚠ 连续失败 {fail_count} 次")

            if fail_count >= 10:
                print(f"  🛑 暂停 60 秒...")
                time.sleep(60)
                fail_count = 0

        time.sleep(config.DELAY_SECONDS)

    total = len(load_existing_ids(config.MOVIES_CSV))
    print(f"\n  阶段二完成!")
    print(f"  本次新增: {new_count} 部")
    print(f"  总计: {total} 部 → {config.MOVIES_CSV}")
    return total


# ==================== 主入口 ====================

def main():
    stage1_only = "--stage1" in sys.argv
    stage2_only = "--stage2" in sys.argv

    print("=" * 60)
    print("  豆瓣电影数据采集系统 v3")
    print("  每阶段独立断点 · 边爬边存 · 遇阻暂停")
    print("=" * 60)

    # ---- 阶段一 ----
    if stage2_only:
        # 只跑阶段二：从已有的 movies_raw.csv 加载列表
        all_movies = load_existing_raw_movies()
        if not all_movies:
            print("\n  ⚠ movies_raw.csv 不存在，请先运行阶段一: python main.py --stage1")
            return
        print(f"\n  从 {config.MOVIES_RAW_CSV} 加载 {len(all_movies)} 部电影")
        selected = select_movies_for_detail(all_movies)
    else:
        all_movies = stage1_search()
        if not all_movies:
            return
        selected = select_movies_for_detail(all_movies)

        if stage1_only:
            print("\n  --stage1 模式，阶段一完成后退出")
            print(f"  原始列表: {config.MOVIES_RAW_CSV} ({len(all_movies)} 部)")
            print(f"  筛选后: {len(selected)} 部待采集详情")
            return

    # ---- 阶段二 ----
    total = stage2_details(selected)

    # ---- 完成汇报 ----
    print("\n" + "=" * 60)
    print("  阶段一 + 阶段二 全部完成！")
    print(f"  原始列表: {config.MOVIES_RAW_CSV} ({len(all_movies)} 部)")
    print(f"  筛选后:   {len(selected)} 部")
    print(f"  详情数据: {config.MOVIES_CSV} ({total} 部)")
    print()
    print("  数据层级说明（写报告用）:")
    print(f"    阶段一 → {len(all_movies)}部（原始池，按标签+ID去重）")
    print(f"    阶段二 → {len(selected)}部（筛选池，取前N部基于热度排序）")
    print(f"    阶段二 → {total}部（详情池，成功采集10字段）")
    print()
    print("  下一步: 采集短评数据（阶段三脚本待开发）")
    print("=" * 60)


if __name__ == "__main__":
    main()
