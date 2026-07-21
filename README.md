# 豆瓣电影评分稳定性与类型结构变化研究

[仓库地址](https://github.com/NightCruising666/douban-movie-crawler)

## 1. 项目目标

本项目用于《大数据采集与治理》认知实习，完成“数据采集—清洗—统计—可视化—报告”全流程。

- **子课题 A：评分统计稳定性**
  研究豆瓣评分、评价人数、社区参与度与短评星级的关系，比较小众高分与大众经典。
- **子课题 B：豆瓣样本电影的类型结构变化**
  研究 2005—2025 年样本中的类型占比、评分与产地差异。

> 项目不直接宣称“检测刷分”，也不将当前豆瓣标签样本解释为完整电影市场。分析对象是评分的统计稳定性与当前样本结构。

## 2. 数据流程

```text
19个搜索标签
  ↓ 分页获取 + 豆瓣ID去重
movies_raw.csv + movie_tags.csv
  ↓ 详情 API，按ID断点续传
movies.csv（15个原始字段）
  ↓ 每部电影分层采样
reviews.csv（15条热门 + 15条时间排序）
  ↓ 清洗与派生指标
data/processed/*.csv
  ↓
统计分析、可视化、实验报告和PPT
```

## 3. 快速开始

```bash
git clone https://github.com/NightCruising666/douban-movie-crawler.git
cd douban-movie-crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r douban_crawler/requirements.txt
```

查看进度：

```bash
python douban_crawler/main.py --status
python douban_crawler/run_batch.py --status
python douban_crawler/run_stage3.py --status
```

分批续采：

```bash
# 阶段二：默认100部，可调小
python douban_crawler/run_batch.py --batch-size 50

# 阶段三：默认最多处理100部
python douban_crawler/run_stage3.py --batch-size 50
```

重建阶段一的标签来源与排名：

```bash
python douban_crawler/main.py --stage1 --rebuild
```

`--rebuild` 会先将现有阶段一文件移入 `data/archive/stage1_rebuild_时间/`，不会直接删除。

## 4. 当前数据契约

| 文件 | 主键 | 用途 |
|---|---|---|
| `movies_raw.csv` | `豆瓣ID` | 独立电影候选池 |
| `movie_tags.csv` | `豆瓣ID + 标签` | 保留样本来源与标签内排名 |
| `movies.csv` | `豆瓣ID` | 电影详情 |
| `reviews.csv` | `短评ID + 采样方式` | 匿名化短评样本 |
| `review_progress.csv` | `豆瓣ID + 采样方式` | 阶段三断点与穷尽状态 |

详细字段见 [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)。

## 5. 采样设计与局限

1. 阶段一是当前豆瓣标签搜索结果，不是历年全部上映电影的随机样本。
2. 子课题 B 因此描述“豆瓣样本的类型结构变化”，不直接外推到完整市场。
3. 短评分为热门和时间排序两层；如 `time` 参数未生效，应通过两层短评 ID 重复率判断并在报告中说明。
4. 短评星级计算的是“样本五星占比”，不是豆瓣全体评分用户的真实五星比例。
5. 有用数加权反映社区对评论的认可，不能单独用来证明刷分或控评。

## 6. 清洗与分析

```bash
python douban_crawler/src/data_cleaning.py
```

清洗脚本会产生：

- `movies_cleaned.csv`：数值类型、产地分类、短/长评参与率、贝叶斯加权评分。
- `reviews_cleaned.csv`：数值星级、有用数和时间字段。
- `review_metrics.csv`：普通平均、原始有用数加权、对数加权、五星占比及其 95% 置信区间、星级分布熵。

完整统计设计见 [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md)。

## 7. 目录结构

```text
douban_crawler/
├── main.py
├── run_batch.py
├── run_stage3.py
├── src/
│   ├── config.py
│   ├── crawler.py
│   ├── parser.py
│   ├── saver.py
│   └── data_cleaning.py
└── data/
    ├── movies_raw.csv
    ├── movie_tags.csv          # 重建阶段一后生成
    ├── movies.csv              # 阶段二生成
    ├── reviews.csv             # 阶段三生成
    ├── review_progress.csv
    ├── processed/              # 可再生清洗产物，默认不入库
    └── archive/                # 旧版数据，不参与新流程
```

## 8. 合规与隐私

- 只采集研究所需的公开字段，控制请求频率。
- 新版短评表不保存公开用户名，只保存不可逆摘要。
- 不提供验证码规避、账号凭证或代理 IP 自动轮换功能。
- 仓库不应包含 API Key、Cookie、Token、学号或其他个人资料。
