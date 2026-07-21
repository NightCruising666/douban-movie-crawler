"""项目配置与数据契约。

所有采集脚本共用本文件中的路径、字段和速率参数，避免同一个 CSV
在不同脚本中出现不同表头。
"""

from __future__ import annotations

import random


# ==================== HTTP ====================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3


def random_delay(base: float) -> float:
    """在基准延迟上添加 ±30% 随机抖动。"""
    jitter = base * 0.3
    return base + random.uniform(-jitter, jitter)


SEARCH_DELAY_BASE = 2.0
DETAIL_DELAY_BASE = 5.0
COOLDOWN_EVERY_N = 15
COOLDOWN_SECONDS = 45
FAIL_PAUSE_SHORT = 10
FAIL_PAUSE_MEDIUM = 45
FAILURE_COOLDOWN_BASE = 900.0
FAILURE_RETRIES = 1
MAX_CONSECUTIVE_FAILURES = 3
MINIMUM_RUNTIME_HOURS = 3.0


# ==================== API 与采集范围 ====================

SEARCH_API = "https://movie.douban.com/j/search_subjects"
PAGE_SIZE = 20
MAX_PER_TAG = 200
BATCH_SIZE = 100

MOVIE_TAGS = [
    "热门",
    "最新",
    "经典",
    "可播放",
    "豆瓣高分",
    "冷门佳片",
    "华语",
    "欧美",
    "韩国",
    "日本",
    "动作",
    "喜剧",
    "爱情",
    "科幻",
    "悬疑",
    "恐怖",
    "剧情",
    "动画",
    "纪录片",
]

# 2026-07-21 对 time/latest/new_score/newest 进行小规模验证：除 latest
# 返回空外，其余与 hot 前15条重合14条，不能视为独立时间样本。
# 因此当前只保留一个明确的“热门”样本层，不伪造分层采样。
REVIEW_SAMPLING_PLAN = (
    {"label": "热门", "order_by": "hot", "limit": 30},
)

TARGET_MOVIES = None  # None = movies_raw.csv 全量


# ==================== 路径 ====================

CSV_ENCODING = "utf-8-sig"
MOVIES_RAW_CSV = "data/movies_raw.csv"
MOVIE_TAGS_CSV = "data/movie_tags.csv"
MOVIES_CSV = "data/movies.csv"
REVIEWS_CSV = "data/reviews.csv"
REVIEW_PROGRESS_CSV = "data/review_progress.csv"
DETAIL_FAILURES_CSV = "data/detail_failures.csv"
UNAVAILABLE_MOVIES_CSV = "data/unavailable_movies.csv"


# ==================== CSV 表头 ====================

RAW_MOVIE_FIELDS = ["豆瓣ID", "电影名称", "搜索评分", "URL", "采集时间"]

MOVIE_TAG_FIELDS = ["豆瓣ID", "标签", "标签内排名", "采集时间"]

MOVIE_FIELDS = [
    "豆瓣ID",
    "电影名称",
    "原始片名",
    "导演",
    "主演",
    "上映年份",
    "首映日期",
    "类型",
    "国家/地区",
    "片长",
    "豆瓣评分",
    "评价人数",
    "短评总数",
    "长评总数",
    "采集时间",
]

REVIEW_FIELDS = [
    "短评ID",
    "豆瓣ID",
    "电影名称",
    "评分",
    "短评正文",
    "有用数",
    "评论时间",
    "采样方式",
    "排序位置",
    "采集时间",
]

REVIEW_PROGRESS_FIELDS = [
    "豆瓣ID",
    "电影名称",
    "采样方式",
    "目标数",
    "已采集数",
    "状态",
    "更新时间",
]

DETAIL_FAILURE_FIELDS = [
    "豆瓣ID",
    "电影名称",
    "最后失败原因",
    "首次失败轮次",
    "最后失败轮次",
    "失败轮次数",
    "永久失败轮次数",
    "连续永久失败轮次数",
    "状态",
    "首次失败时间",
    "最后更新时间",
]
