"""
豆瓣爬虫配置文件
==============
集中管理所有可调参数，方便后期修改。
不要在各个模块里硬编码URL和参数！
"""

# ========== HTTP请求配置 ==========

# User-Agent：模拟浏览器身份。豆瓣不检查UA时用这个就够了。
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 请求超时时间（秒）
REQUEST_TIMEOUT = 10

# ========== 请求间隔 & 随机延迟 ==========
# 为什么用随机延迟？
#   固定间隔容易被反爬系统识别为机器行为（周期性规律）
#   随机 ±30% 的抖动模拟人类阅读页面的自然节奏
#   反爬系统的行为分析会降低对"有波动"请求的敏感度

import random as _random

def random_delay(base):
    """在基准延迟上添加 ±30% 随机抖动"""
    jitter = base * 0.3
    return base + _random.uniform(-jitter, jitter)

# 搜索API（阶段一）：基础 2 秒 ± 30% → 1.4~2.6 秒
SEARCH_DELAY_BASE = 2.0

# Rexxar API（阶段二/三）：基础 5 秒 ± 30% → 3.5~6.5 秒
#   从 3s 提升到 5s，降低单 IP 请求速率
DETAIL_DELAY_BASE = 5.0

# 主动冷却：每 N 部成功后强制休息（给 IP 缓冲时间）
COOLDOWN_EVERY_N = 15       # 每 15 部
COOLDOWN_SECONDS = 45       # 休息 45 秒

# 连续失败后的冷却（豆瓣硬限后需要更长时间恢复）
FAIL_PAUSE_SHORT = 10       # 1-3次失败：等 10 秒
FAIL_PAUSE_MEDIUM = 45      # 4-6次失败：等 45 秒
FAIL_PAUSE_LONG = 120       # 7-9次失败：等 2 分钟
FAIL_PAUSE_HARD = 600       # ≥10次失败：等 10 分钟（IP级别限制）

# 请求失败后最大重试次数
MAX_RETRIES = 3

# ========== 豆瓣API配置 ==========

# 豆瓣电影搜索API
# 参数: type=movie, tag=标签名, page_limit=每页数, page_start=偏移量
SEARCH_API = "https://movie.douban.com/j/search_subjects"

# 单次请求返回条数（豆瓣上限是20）
PAGE_SIZE = 20

# 每个标签最多可获取的记录数（豆瓣限制约200条）
MAX_PER_TAG = 200

# ========== 电影标签列表 ==========
# 用于翻页采集时按标签遍历。
# 相邻标签会有重复电影，需要在保存前去重。

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

# ========== 输出配置 ==========

# CSV保存路径（相对于项目根目录）
MOVIES_RAW_CSV = "data/movies_raw.csv"   # 阶段一原始列表（全部去重电影）
MOVIES_CSV = "data/movies.csv"           # 阶段二电影详情
REVIEWS_CSV = "data/reviews.csv"         # 阶段三短评

# CSV编码
CSV_ENCODING = "utf-8-sig"  # utf-8-sig → Excel能正确打开中文

# ========== 翻页配置 ==========

# 目标电影数
TARGET_MOVIES = 2478        # 全量采集 raw 中的所有电影

# 每部电影短评数
REVIEWS_PER_MOVIE = 30      # 阶段三用

# 每部电影拉取的最大短评数（豆瓣短评约200条可见）
MAX_REVIEWS_PER_MOVIE = 200
