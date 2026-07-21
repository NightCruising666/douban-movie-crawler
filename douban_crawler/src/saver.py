"""
CSV保存模块
==========
负责将爬取的数据写入CSV文件。

为什么用csv模块而不是直接写文件？
- 自动处理字段内的逗号、引号、换行符
- 支持中文编码（utf-8-sig）
- DictWriter让代码和字段名绑定，不易出错
"""

import csv
import os
from . import config


def ensure_data_dir():
    """确保 data/ 目录存在。"""
    # 项目根目录是 douban_crawler/
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data"
    )
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _resolve_path(filename):
    """解析 data/ 相对路径，并保留 archive/ 等子目录。"""
    data_dir = ensure_data_dir()
    normalized = filename.replace("\\", "/")
    if normalized.startswith("data/"):
        normalized = normalized[len("data/"):]
    filepath = os.path.join(data_dir, normalized)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    return filepath


def _validate_existing_header(filepath, fieldnames):
    """追加前检查现有表头，防止新旧 schema 混写造成 CSV 损坏。"""
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return
    with open(filepath, "r", newline="", encoding=config.CSV_ENCODING) as file:
        existing = next(csv.reader(file), [])
    if list(existing) != list(fieldnames):
        raise ValueError(
            f"CSV表头与当前数据契约不一致: {filepath}\n"
            f"现有: {existing}\n期望: {list(fieldnames)}\n"
            "请将旧文件移入 data/archive 后重试。"
        )


def save_to_csv(records, filename, fieldnames):
    """
    将字典列表保存为CSV文件。

    参数:
        records:    list[dict]，每条记录是一个字典
        filename:   保存的文件名（如 "movies.csv"）
        fieldnames: list[str]，CSV列名（决定列顺序）

    返回:
        保存的文件完整路径
    """
    filepath = _resolve_path(filename)

    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", newline="", encoding=config.CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()   # 写入表头
        writer.writerows(records)  # 批量写入数据
    os.replace(temp_path, filepath)

    print(f"已保存: {filepath}  ({len(records)} 条记录)")
    return filepath


def append_to_csv(records, filename, fieldnames):
    """
    追加写入CSV（首次写入时写入表头，后续追加数据）。

    用于分批采集时，边爬边存，防止中途崩溃丢失数据。
    """
    filepath = _resolve_path(filename)

    # 判断是否需要写表头
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    _validate_existing_header(filepath, fieldnames)

    with open(filepath, "a", newline="", encoding=config.CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        if not file_exists:
            writer.writeheader()
        writer.writerows(records)

    return filepath


def deduplicate_movies(input_csv, output_csv, key_field="电影名称"):
    """
    按指定字段去重，保留每组中的第一条。

    豆瓣多个标签会包含同一部电影（如《肖申克的救赎》
    同时出现在"经典"和"豆瓣高分"中），这个函数解决重复问题。
    """
    input_path = _resolve_path(input_csv)
    output_path = _resolve_path(output_csv)

    seen = set()
    unique = []

    with open(input_path, "r", encoding=config.CSV_ENCODING) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            key = row.get(key_field, "")
            if key and key not in seen:
                seen.add(key)
                unique.append(row)

    with open(output_path, "w", newline="", encoding=config.CSV_ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(unique)

    print(f"去重完成: {input_path} ({len(seen) + len(unique)}条→{len(unique)}条) → {output_path}")
    return output_path
