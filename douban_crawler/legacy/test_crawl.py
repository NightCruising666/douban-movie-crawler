"""
快速测试脚本（API版）
====================
测试所有三个阶段: 搜索 → 详情 → 短评
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from src.crawler import fetch_movies_by_tag, extract_movie_id
from src.parser import parse_movie_detail, parse_movie_reviews

config.DELAY_SECONDS = 1.0  # 测试时加快速度

print("=" * 50)
print("快速验证测试（API版）")
print("=" * 50)

# ---- 测试1: 搜索API ----
print("\n[测试1] 搜索API — 获取'热门'标签前20部电影\n")
data = fetch_movies_by_tag("热门", start=0, limit=20)
if not data:
    print("❌ 测试1失败")
    sys.exit(1)

movies = data["subjects"]
print(f"\n✓ 获取 {len(movies)} 部电影:")
for m in movies[:5]:
    print(f"    《{m['title']}》 评分:{m.get('rate','N/A')}")

# ---- 测试2: 详情API ----
first_id = extract_movie_id(movies[0]["url"])
print(f"\n[测试2] 详情API — 电影ID: {first_id}\n")
time.sleep(config.DELAY_SECONDS)

detail = parse_movie_detail(first_id)
if not detail:
    print("❌ 测试2失败")
    sys.exit(1)

print("\n✓ 10字段提取结果:")
for k, v in detail.items():
    display = str(v)[:60] + "..." if len(str(v)) > 60 else str(v)
    print(f"    {k}: {display}")

# ---- 测试3: 短评API ----
print(f"\n[测试3] 短评API — 获取《{movies[0]['title']}》前20条\n")
time.sleep(config.DELAY_SECONDS)

reviews = parse_movie_reviews(first_id, movies[0]["title"], max_reviews=20)
if not reviews:
    print("❌ 测试3失败")
    sys.exit(1)

print(f"\n✓ 获取 {len(reviews)} 条短评，预览:")
for r in reviews[:3]:
    print(f"    用户:{r['用户名称']:12s}  {r['评分']:5s}  有用:{r['有用数']:5s}")
    content = r['短评正文'][:60] + "..." if len(r['短评正文']) > 60 else r['短评正文']
    print(f"    「{content}」\n")

print("=" * 50)
print("✅ 全部测试通过！可以开始正式采集:")
print("   python main.py")
print("=" * 50)
