#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
认知实习 — 销售数据清洗与可视化分析
专业：待填  班级：待填  学号：待填  姓名：待填
============================================================

本脚本完成以下任务：
  (1) 读取 sales.csv 原始数据
  (2) 探索性数据分析（EDA）—— 查看缺失值、异常值
  (3) 处理缺失数据（NaN / 空字符串）
  (4) 剔除重复数据
  (5) 处理 "ERROR" / "UNKNOWN" 等无效数据
  (6) 保存清洗后数据 → cleaned_sales.csv
  (7) 可视化：不同类别产品价格、购买数量等统计特征
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')                         # 非交互式后端，方便无 GUI 环境下运行
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# ---------- 字体设置（macOS / Windows 通用）----------
import platform
if platform.system() == 'Darwin':
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti SC', 'PingFang SC']
elif platform.system() == 'Windows':
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
else:
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150

# ============================================================
# 0. 全局变量：记录每一步的数据行数变化
# ============================================================
log_lines = []   # 用于最终输出日志摘要


def log(msg: str):
    """同时打印到终端并记录在 log_lines 中。"""
    print(msg)
    log_lines.append(msg)


# ============================================================
# 1. 读取 CSV 文件
# ============================================================
log("=" * 60)
log("步骤1：读取原始数据")
log("=" * 60)

FILE_PATH = "sales.csv"
df_raw = pd.read_csv(FILE_PATH, dtype=str)   # 全部以字符串读入，避免自动转换带来的丢失
log(f"原始数据维度: {df_raw.shape[0]} 行 × {df_raw.shape[1]} 列")
log(f"列名: {df_raw.columns.tolist()}")

# ============================================================
# 2. 探索性数据分析（EDA）
# ============================================================
log("\n" + "=" * 60)
log("步骤2：探索性数据分析（EDA）")
log("=" * 60)

# 2.1 基本信息
log("\n--- 2.1 各列缺失值统计（NaN） ---")
null_counts = df_raw.isnull().sum()
log(null_counts.to_string())

# 2.2 空字符串统计
log("\n--- 2.2 各列空字符串统计 ---")
for col in df_raw.columns:
    empty_count = (df_raw[col] == '').sum()
    if empty_count > 0:
        log(f"  {col}: {empty_count} 个空字符串")

# 2.3 "ERROR" 统计
log("\n--- 2.3 各列 'ERROR' 值统计 ---")
error_stats = {}
for col in df_raw.columns:
    cnt = (df_raw[col].str.upper() == 'ERROR').sum()
    if cnt > 0:
        error_stats[col] = cnt
        log(f"  {col}: {cnt} 个 ERROR")

# 2.4 "UNKNOWN" 统计
log("\n--- 2.4 各列 'UNKNOWN' 值统计 ---")
unknown_stats = {}
for col in df_raw.columns:
    cnt = (df_raw[col].str.upper() == 'UNKNOWN').sum()
    if cnt > 0:
        unknown_stats[col] = cnt
        log(f"  {col}: {cnt} 个 UNKNOWN")

# 2.5 重复行统计
log("\n--- 2.5 重复行统计 ---")
dup_rows = df_raw.duplicated().sum()
log(f"完全重复的行数: {dup_rows}")
dup_txn = df_raw.duplicated(subset=['Transaction ID']).sum()
log(f"Transaction ID 重复数: {dup_txn}")

# 2.6 正常类别一览
log("\n--- 2.6 正常类别分布 ---")
for col in ['Item', 'Payment Method', 'Location']:
    # 过滤掉 ERROR / UNKNOWN / NaN / 空
    valid = df_raw[col].dropna()
    valid = valid[~valid.str.upper().isin(['ERROR', 'UNKNOWN'])]
    valid = valid[valid != '']
    log(f"\n[{col}] 有效值分布 (共 {len(valid)} 条):")
    log(valid.value_counts().to_string())

# ============================================================
# 3. 数据清洗
# ============================================================
log("\n" + "=" * 60)
log("步骤3：数据清洗")
log("=" * 60)

df = df_raw.copy()
initial_rows = len(df)

# --- 3.1 将 "ERROR" / "UNKNOWN" 替换为 NaN ---
log("\n--- 3.1 将 'ERROR' / 'UNKNOWN' 替换为 NaN ---")
for col in df.columns:
    mask_err = df[col].str.upper().isin(['ERROR', 'UNKNOWN'])
    cnt = mask_err.sum()
    if cnt > 0:
        df.loc[mask_err, col] = np.nan
        log(f"  {col}: 替换 {cnt} 个 ERROR/UNKNOWN → NaN")

# --- 3.2 将空字符串替换为 NaN ---
log("\n--- 3.2 将空字符串替换为 NaN ---")
for col in df.columns:
    mask_empty = (df[col] == '')
    cnt = mask_empty.sum()
    if cnt > 0:
        df.loc[mask_empty, col] = np.nan
        log(f"  {col}: 替换 {cnt} 个空字符串 → NaN")

# --- 3.3 删除完全重复的行 ---
log("\n--- 3.3 删除重复行 ---")
before_dedup = len(df)
df = df.drop_duplicates()
log(f"  移除重复行: {before_dedup - len(df)} 行")

# --- 3.4 处理 Transaction ID 重复 ---
log("\n--- 3.4 处理 Transaction ID 重复 ---")
df = df.drop_duplicates(subset=['Transaction ID'], keep='first')
log(f"  移除重复 Transaction ID: {before_dedup - len(df)} → 当前 {len(df)} 行（含此步累计）")

# --- 3.5 转换数值列 ---
log("\n--- 3.5 转换数值列 ---")
for col in ['Quantity', 'Price Per Unit', 'Total Spent']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
    nan_cnt = df[col].isnull().sum()
    log(f"  {col}: 转换后 NaN 数量 = {nan_cnt}")

# --- 3.6 转换日期列 ---
log("\n--- 3.6 转换日期列 ---")
df['Transaction Date'] = pd.to_datetime(df['Transaction Date'], errors='coerce')
date_nan = df['Transaction Date'].isnull().sum()
log(f"  Transaction Date: 转换后 NaT 数量 = {date_nan}")

# --- 3.7 数值列的逻辑修复 ---
# 如果 Quantity 和 Price Per Unit 已知但 Total Spent 缺失 → 计算
# 如果 Total Spent 和 Price Per Unit 已知但 Quantity 缺失 → 计算
# 如果 Total Spent 和 Quantity 已知但 Price Per Unit 缺失 → 计算
log("\n--- 3.7 数值列逻辑修复 ---")

# 补全 Total Spent
mask_fix_ts = (
    df['Total Spent'].isnull() &
    df['Quantity'].notnull() &
    df['Price Per Unit'].notnull()
)
n_fix_ts = mask_fix_ts.sum()
df.loc[mask_fix_ts, 'Total Spent'] = (
    df.loc[mask_fix_ts, 'Quantity'] * df.loc[mask_fix_ts, 'Price Per Unit']
)
log(f"  依据 Quantity × Price Per Unit 补全 Total Spent: {n_fix_ts} 行")

# 补全 Quantity
mask_fix_qty = (
    df['Quantity'].isnull() &
    df['Total Spent'].notnull() &
    df['Price Per Unit'].notnull() &
    (df['Price Per Unit'] != 0)
)
n_fix_qty = mask_fix_qty.sum()
df.loc[mask_fix_qty, 'Quantity'] = (
    df.loc[mask_fix_qty, 'Total Spent'] / df.loc[mask_fix_qty, 'Price Per Unit']
)
log(f"  依据 Total Spent ÷ Price Per Unit 补全 Quantity: {n_fix_qty} 行")

# 补全 Price Per Unit
mask_fix_price = (
    df['Price Per Unit'].isnull() &
    df['Total Spent'].notnull() &
    df['Quantity'].notnull() &
    (df['Quantity'] != 0)
)
n_fix_price = mask_fix_price.sum()
df.loc[mask_fix_price, 'Price Per Unit'] = (
    df.loc[mask_fix_price, 'Total Spent'] / df.loc[mask_fix_price, 'Quantity']
)
log(f"  依据 Total Spent ÷ Quantity 补全 Price Per Unit: {n_fix_price} 行")

# --- 3.8 剔除存在任何缺失值的行 ---
log("\n--- 3.8 剔除仍存在缺失值的行 ---")
before_dropna = len(df)
df = df.dropna()
log(f"  移除含 NaN 的行: {before_dropna - len(df)} 行")
log(f"  当前数据维度: {df.shape[0]} 行 × {df.shape[1]} 列")

# --- 3.9 数据类型定型 ---
df['Quantity'] = df['Quantity'].astype(int)
df['Total Spent'] = df['Total Spent'].round(2)
df['Price Per Unit'] = df['Price Per Unit'].round(2)
# 保持 Total Spent = round(Quantity * Price Per Unit, 2) 的一致性
df['Total Spent'] = (df['Quantity'] * df['Price Per Unit']).round(2)

# 重置索引
df = df.reset_index(drop=True)

final_rows = len(df)
log(f"\n清洗完成！原始行数: {initial_rows} → 清洗后行数: {final_rows}")
log(f"共移除 {initial_rows - final_rows} 行无效数据 ({(initial_rows - final_rows) / initial_rows * 100:.2f}%)")

# ============================================================
# 4. 保存清洗后的数据
# ============================================================
log("\n" + "=" * 60)
log("步骤4：保存清洗后数据")
log("=" * 60)

OUTPUT_CSV = "cleaned_sales.csv"
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
log(f"已保存至: {OUTPUT_CSV}")

# 验证保存的文件
df_check = pd.read_csv(OUTPUT_CSV)
log(f"验证读取: {df_check.shape[0]} 行 × {df_check.shape[1]} 列")
log(f"各列数据类型:\n{df_check.dtypes.to_string()}")

# ============================================================
# 5. 数据可视化
# ============================================================
log("\n" + "=" * 60)
log("步骤5：数据可视化")
log("=" * 60)

# 为方便绘图读取回清洗好的数据
plot_df = df.copy()
plot_df['Item'] = plot_df['Item'].astype(str)
plot_df['Payment Method'] = plot_df['Payment Method'].astype(str)
plot_df['Location'] = plot_df['Location'].astype(str)
plot_df['Transaction Date'] = pd.to_datetime(plot_df['Transaction Date'])

# ----- 产品统计 -----
items = plot_df['Item'].unique()
log(f"产品类别({len(items)}): {sorted(items)}")

# =============================================================
# 图1：各类产品销量分布（柱状图）
# =============================================================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 1a. 各类产品销售数量总和
item_qty = plot_df.groupby('Item')['Quantity'].sum().sort_values(ascending=False)
colors1 = sns.color_palette('Set2', n_colors=len(item_qty))
axes[0].bar(item_qty.index, item_qty.values, color=colors1, edgecolor='white', linewidth=0.5)
axes[0].set_title('各类产品销售总量', fontsize=14, fontweight='bold')
axes[0].set_xlabel('产品类别')
axes[0].set_ylabel('销售总量（件）')
axes[0].tick_params(axis='x', rotation=30)
for i, v in enumerate(item_qty.values):
    axes[0].text(i, v + max(item_qty.values) * 0.01, str(v),
                 ha='center', va='bottom', fontsize=8)

# 1b. 各类产品交易笔数
item_count = plot_df.groupby('Item').size().sort_values(ascending=False)
colors2 = sns.color_palette('Set2', n_colors=len(item_count))
axes[1].bar(item_count.index, item_count.values, color=colors2, edgecolor='white', linewidth=0.5)
axes[1].set_title('各类产品交易笔数', fontsize=14, fontweight='bold')
axes[1].set_xlabel('产品类别')
axes[1].set_ylabel('交易笔数')
axes[1].tick_params(axis='x', rotation=30)
for i, v in enumerate(item_count.values):
    axes[1].text(i, v + max(item_count.values) * 0.01, str(v),
                 ha='center', va='bottom', fontsize=8)

# 1c. 各类产品平均单价
item_avg_price = plot_df.groupby('Item')['Price Per Unit'].mean().sort_values(ascending=False)
colors3 = sns.color_palette('Set2', n_colors=len(item_avg_price))
axes[2].bar(item_avg_price.index, item_avg_price.values, color=colors3, edgecolor='white', linewidth=0.5)
axes[2].set_title('各类产品平均单价', fontsize=14, fontweight='bold')
axes[2].set_xlabel('产品类别')
axes[2].set_ylabel('平均单价（元）')
axes[2].tick_params(axis='x', rotation=30)
for i, v in enumerate(item_avg_price.values):
    axes[2].text(i, v + max(item_avg_price.values) * 0.01, f'{v:.2f}',
                 ha='center', va='bottom', fontsize=8)

plt.tight_layout()
fig.savefig('fig1_product_sales.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图1 已保存: fig1_product_sales.png")

# =============================================================
# 图2：各类产品价格箱线图 + 购买数量箱线图
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 2a. 价格箱线图
order_by_price = plot_df.groupby('Item')['Price Per Unit'].median().sort_values().index.tolist()
sns.boxplot(data=plot_df, x='Item', y='Price Per Unit', order=order_by_price,
            palette='Set2', ax=axes[0], linewidth=0.8)
axes[0].set_title('各类产品单价分布（箱线图）', fontsize=14, fontweight='bold')
axes[0].set_xlabel('产品类别')
axes[0].set_ylabel('单价（元）')
axes[0].tick_params(axis='x', rotation=30)

# 2b. 购买数量箱线图
order_by_qty = plot_df.groupby('Item')['Quantity'].median().sort_values().index.tolist()
sns.boxplot(data=plot_df, x='Item', y='Quantity', order=order_by_qty,
            palette='Set2', ax=axes[1], linewidth=0.8)
axes[1].set_title('各类产品购买数量分布（箱线图）', fontsize=14, fontweight='bold')
axes[1].set_xlabel('产品类别')
axes[1].set_ylabel('购买数量（件）')
axes[1].tick_params(axis='x', rotation=30)

plt.tight_layout()
fig.savefig('fig2_boxplot_price_qty.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图2 已保存: fig2_boxplot_price_qty.png")

# =============================================================
# 图3：各产品销售额占比 & 支付方式分布
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 3a. 各产品销售额占比（饼图）
item_revenue = plot_df.groupby('Item')['Total Spent'].sum().sort_values(ascending=False)
colors_pie = sns.color_palette('Set2', n_colors=len(item_revenue))
wedges, texts, autotexts = axes[0].pie(
    item_revenue.values, labels=item_revenue.index,
    autopct='%1.1f%%', colors=colors_pie,
    explode=[0.03] * len(item_revenue),
    textprops={'fontsize': 9}
)
for at in autotexts:
    at.set_fontweight('bold')
axes[0].set_title('各类产品销售额占比', fontsize=14, fontweight='bold')

# 3b. 支付方式分布（柱状图）
pay_counts = plot_df['Payment Method'].value_counts()
colors_pay = sns.color_palette('Set3', n_colors=len(pay_counts))
bars = axes[1].bar(pay_counts.index, pay_counts.values, color=colors_pay, edgecolor='white')
axes[1].set_title('支付方式分布', fontsize=14, fontweight='bold')
axes[1].set_xlabel('支付方式')
axes[1].set_ylabel('交易笔数')
for bar, v in zip(bars, pay_counts.values):
    axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(pay_counts.values) * 0.01,
                 str(v), ha='center', fontsize=10, fontweight='bold')

plt.tight_layout()
fig.savefig('fig3_revenue_payment.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图3 已保存: fig3_revenue_payment.png")

# =============================================================
# 图4：月度销售趋势 & 位置分布
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 4a. 月度销售额趋势
plot_df['YearMonth'] = plot_df['Transaction Date'].dt.to_period('M').astype(str)
monthly_revenue = plot_df.groupby('YearMonth')['Total Spent'].sum()
axes[0].plot(monthly_revenue.index, monthly_revenue.values, marker='o',
             color='#2E86AB', linewidth=2, markersize=6)
axes[0].fill_between(range(len(monthly_revenue)), monthly_revenue.values,
                     alpha=0.15, color='#2E86AB')
axes[0].set_title('月度销售额趋势', fontsize=14, fontweight='bold')
axes[0].set_xlabel('月份')
axes[0].set_ylabel('销售额（元）')
axes[0].tick_params(axis='x', rotation=45)
axes[0].yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f'))
# 在数据点上标注数值
for i, (x, y) in enumerate(zip(monthly_revenue.index, monthly_revenue.values)):
    axes[0].annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                     xytext=(0, 10), ha='center', fontsize=7)

# 4b. 位置分布
loc_counts = plot_df['Location'].value_counts()
colors_loc = sns.color_palette('Set2', n_colors=len(loc_counts))
bars = axes[1].bar(loc_counts.index, loc_counts.values, color=colors_loc, edgecolor='white')
axes[1].set_title('交易位置分布', fontsize=14, fontweight='bold')
axes[1].set_xlabel('位置')
axes[1].set_ylabel('交易笔数')
for bar, v in zip(bars, loc_counts.values):
    axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(loc_counts.values) * 0.01,
                 str(v), ha='center', fontsize=11, fontweight='bold')

plt.tight_layout()
fig.savefig('fig4_trend_location.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图4 已保存: fig4_trend_location.png")

# =============================================================
# 图5：多维度综合热力图（产品 × 支付方式 交叉统计）
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# 5a. 产品 × 支付方式 —— 交易笔数
ct1 = pd.crosstab(plot_df['Item'], plot_df['Payment Method'])
sns.heatmap(ct1, annot=True, fmt='d', cmap='YlGnBu', ax=axes[0],
            linewidths=0.5, cbar_kws={'label': '交易笔数'})
axes[0].set_title('产品类别 × 支付方式（交易笔数）', fontsize=13, fontweight='bold')
axes[0].set_xlabel('支付方式')
axes[0].set_ylabel('产品类别')

# 5b. 产品 × 位置 —— 交易笔数
ct2 = pd.crosstab(plot_df['Item'], plot_df['Location'])
sns.heatmap(ct2, annot=True, fmt='d', cmap='YlOrRd', ax=axes[1],
            linewidths=0.5, cbar_kws={'label': '交易笔数'})
axes[1].set_title('产品类别 × 位置（交易笔数）', fontsize=13, fontweight='bold')
axes[1].set_xlabel('位置')
axes[1].set_ylabel('产品类别')

plt.tight_layout()
fig.savefig('fig5_heatmap_cross.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图5 已保存: fig5_heatmap_cross.png")

# =============================================================
# 图6：描述性统计表格可视化
# =============================================================
fig, ax = plt.subplots(figsize=(12, 5))
ax.axis('off')

desc = plot_df.groupby('Item').agg(
    交易笔数=('Transaction ID', 'count'),
    销售总量=('Quantity', 'sum'),
    平均单价=('Price Per Unit', 'mean'),
    销售额总和=('Total Spent', 'sum'),
    平均每笔消费=('Total Spent', 'mean'),
    平均每次购买量=('Quantity', 'mean'),
).round(2)

# 用 matplotlib 绘制统计表格
table = ax.table(
    cellText=desc.values,
    colLabels=desc.columns,
    rowLabels=desc.index,
    cellLoc='center',
    rowLoc='center',
    loc='center',
)
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.2, 1.6)
# 表头样式
for j in range(len(desc.columns)):
    cell = table[0, j]
    cell.set_facecolor('#2E86AB')
    cell.set_text_props(color='white', fontweight='bold')
# 行标签样式
for i in range(len(desc.index)):
    cell = table[i + 1, -1]
    # 行 label 在最左列
for i in range(len(desc.index)):
    table[i + 1, 0].set_facecolor('#E8F4F8')

ax.set_title('各类产品描述性统计汇总', fontsize=16, fontweight='bold', pad=20)

plt.tight_layout()
fig.savefig('fig6_summary_table.png', dpi=200, bbox_inches='tight')
plt.close(fig)
log("  图6 已保存: fig6_summary_table.png")

# =============================================================
# 步骤6：输出汇总日志
# =============================================================
log("\n" + "=" * 60)
log("步骤6：清洗与可视化完成，输出日志")
log("=" * 60)

log("\n--- 清洗前后数据对比 ---")
log(f"  原始数据行数: {initial_rows}")
log(f"  清洗后行数:   {final_rows}")
log(f"  移除行数:     {initial_rows - final_rows}")
log(f"  保留比例:     {final_rows / initial_rows * 100:.2f}%")

log("\n--- 生成的文件 ---")
log("  ✓ cleaned_sales.csv         — 清洗后数据")
log("  ✓ fig1_product_sales.png    — 产品销售统计柱状图")
log("  ✓ fig2_boxplot_price_qty.png— 价格与数量箱线图")
log("  ✓ fig3_revenue_payment.png  — 销售额占比 & 支付方式")
log("  ✓ fig4_trend_location.png   — 月度趋势 & 位置分布")
log("  ✓ fig5_heatmap_cross.png    — 交叉统计热力图")
log("  ✓ fig6_summary_table.png    — 描述性统计汇总表")

log("\n程序运行完毕。")

# =============================================================
# 将日志写入文件，供 Word 报告生成脚本读取
# =============================================================
with open("cleaning_log.txt", "w", encoding="utf-8") as f:
    for line in log_lines:
        f.write(line + "\n")
