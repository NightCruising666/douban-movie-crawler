"""
网络请求模块
===========
负责与豆瓣服务器通信：发送请求、处理响应、重试逻辑。
不负责解析数据——解析交给 parser.py。
"""

import re
import time
import requests
from . import config


def safe_get(url, params=None, headers=None, timeout=None, failure_audit=None):
    """
    安全的GET请求：带重试、带延迟、带异常处理。

    为什么这样设计？
    - 网络不稳定时自动重试（最多MAX_RETRIES次）
    - SSL错误也算作可重试的失败
    - 失败时打印清晰的错误信息，方便调试

    参数:
        url: 请求地址
        params: URL参数字典（可选）
        headers: 自定义请求头（不传则用config里的默认值）
        timeout: 超时秒数（不传则用config里的默认值）
        failure_audit: 可选回调，每次底层传输失败时接收原因字符串

    返回:
        成功: requests.Response 对象
        失败: None
    """
    if headers is None:
        headers = config.HEADERS
    if timeout is None:
        timeout = config.REQUEST_TIMEOUT

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
            return response

        except requests.exceptions.SSLError as e:
            # SSL错误：有时是网络波动，重试
            if failure_audit:
                failure_audit("SSL错误")
            print(f"  [SSL错误] 第{attempt}次重试... ({e})")
            time.sleep(2)

        except requests.exceptions.ConnectionError as e:
            # 连接被拒绝或DNS失败
            if failure_audit:
                failure_audit("连接错误")
            print(f"  [连接错误] 第{attempt}次重试... ({e})")
            time.sleep(3)

        except requests.exceptions.Timeout as e:
            # 超时
            if failure_audit:
                failure_audit("请求超时")
            print(f"  [超时] 第{attempt}次重试... ({e})")
            time.sleep(2)

        except requests.exceptions.RequestException as e:
            # 其他所有requests异常
            if failure_audit:
                failure_audit("请求异常")
            print(f"  [请求失败] {e}")
            return None

    print(f"  [放弃] 重试{config.MAX_RETRIES}次后仍然失败: {url}")
    return None


def fetch_movies_by_tag(tag, start=0, limit=None):
    """
    从豆瓣搜索API获取指定标签的电影列表。

    API: https://movie.douban.com/j/search_subjects

    返回JSON格式:
    {
        "subjects": [
            {
                "title": "电影名",
                "url": "https://movie.douban.com/subject/37450627/",
                "rate": "7.7",
                "cover": "封面图URL"
            },
            ...
        ]
    }

    参数:
        tag:   电影标签（如"热门"、"科幻"）
        start: 起始偏移
        limit: 本次最多获取数（默认config.PAGE_SIZE）

    返回:
        成功: JSON数据字典，含subjects列表
        失败: None
    """
    if limit is None:
        limit = config.PAGE_SIZE

    params = {
        "type": "movie",
        "tag": tag,
        "page_limit": limit,
        "page_start": start,
    }

    print(f"  请求标签 '{tag}'  offset={start} ...", end=" ")

    response = safe_get(config.SEARCH_API, params=params)

    if response is None:
        print("失败")
        return None

    if response.status_code == 200:
        data = response.json()
        count = len(data.get("subjects", []))
        print(f"✓ 获取 {count} 条")
        return data
    else:
        print(f"✗ HTTP {response.status_code}")
        return None


def fetch_all_movies_for_tag_with_status(tag):
    """
    获取某个标签下的全部电影（自动翻页）。

    豆瓣搜索API每标签上限约200条。

    参数:
        tag: 电影标签

    返回:
        tuple[list[dict], bool]: 电影列表和标签是否完整采集
    """
    all_subjects = []
    offset = 0
    complete = True

    while offset < config.MAX_PER_TAG:
        data = fetch_movies_by_tag(tag, start=offset)

        if data is None:
            complete = False
            break

        subjects = data.get("subjects", [])
        if not subjects:
            break

        all_subjects.extend(subjects)
        offset += len(subjects)

        if len(subjects) < config.PAGE_SIZE:
            break

        time.sleep(config.random_delay(config.SEARCH_DELAY_BASE))

    print(f"  标签 '{tag}' 共计 {len(all_subjects)} 部电影")
    return all_subjects, complete


def fetch_all_movies_for_tag(tag):
    """兼容旧调用：只返回电影列表。"""
    subjects, _ = fetch_all_movies_for_tag_with_status(tag)
    return subjects


def extract_movie_id(url):
    """
    从豆瓣电影URL中提取电影ID。

    输入: "https://movie.douban.com/subject/37450627/"
    输出: "37450627"

    参数:
        url: 豆瓣电影完整URL

    返回:
        str: 豆瓣电影ID；提取失败返回空字符串
    """
    if not url:
        return ""

    # 匹配 /subject/数字/ 的模式
    match = re.search(r"/subject/(\d+)/?", url)
    if match:
        return match.group(1)

    return ""
