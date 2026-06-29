"""
豆瓣反爬破解模块
===============
破解豆瓣的 SHA-512 工作量证明（Proof-of-Work）反爬机制。

机制原理:
  1. 豆瓣返回空壳页面，内含一个 <form>，字段包括:
     - tok: 会话令牌
     - cha: 挑战字符串（随机生成）
     - red: 目标页面URL（Base64编码）
  2. 浏览器JS执行 SHA-512(cha + nonce)，找一个nonce使哈希以"0000"开头
  3. 提交表单到 /c，服务器验证后设置Cookie，重定向到真实页面

为什么要破解而不是用Playwright？
  - Playwright启动浏览器要2-3秒，爬500部电影就是1000秒开销
  - 纯Python计算SHA-512只需1-3秒，且不占内存
  - 答辩时能讲清楚原理，展示你理解了反爬机制

知识点:
  - hashlib.sha512: Python内置的SHA-512哈希函数
  - 工作量证明: 和比特币挖矿同原理（找特定前缀的哈希）
  - Cookie维持会话: 拿到Cookie后所有请求共用同一个Session
"""

import re
import hashlib
import requests
from . import config


# ---- 第一步：从防爬页面提取挑战参数 ----

def extract_challenge(html):
    """
    从豆瓣反爬页面中提取 tok、cha、red 三个隐藏字段。

    豆瓣反爬页面的表单结构:

    <form name="sec" id="sec" method="POST" action="/c">
      <input type="hidden" id="tok" name="tok" value="1782732860@a6f32..." />
      <input type="hidden" id="cha" name="cha" value="8b7ffa380d88..." />
      <input type="hidden" id="sol" name="sol" value="" />
      <input type="hidden" id="red" name="red" value="https://movie.douban.com/subject/..." />
    </form>

    返回:
        (tok, cha, red) 三元组，提取失败返回 (None, None, None)
    """
    tok_match = re.search(r'name="tok"\s+value="([^"]+)"', html)
    cha_match = re.search(r'name="cha"\s+value="([^"]+)"', html)
    red_match = re.search(r'name="red"\s+value="([^"]+)"', html)

    if tok_match and cha_match and red_match:
        return tok_match.group(1), cha_match.group(1), red_match.group(1)

    return None, None, None


# ---- 第二步：解SHA-512工作量证明 ----

def solve_pow(cha, difficulty=4):
    """
    求解工作量证明: 找到一个 nonce，使 SHA-512(cha + nonce) 以 N 个 '0' 开头。

    为什么是SHA-512而不是SHA-256？
    - 豆瓣前端用了 crypto.subtle.digest('SHA-512', ...)
    - 我们必须在Python里做完全相同的计算

    时间复杂度:
    - difficulty=4  → 平均尝试 2^16 = 65536 次 → 约 1-3 秒
    - difficulty=5  → 平均尝试 2^20 ≈ 100万次   → 约 30-60 秒
    - 目前豆瓣用的是 difficulty=4

    参数:
        cha:       挑战字符串（从豆瓣页面提取）
        difficulty: 哈希前缀需要几个零

    返回:
        找到的 nonce 值（整数）
    """
    target_prefix = "0" * difficulty  # difficulty=4 → "0000"
    nonce = 0

    print(f"    求解PoW (目标: 哈希以 '{target_prefix}' 开头)...", end=" ", flush=True)

    while True:
        # SHA-512(挑战字符串 + nonce)
        data = f"{cha}{nonce}".encode("utf-8")
        hash_result = hashlib.sha512(data).hexdigest()

        if hash_result.startswith(target_prefix):
            print(f"✓ nonce={nonce}  (尝试{nonce + 1}次)")
            return nonce

        nonce += 1

        # 每尝试10万次打印一次进度（防止看起来卡死）
        if nonce % 100000 == 0:
            print(f"\n    已尝试 {nonce} 次，继续...", end=" ", flush=True)


# ---- 第三步：提交解，获取Cookie ----

def solve_and_get_cookies(url, session=None):
    """
    完整破解流程:
      1. 访问目标URL → 拿到反爬页面
      2. 提取挑战参数 (tok, cha, red)
      3. 计算SHA-512工作量证明
      4. POST到 /c 提交答案
      5. 从响应中获取 Cookie

    参数:
        url:     目标URL（如 'https://movie.douban.com/subject/37450627/'）
        session: requests.Session对象（复用TCP连接和Cookie）

    返回:
        成功: requests.Session（已含Cookie）
        失败: None
    """
    if session is None:
        session = requests.Session()
        session.headers.update(config.HEADERS)

    print(f"  破解反爬: {url}")

    # Step 1: 访问目标页面，拿到反爬挑战
    resp = session.get(url, timeout=config.REQUEST_TIMEOUT)
    if resp.status_code != 200:
        print(f"    ✗ 无法访问页面 (HTTP {resp.status_code})")
        return None

    html = resp.text

    # Step 2: 提取挑战参数
    tok, cha, red = extract_challenge(html)
    if not tok:
        print(f"    ✗ 未找到挑战参数（可能不需要反爬）")
        # 如果页面直接返回了内容（没有挑战），直接返回session
        if "载入中" not in html:
            return session
        print(f"    页面显示'载入中'但提取失败，放弃")
        return None

    # Step 3: 求解PoW
    sol = solve_pow(cha, difficulty=4)

    # Step 4: 提交答案到 /c
    # 豆瓣的 /c 端点用于验证反爬挑战
    solve_url = "https://movie.douban.com/c"
    form_data = {
        "tok": tok,
        "cha": cha,
        "sol": str(sol),
        "red": red,
    }

    print(f"    提交答案到 /c ...", end=" ", flush=True)

    try:
        # 提交表单，豆瓣验证后设置Cookie并返回302重定向
        # allow_redirects=True 会自动跟随重定向到目标页面
        resp2 = session.post(
            solve_url,
            data=form_data,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True
        )
        print(f"✓ HTTP {resp2.status_code}")

        # 验证Cookie是否设置成功
        # 豆瓣会设置 bid、dbcl2 等Cookie
        cookies = session.cookies.get_dict()
        if cookies:
            print(f"    获取到Cookie: {list(cookies.keys())}")
            return session
        else:
            print(f"    ⚠ Cookie为空，但继续尝试...")
            return session

    except Exception as e:
        print(f"✗ {e}")
        return None


# ---- 综合函数：获取受保护页面的内容 ----

def fetch_protected_page(url, session=None):
    """
    获取受反爬保护的豆瓣页面。

    流程:
    - 如果session已有有效Cookie，直接用
    - 如果没有，先破解反爬获取Cookie，再访问

    返回:
        成功: (response, session)
        失败: (None, session)
    """
    if session is None:
        session = requests.Session()
        session.headers.update(config.HEADERS)

    # 直接尝试访问
    resp = session.get(url, timeout=config.REQUEST_TIMEOUT)

    # 检查是否触发反爬
    html = resp.text
    if "载入中" in html or "loading" in html.lower():
        # 触发了反爬，需要破解
        print(f"  触发反爬: {url}")
        session = solve_and_get_cookies(url, session)
        if session is None:
            return None, None

        # 破解后重新访问
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT)

    return resp, session
