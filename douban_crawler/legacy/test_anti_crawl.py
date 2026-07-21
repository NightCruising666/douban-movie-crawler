"""
测试反爬破解模块
===============
验证 SHA-512 PoW 求解器能否成功突破豆瓣反爬。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.anti_crawl import solve_and_get_cookies, fetch_protected_page

print("=" * 50)
print("反爬破解测试")
print("=" * 50)

# ---- 测试1: 破解反爬获取Cookie ----
print("\n[测试1] 破解反爬，获取Cookie\n")

session = solve_and_get_cookies(
    "https://movie.douban.com/subject/37450627/"
)

if session is None:
    print("\n❌ 破解失败")
    sys.exit(1)

# ---- 测试2: 用Cookie再次访问，看能否拿到真实内容 ----
print(f"\n[测试2] 用Cookie重新访问详情页\n")

resp, session = fetch_protected_page(
    "https://movie.douban.com/subject/37450627/",
    session=session
)

if resp is None or resp.status_code != 200:
    print("❌ 获取页面失败")
    sys.exit(1)

html = resp.text
print(f"  状态码: {resp.status_code}")
print(f"  页面长度: {len(html)} 字符")

# 检查是否拿到了真实内容
# 真实页面会有电影名相关的元素
checks = [
    ("电影名称" in html or "v:itemreviewed" in html, "含有电影相关标签"),
    ("载入中" not in html, "不是空壳页面"),
    ("rating" in html.lower(), "含有评分信息"),
    ("<h1" in html, "含有h1标签"),
    (len(html) > 10000, "页面长度合理(>10000字)"),
]

all_pass = True
for passed, desc in checks:
    status = "✓" if passed else "✗"
    print(f"  {status} {desc}")
    if not passed:
        all_pass = False

if all_pass:
    print("\n✅ 反爬破解成功！可以获取真实页面内容。")
else:
    print("\n⚠ 部分检查未通过，可能需要调整解析策略。")

# 打印页面标题附近的内容帮助调试
print(f"\n[调试] 页面标题: ", end="")
import re
title_match = re.search(r'<title>(.*?)</title>', html)
if title_match:
    print(title_match.group(1))
else:
    print("未找到")
