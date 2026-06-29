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

# 请求间隔（秒）——反爬的关键参数！
# 搜索API（阶段一）：2秒够用，约380次请求无问题
# Rexxar API（阶段二）：豆瓣对详情API更敏感，需更大间隔
DELAY_SECONDS = 2.0         # 搜索API用
DETAIL_DELAY_SECONDS = 3.0  # Rexxar API用（阶段二/三）

# Rexxar API 速率限制策略
# 每采集 N 部电影后主动休息，防止触发豆瓣硬限
COOLDOWN_EVERY_N = 30       # 每 N 部电影
COOLDOWN_SECONDS = 30       # 休息秒数

# 连续失败处理
# 触发硬限后需要更长的冷却时间（豆瓣IP限制通常在5-10分钟恢复）
FAIL_COOLDOWN_SHORT = 5     # 短冷却（连续失败 ≤5次）
FAIL_COOLDOWN_LONG = 30     # 长冷却（连续失败 6-10次）
FAIL_COOLDOWN_HARD = 300    # 硬冷却（连续失败 >10次，IP级别限制）

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
TARGET_MOVIES = 500

# 每部电影拉取的最大短评数（豆瓣短评约200条可见）
MAX_REVIEWS_PER_MOVIE = 200
