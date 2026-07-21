"""豆瓣 JSON API 解析与记录标准化。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from . import config
from .crawler import safe_get


def now_iso() -> str:
    """返回带时区的本地采集时间。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _join_names(items: Iterable[dict], limit: int | None = None) -> str:
    values = list(items)
    if limit is not None:
        values = values[:limit]
    return " / ".join(str(item.get("name", "")).strip() for item in values if item.get("name"))


def _normalize_release_date(value: object) -> str:
    """将 API 中的字符串或列表日期归一为 YYYY[-MM[-DD]]。"""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    text = str(value or "")
    match = re.search(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", text)
    if not match:
        return ""
    year, month, day = match.groups()
    if day:
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if month:
        return f"{year}-{int(month):02d}"
    return year


def transform_movie_detail(movie_id: str, data: dict, captured_at: str | None = None) -> dict:
    """将详情 API JSON 转换为稳定的电影表记录。"""
    rating = data.get("rating") or {}
    release_date = _normalize_release_date(data.get("release_date") or data.get("pubdate"))

    return {
        "豆瓣ID": str(movie_id),
        "电影名称": str(data.get("title", "")),
        "原始片名": str(data.get("original_title", "")),
        "导演": _join_names(data.get("directors") or []),
        "主演": _join_names(data.get("actors") or [], limit=15),
        "上映年份": str(data.get("year", "")),
        "首映日期": str(release_date),
        "类型": " / ".join(data.get("genres") or []),
        "国家/地区": " / ".join(data.get("countries") or []),
        "片长": " / ".join(data.get("durations") or []),
        "豆瓣评分": str(rating.get("value", "")),
        "评价人数": str(rating.get("count", "")),
        "短评总数": str(data.get("comment_count", "")),
        "长评总数": str(data.get("review_count", "")),
        "采集时间": captured_at or now_iso(),
    }


def parse_movie_detail_with_reason(
    movie_id: str,
    transport_attempts: list[dict] | None = None,
) -> tuple[dict | None, str]:
    """请求详情 API，同时返回可持久化的失败原因。"""
    url = f"https://m.douban.com/rexxar/api/v2/movie/{movie_id}"
    headers = {
        **config.HEADERS,
        "Referer": f"https://m.douban.com/movie/subject/{movie_id}/",
    }

    print(f"  请求详情API: {movie_id} ...", end=" ", flush=True)
    def audit_transport_failure(reason: str) -> None:
        if transport_attempts is not None:
            transport_attempts.append(
                {
                    "尝试层级": "传输重试",
                    "失败原因": reason,
                    "失败时间": now_iso(),
                }
            )

    response = safe_get(url, headers=headers, failure_audit=audit_transport_failure)
    if response is None:
        print("✗ 请求失败")
        return None, "网络请求失败"
    if response.status_code != 200:
        print(f"✗ HTTP {response.status_code}")
        return None, f"HTTP {response.status_code}"

    try:
        data = response.json()
        if not isinstance(data, dict):
            raise TypeError("详情接口JSON顶层不是对象")
        record = transform_movie_detail(movie_id, data)
    except (AttributeError, TypeError, ValueError):
        print("✗ JSON解析失败")
        return None, "JSON解析失败"

    print(f"✓ 《{record['电影名称']}》评分{record['豆瓣评分']}")
    return record, ""


def parse_movie_detail(movie_id: str) -> dict | None:
    """兼容旧调用：成功返回详情，失败返回 ``None``。"""
    record, _ = parse_movie_detail_with_reason(movie_id)
    return record


def transform_review_item(
    movie_id: str,
    movie_title: str,
    item: dict,
    sample_label: str,
    rank: int,
    captured_at: str | None = None,
) -> dict:
    """将短评 API 条目转换为不含用户身份字段的标准记录。"""
    rating = item.get("rating") or {}
    value = rating.get("value")
    stars = f"{int(value)}星" if value not in (None, "") else "未评分"

    return {
        "短评ID": str(item.get("id", "")),
        "豆瓣ID": str(movie_id),
        "电影名称": movie_title,
        "评分": stars,
        "短评正文": str(item.get("comment", "")),
        "有用数": str(item.get("vote_count", 0)),
        "评论时间": str(item.get("create_time", "")),
        "采样方式": sample_label,
        "排序位置": str(rank),
        "采集时间": captured_at or now_iso(),
    }


def fetch_review_sample(
    movie_id: str,
    movie_title: str,
    *,
    sample_label: str,
    order_by: str,
    rank_limit: int,
    existing_keys: set[tuple[str, str]] | None = None,
) -> dict:
    """
    采集一个排序口径下的前 ``rank_limit`` 条短评。

    返回 ``records``、``exhausted`` 和 ``request_failed``，供阶段三脚本保存
    分采样方式的断点状态。
    """
    existing_keys = existing_keys or set()
    records: list[dict] = []
    start = 0
    page_size = 20
    exhausted = False

    headers = {
        **config.HEADERS,
        "Referer": f"https://m.douban.com/movie/subject/{movie_id}/",
    }

    while start < rank_limit:
        count = min(page_size, rank_limit - start)
        url = (
            f"https://m.douban.com/rexxar/api/v2/movie/{movie_id}/interests"
            f"?count={count}&start={start}&order_by={order_by}"
        )
        response = safe_get(url, headers=headers)
        if response is None or response.status_code != 200:
            return {"records": records, "exhausted": False, "request_failed": True}

        try:
            data = response.json()
        except (TypeError, ValueError):
            return {"records": records, "exhausted": False, "request_failed": True}

        items = data.get("interests") or []
        if not items:
            exhausted = True
            break

        captured_at = now_iso()
        for offset, item in enumerate(items):
            rank = start + offset + 1
            if rank > rank_limit:
                break
            review_id = str(item.get("id", ""))
            key = (review_id, sample_label)
            if review_id and key not in existing_keys:
                records.append(
                    transform_review_item(
                        movie_id,
                        movie_title,
                        item,
                        sample_label,
                        rank,
                        captured_at,
                    )
                )
                existing_keys.add(key)

        start += len(items)
        total = int(data.get("total") or 0)
        if len(items) < count or (total and start >= total):
            exhausted = True
            break

        if start < rank_limit:
            import time

            time.sleep(config.random_delay(config.DETAIL_DELAY_BASE))

    return {"records": records, "exhausted": exhausted, "request_failed": False}


def parse_movie_reviews(movie_id: str, movie_title: str, max_reviews: int = 20) -> list[dict]:
    """兼容旧调用：返回热门排序前 ``max_reviews`` 条。"""
    result = fetch_review_sample(
        movie_id,
        movie_title,
        sample_label="热门",
        order_by="hot",
        rank_limit=max_reviews,
    )
    return result["records"]
