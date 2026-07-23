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
  ↓ 每部电影定额采样
reviews.csv（前30条热门短评）
  ↓ 清洗与派生指标
data/processed/*.csv
  ↓
run_analysis.py
  ↓
data/analysis/*.csv + *.png
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

当前仓库数据状态：

| 数据 | 数量 | 状态 |
|---|---:|---|
| 新版候选电影池 `movies_raw.csv` | 2601 部 | 阶段一已完成，19 个标签 |
| 新版电影详情 `movies.csv` | 2601 部 | 阶段二已完成，ID无重复 |
| 阶段二失败复核 | 12 部 | 均已恢复，确认不可用0部 |
| 新版正式短评 | 0 条 | 阶段三尚未开始 |
| 旧电影详情 | 499 部完整旧表 + 135 部部分新表 | 已归档，不计入新版断点 |
| 旧短评 | 9980 条正式数据 + 200 条试采 | 已删除用户标识并归档 |

旧表缺少稳定的豆瓣 ID 或与新版字段不一致，因此保留作采集过程证据，但不会与新版正式表直接拼接。

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

# 阶段二低速长批次：间隔约8.4—15.6秒，每10部冷却60秒
python douban_crawler/run_batch.py --batch-size 2601 --delay-base 12 --cooldown-every 10 --cooldown-seconds 60 --minimum-runtime-hours 3

# 持续监督：失败不停止，一轮结束后自动补采遗漏ID
python douban_crawler/run_stage2_continuous.py

# 阶段三：默认最多处理100部
python douban_crawler/run_stage3.py --batch-size 50
```

清洗与分析：

```bash
python douban_crawler/run_cleaning.py
python douban_crawler/run_analysis.py
```

重建阶段一的标签来源与排名：

```bash
python douban_crawler/main.py --stage1 --rebuild
```

`--rebuild` 会将当前阶段一至阶段三文件一起移入 `data/archive/pipeline_rebuild_时间/`，避免新电影池与旧详情、旧短评混用，也不会直接删除数据。

## 4. 当前数据契约

| 文件 | 主键 | 用途 |
|---|---|---|
| `movies_raw.csv` | `豆瓣ID` | 独立电影候选池 |
| `movie_tags.csv` | `豆瓣ID + 标签` | 保留样本来源与标签内排名 |
| `movies.csv` | `豆瓣ID` | 电影详情 |
| `detail_failures.csv` | `豆瓣ID` | 阶段二失败轮次、原因与恢复状态 |
| `detail_failure_attempts.csv` | `豆瓣ID + 轮次 + 尝试序号` | 每次电影级失败请求的审计记录 |
| `unavailable_movies.csv` | `豆瓣ID` | 从失败状态事实表重建的不可用条目快照 |
| `reviews.csv` | `短评ID + 采样方式` | 不含用户标识的短评样本 |
| `review_progress.csv` | `豆瓣ID + 采样方式` | 阶段三断点与穷尽状态 |

详细字段见 [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)。

## 5. 采样设计与局限

1. 阶段一是当前豆瓣标签搜索结果，不是历年全部上映电影的随机样本。
2. 子课题 B 因此描述“豆瓣样本的类型结构变化”，不直接外推到完整市场。
3. 每部电影采集热门排序前 30 条短评。2026-07-21 小规模验证中，`time`、`new_score`、`newest` 与 `hot` 的前 15 条均重合 14 条，`latest` 返回空，因此不把这些参数伪装成独立的“近期层”。
4. 短评星级计算的是“样本五星占比”，不是豆瓣全体评分用户的真实五星比例。
5. 有用数加权反映社区对评论的认可，不能单独用来证明刷分或控评。
6. 热门排序会放大高互动评论，样本不能代表全部短评；报告必须同时使用电影总体评分和评价人数，短评仅作辅助验证。
7. 持续监督模式下，阶段二失败会随机冷却约 10.5—19.5 分钟并重试一次；仍失败则暂时跳过。连续失败不会结束进程；只有 HTTP 400/404/410 连续两个不同轮次失败才记为“不可用”，网络错误、403、429 不会永久排除。
8. 阶段二完成标准是“成功详情数 + 确认不可用数 = 候选电影总数”。失败证据单独保留，报告中应披露不可用比例。

## 6. 清洗与分析

```bash
python douban_crawler/run_cleaning.py
```

清洗脚本会产生：

- `movies_cleaned.csv`：2601条清洗主表，包含质量标记和两个课题的纳入标志。
- `movies_cleaning_report.csv`：缺失、异常、筛选数量与比例。
- `movies_cleaning_rules.csv`：每条清洗规则、处理方式、选择原因、未采用方法和命中数。
- `reviews_cleaned.csv`：数值星级、有用数和时间字段。
- `review_metrics.csv`：普通平均、原始有用数加权、对数加权、五星占比及其 95% 置信区间、星级分布熵。

完整清洗说明见 [docs/CLEANING_PLAN.md](docs/CLEANING_PLAN.md)，全流程筛选决策见 [docs/PIPELINE_DECISIONS.md](docs/PIPELINE_DECISIONS.md)，统计设计见 [docs/ANALYSIS_PLAN.md](docs/ANALYSIS_PLAN.md)。

分析脚本会在 `data/analysis/` 生成描述统计、年度类型占比、产地比较、四象限分类等 CSV，以及对应 PNG 图。该目录可由原始数据重复生成，因此默认不提交。

## 7. 目录结构

```text
douban_crawler/
├── main.py
├── run_batch.py
├── run_stage2_continuous.py
├── run_stage3.py
├── run_cleaning.py
├── run_analysis.py
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
    ├── detail_failures.csv     # 阶段二失败状态与轮次
    ├── detail_failure_attempts.csv # 逐次失败原因与时间
    ├── unavailable_movies.csv  # 可从失败状态重建的不可用快照
    ├── reviews.csv             # 阶段三生成
    ├── review_progress.csv
    ├── processed/              # 可再生清洗产物，默认不入库
    ├── analysis/               # 可再生统计表和图，默认不入库
    └── archive/                # 旧版数据，不参与新流程
```

## 8. 合规与隐私

- 只采集研究所需的公开字段，控制请求频率。
- 新版短评表不保存用户名、用户 ID、头像地址或其摘要。
- 不提供验证码规避、账号凭证或代理 IP 自动轮换功能。
- 仓库不应包含 API Key、Cookie、Token、学号或其他个人资料。
