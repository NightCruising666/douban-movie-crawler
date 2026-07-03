"""
数据解析模块（API版）
==================
豆瓣移动版提供了 JSON API，比 HTML 解析更稳定、更快速。

三个核心 API:
  1. 搜索API: /j/search_subjects          → 电影列表
  2. 详情API: /rexxar/api/v2/movie/{id}   → 电影10字段
  3. 评论API: /rexxar/api/v2/movie/{id}/interests → 短评数据

优缺点对比:
  HTML解析: 依赖页面结构，豆瓣改版就失效
  API调用:   返回JSON，结构稳定，字段规范
"""

from . import config
from .crawler import safe_get


# ==================== 电影详情 ====================

def parse_movie_detail(movie_id):
    """
    从豆瓣 Rexxar API 获取电影详情，提取10个字段。

    API: https://m.douban.com/rexxar/api/v2/movie/{movie_id}

    返回JSON结构:
    {
      "title": "痴迷",
      "original_title": "Obsession",
      "year": 2025,
      "genres": ["恐怖"],
      "countries": ["美国"],
      "durations": ["108分钟"],
      "directors": [{"name": "库里·巴克"}],
      "actors": [{"name": "迈克尔·约翰斯顿"}, ...],
      "rating": {"value": 7.7, "count": 15087, "max": 10, "star_count": 4.0},
      "intro": "剧情简介文字..."
    }

    参数:
        movie_id: 豆瓣电影ID（如 "37450627"）

    返回:
        dict: 10个字段的字典；失败返回 None
    """
    url = f"https://m.douban.com/rexxar/api/v2/movie/{movie_id}"

    print(f"  请求详情API: {movie_id} ...", end=" ", flush=True)

    # 移动API需要特殊的请求头
    api_headers = {
        **config.HEADERS,
        "Referer": f"https://m.douban.com/movie/subject/{movie_id}/",
    }

    response = safe_get(url, headers=api_headers)

    if response is None or response.status_code != 200:
        print("✗ 请求失败")
        return None

    try:
        data = response.json()
    except Exception:
        print("✗ JSON解析失败")
        return None

    # 提取导演（列表 → 逗号分隔字符串）
    directors = data.get("directors", [])
    director_str = " / ".join(d.get("name", "") for d in directors)

    # 提取主演（取前15个，太多了CSV不好看）
    actors = data.get("actors", [])
    actor_str = " / ".join(a.get("name", "") for a in actors[:15])

    # 提取评分
    rating_data = data.get("rating", {})
    rating_value = rating_data.get("value", "")
    rating_count = rating_data.get("count", "")

    # 拼接类型
    genres = data.get("genres", [])
    genre_str = " / ".join(genres)

    # 拼接国家
    countries = data.get("countries", [])
    country_str = " / ".join(countries)

    # 拼接片长
    durations = data.get("durations", [])
    duration_str = " / ".join(durations)

    movie = {
        "电影名称": data.get("title", ""),
        "导演": director_str,
        "主演": actor_str,
        "上映年份": str(data.get("year", "")),
        "类型": genre_str,
        "国家/地区": country_str,
        "片长": duration_str,
        "豆瓣评分": str(rating_value),
        "评价人数": str(rating_count),
        "五星占比": "",  # Rexxar API 不直接提供五星占比
        "短评总数": str(data.get("comment_count", "")),
        "长评总数": str(data.get("review_count", "")),
    }

    print(f"✓ 《{movie['电影名称']}》评分{movie['豆瓣评分']}")
    return movie


# ==================== 短评采集 ====================

def parse_movie_reviews(movie_id, movie_title, max_reviews=None):
    """
    从豆瓣 Rexxar API 获取电影短评。

    API: https://m.douban.com/rexxar/api/v2/movie/{movie_id}/interests

    返回JSON结构:
    {
      "total": 1234,
      "start": 0,
      "count": 20,
      "interests": [
        {
          "comment": "短评正文",
          "create_time": "2026-05-16 06:10:44",
          "rating": {"value": 5, "max": 5},   # 用户打分(1-5星)
          "user": {"name": "用户名"},
          "vote_count": 123                     # 有用数
        },
        ...
      ]
    }

    参数:
        movie_id:    豆瓣电影ID（字符串）
        movie_title: 电影名称（用于CSV记录）
        max_reviews: 最多获取数

    返回:
        list[dict]: 短评列表，每条约6个字段
    """
    if max_reviews is None:
        max_reviews = config.MAX_REVIEWS_PER_MOVIE

    all_reviews = []
    start = 0
    count_per_page = 20  # API每页20条

    api_headers = {
        **config.HEADERS,
        "Referer": f"https://m.douban.com/movie/subject/{movie_id}/",
    }

    while len(all_reviews) < max_reviews:
        url = (
            f"https://m.douban.com/rexxar/api/v2/movie/{movie_id}/interests"
            f"?count={count_per_page}&start={start}&order_by=hot"
        )

        response = safe_get(url, headers=api_headers)
        if response is None or response.status_code != 200:
            break

        try:
            data = response.json()
        except Exception:
            break

        interests = data.get("interests", [])
        if not interests:
            break  # 没有更多短评了

        for item in interests:
            # 用户评分: API返回1-5星级，转换为"X星"格式
            user_rating = item.get("rating", {})
            if user_rating and user_rating.get("value"):
                stars = str(int(user_rating["value"])) + "星"
            else:
                stars = "未评分"

            # 有用数
            vote_count = item.get("vote_count", 0)

            review = {
                "电影名称": movie_title,
                "用户名称": item.get("user", {}).get("name", ""),
                "评分": stars,
                "短评正文": item.get("comment", ""),
                "有用数": str(vote_count),
                "评论时间": item.get("create_time", ""),
            }

            all_reviews.append(review)

            if len(all_reviews) >= max_reviews:
                break

        start += count_per_page

        # 检查是否已经获取了全部可用的
        total = data.get("total", 0)
        if start >= total:
            break

    print(f"  《{movie_title}》: 获取 {len(all_reviews)} 条短评")
    return all_reviews
