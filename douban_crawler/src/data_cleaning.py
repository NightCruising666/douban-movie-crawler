"""新版电影与短评数据清洗。

输出：
  data/processed/movies_cleaned.csv
  data/processed/movies_cleaning_report.csv
  data/processed/movies_cleaning_rules.csv
  data/processed/reviews_cleaned.csv
  data/processed/review_metrics.csv
"""

from __future__ import annotations

import math
import os
import re

import numpy as np
import pandas as pd


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
STUDY_YEAR_START = 2005
STUDY_YEAR_END = 2025

MOVIE_REQUIRED_FIELDS = [
    "豆瓣ID",
    "电影名称",
    "原始片名",
    "导演",
    "主演",
    "上映年份",
    "首映日期",
    "类型",
    "国家/地区",
    "片长",
    "豆瓣评分",
    "评价人数",
    "短评总数",
    "长评总数",
    "采集时间",
]
MOVIE_TEXT_FIELDS = [
    "豆瓣ID",
    "电影名称",
    "原始片名",
    "导演",
    "主演",
    "首映日期",
    "类型",
    "国家/地区",
    "片长",
    "采集时间",
]
PLACEHOLDERS = {"", "nan", "none", "null", "暂无", "<na>"}


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少数据文件: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"豆瓣ID": "string", "短评ID": "string"})


def classify_origin(countries: object) -> str:
    if pd.isna(countries):
        return "未知"
    parts = {
        part.strip()
        for part in str(countries).split("/")
        if part.strip() and part.strip().lower() not in PLACEHOLDERS
    }
    china_parts = {"中国大陆", "中国香港", "中国台湾", "中国澳门"}
    chinese = parts & china_parts
    foreign = parts - china_parts
    if chinese and foreign:
        return "合拍"
    if "中国大陆" in parts and len(parts) > 1:
        return "合拍"
    if parts == {"中国大陆"}:
        return "中国大陆"
    if chinese:
        return "港澳台"
    if foreign:
        return "进口"
    return "未知"


def _clean_text(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"\s+", " ", str(value)).strip()
    return pd.NA if text.lower() in PLACEHOLDERS else text


def _normalize_multivalue(value: object) -> object:
    value = _clean_text(value)
    if pd.isna(value):
        return pd.NA
    unique_parts = list(dict.fromkeys(part.strip() for part in str(value).split("/") if part.strip()))
    return " / ".join(unique_parts) if unique_parts else pd.NA


def _nonnegative_integers(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.notna() & numeric.ge(0) & np.isclose(numeric % 1, 0)
    return numeric.where(valid).astype("Int64"), ~valid


def _release_date_fields(
    series: pd.Series, maximum_year: pd.Series
) -> pd.DataFrame:
    rows = []
    for index, value in series.astype("string").items():
        if pd.isna(value):
            rows.append((pd.NA, pd.NA, pd.NA, pd.NA, "缺失"))
            continue
        text = str(value).strip()
        match = re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", text)
        if not match:
            rows.append((pd.NA, pd.NA, pd.NA, pd.NA, "异常"))
            continue
        year = int(match.group(1))
        max_allowed = int(maximum_year.loc[index])
        if year < 1888 or year > max_allowed:
            rows.append((year, pd.NA, pd.NA, pd.NA, "异常"))
            continue
        month = int(match.group(2)) if match.group(2) else None
        day = int(match.group(3)) if match.group(3) else None
        if day is not None:
            parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
            if pd.isna(parsed):
                rows.append((year, month, day, pd.NA, "异常"))
            else:
                rows.append((year, month, day, parsed.strftime("%Y-%m-%d"), "日"))
        elif month is not None:
            precision = "月" if 1 <= month <= 12 else "异常"
            rows.append((year, month, pd.NA, pd.NA, precision))
        else:
            rows.append((year, pd.NA, pd.NA, pd.NA, "年"))
    return pd.DataFrame(
        rows,
        columns=["首映年份_日期", "首映月份", "首映日", "首映日期标准化", "首映日期精度"],
        index=series.index,
    ).astype(
        {
            "首映年份_日期": "Int64",
            "首映月份": "Int64",
            "首映日": "Int64",
            "首映日期标准化": "string",
            "首映日期精度": "string",
        }
    )


def _add_flag(flag_lists: list[list[str]], mask: pd.Series, label: str) -> None:
    for position in np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool)):
        flag_lists[position].append(label)


def _metric(
    name: str,
    count: int,
    total: int,
    explanation: str,
    scope: str,
) -> dict:
    return {
        "指标": name,
        "统计口径": scope,
        "数量": int(count),
        "占统计口径比例": count / total if total else math.nan,
        "说明": explanation,
    }


def clean_movies_with_audit(
    df: pd.DataFrame,
    study_year_start: int = STUDY_YEAR_START,
    study_year_end: int = STUDY_YEAR_END,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """清洗电影表，同时返回汇总质量报告和可审计规则表。"""
    missing_columns = [column for column in MOVIE_REQUIRED_FIELDS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"电影表缺少必需字段: {', '.join(missing_columns)}")

    original_count = len(df)
    df = df.copy()
    df["_原始顺序"] = np.arange(len(df))

    normalized_record_mask = pd.Series(False, index=df.index)
    for column in MOVIE_TEXT_FIELDS:
        original = df[column].astype("string")
        normalized = original.map(_clean_text).astype("string")
        if column in {"类型", "国家/地区"}:
            normalized = normalized.map(_normalize_multivalue).astype("string")
        normalized_record_mask |= original.fillna("<NA>") != normalized.fillna("<NA>")
        df[column] = normalized

    input_missing_counts = {
        column: int(df[column].isna().sum())
        for column in ["原始片名", "导演", "主演", "类型", "国家/地区"]
    }
    missing_id_mask = df["豆瓣ID"].isna()
    missing_id_count = int(missing_id_mask.sum())
    df = df.loc[~missing_id_mask].copy()
    normalized_record_count = int(normalized_record_mask.loc[df.index].sum())

    duplicate_removed_count = int(df.duplicated(subset=["豆瓣ID"], keep="last").sum())
    capture_has_timezone = df["采集时间"].astype("string").str.contains(
        r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, regex=True, na=False
    )
    parsed_capture_time = pd.to_datetime(
        df["采集时间"], format="mixed", errors="coerce", utc=True
    )
    df["_采集时间解析"] = parsed_capture_time.where(capture_has_timezone)
    df = (
        df.sort_values(["豆瓣ID", "_采集时间解析", "_原始顺序"], na_position="first")
        .drop_duplicates(subset=["豆瓣ID"], keep="last")
        .sort_values("_原始顺序")
        .reset_index(drop=True)
    )
    capture_missing_mask = df["采集时间"].isna()
    capture_invalid_mask = df["采集时间"].notna() & df["_采集时间解析"].isna()

    count_invalid_masks: list[pd.Series] = []
    for column in ["评价人数", "短评总数", "长评总数"]:
        df[column], invalid = _nonnegative_integers(df[column])
        count_invalid_masks.append(invalid)
    count_invalid_mask = pd.concat(count_invalid_masks, axis=1).any(axis=1)

    raw_score = pd.to_numeric(df["豆瓣评分"], errors="coerce")
    valid_rating_mask = (
        raw_score.gt(0)
        & raw_score.le(10)
        & df["评价人数"].notna()
        & df["评价人数"].gt(0)
    )
    df["豆瓣评分"] = raw_score.where(valid_rating_mask).astype("Float64")

    raw_year = pd.to_numeric(df["上映年份"], errors="coerce")
    missing_year_mask = raw_year.isna()
    integer_year_mask = raw_year.notna() & np.isclose(raw_year % 1, 0)
    # 取原始带时区文本中的本地年份，避免UTC转换在跨年时改变年份。
    parsed_capture_year = pd.to_numeric(
        df["采集时间"].astype("string").str.extract(r"^(\d{4})", expand=False),
        errors="coerce",
    ).where(df["_采集时间解析"].notna())
    fallback_capture_year = (
        int(parsed_capture_year.max())
        if parsed_capture_year.notna().any()
        else study_year_end + 1
    )
    capture_year = parsed_capture_year.fillna(fallback_capture_year)
    valid_year_mask = (
        integer_year_mask
        & raw_year.ge(1888)
        & raw_year.le(capture_year + 1)
    )
    invalid_year_mask = raw_year.notna() & ~valid_year_mask
    df["上映年份"] = raw_year.where(valid_year_mask).astype("Int64")

    release_fields = _release_date_fields(df["首映日期"], capture_year + 1)
    for column in release_fields:
        df[column] = release_fields[column]

    runtime = pd.to_numeric(
        df["片长"].astype("string").str.extract(r"(\d+)", expand=False),
        errors="coerce",
    )
    valid_runtime_mask = runtime.between(1, 1440).fillna(False)
    df["片长分钟"] = runtime.where(valid_runtime_mask).astype("Int64")

    missing_type_mask = df["类型"].isna()
    missing_country_mask = df["国家/地区"].isna()
    df["类型"] = df["类型"].fillna("未知")
    df["国家/地区"] = df["国家/地区"].fillna("未知")
    df["主类型"] = df["类型"].str.split("/").str[0].str.strip()
    df["类型数"] = df["类型"].str.split("/").map(
        lambda parts: len([part for part in parts if part.strip()])
    ).astype("Int64")
    df["产地分类"] = df["国家/地区"].map(classify_origin)

    votes = df["评价人数"].astype("Float64")
    short_counts = df["短评总数"].astype("Float64")
    long_counts = df["长评总数"].astype("Float64")
    valid_denominator = votes.where(votes.gt(0))
    df["短评参与率"] = short_counts / valid_denominator
    df["长评参与率"] = long_counts / valid_denominator

    df["纳入评分分析"] = valid_rating_mask.astype(bool)
    df["纳入类型趋势分析"] = df["上映年份"].between(
        study_year_start, study_year_end
    ).fillna(False).astype(bool)

    df["贝叶斯加权评分"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    valid = df.loc[df["纳入评分分析"], ["豆瓣评分", "评价人数"]].copy()
    if not valid.empty:
        overall_mean = float(valid["豆瓣评分"].mean())
        minimum_votes = float(valid["评价人数"].median())
        denominator = votes + minimum_votes
        df.loc[df["纳入评分分析"], "贝叶斯加权评分"] = (
            votes / denominator * df["豆瓣评分"]
            + minimum_votes / denominator * overall_mean
        )

    no_score_but_reviews_mask = (
        ~valid_rating_mask & df["短评总数"].fillna(0).gt(0)
    )
    flag_lists: list[list[str]] = [[] for _ in range(len(df))]
    _add_flag(flag_lists, ~valid_rating_mask, "无有效评分")
    _add_flag(flag_lists, no_score_but_reviews_mask, "无评分但有短评")
    _add_flag(flag_lists, count_invalid_mask, "计数字段异常")
    _add_flag(flag_lists, missing_year_mask, "上映年份缺失")
    _add_flag(flag_lists, invalid_year_mask, "上映年份异常")
    _add_flag(flag_lists, capture_missing_mask, "采集时间缺失")
    _add_flag(flag_lists, capture_invalid_mask, "采集时间异常")
    _add_flag(flag_lists, df["首映日期精度"].eq("缺失"), "首映日期缺失")
    _add_flag(flag_lists, df["首映日期精度"].eq("异常"), "首映日期异常")
    _add_flag(flag_lists, ~valid_runtime_mask, "片长缺失或异常")
    _add_flag(flag_lists, missing_type_mask, "类型缺失")
    _add_flag(flag_lists, missing_country_mask, "国家地区缺失")
    _add_flag(flag_lists, df["短评参与率"].gt(1), "短评数大于评价人数")
    _add_flag(flag_lists, df["长评参与率"].gt(1), "长评数大于评价人数")
    df["数据质量标记"] = [";".join(flags) if flags else "正常" for flags in flag_lists]

    df["采集时间"] = df["_采集时间解析"]
    before_period = int(df["上映年份"].lt(study_year_start).fillna(False).sum())
    after_period = int(df["上映年份"].gt(study_year_end).fillna(False).sum())
    invalid_rating_count = int((~valid_rating_mask).sum())
    missing_year_count = int(missing_year_mask.sum())
    invalid_year_count = int(invalid_year_mask.sum())
    capture_missing_count = int(capture_missing_mask.sum())
    capture_invalid_count = int(capture_invalid_mask.sum())
    capture_time_issue_count = capture_missing_count + capture_invalid_count
    non_day_date_count = int(df["首映日期精度"].ne("日").sum())
    missing_runtime_count = int((~valid_runtime_mask).sum())
    analysis_a_count = int(df["纳入评分分析"].sum())
    analysis_b_count = int(df["纳入类型趋势分析"].sum())

    clean_count = len(df)
    report = pd.DataFrame(
        [
            _metric("原始记录数", original_count, original_count, "阶段二 movies.csv 输入行数", "原始输入"),
            _metric("缺失豆瓣ID记录数", missing_id_count, original_count, "无稳定主键，无法关联，清洗表删除", "原始输入"),
            _metric("重复豆瓣ID记录数", duplicate_removed_count, original_count, "按采集时间保留最新快照", "原始输入"),
            _metric("清洗后记录数", clean_count, original_count, "保留全部有主键的唯一记录", "原始输入"),
            _metric("无有效评分记录数", invalid_rating_count, clean_count, "评分置为空，不做均值填补", "清洗后唯一记录"),
            _metric("评分分析样本数", analysis_a_count, clean_count, "评分>0且评价人数>0", "清洗后唯一记录"),
            _metric(
                f"{study_year_start}-{study_year_end}类型趋势样本数",
                analysis_b_count,
                clean_count,
                "只在课题B分析时筛选，不从清洗表删除",
                "清洗后唯一记录",
            ),
            _metric("研究期前年份记录数", before_period, clean_count, "保留，用于课题A和样本说明", "清洗后唯一记录"),
            _metric("研究期后年份记录数", after_period, clean_count, "保留，不进入课题B", "清洗后唯一记录"),
            _metric("上映年份缺失记录数", missing_year_count, clean_count, "置为空并标记为缺失", "清洗后唯一记录"),
            _metric("上映年份异常记录数", invalid_year_count, clean_count, "置为空并标记", "清洗后唯一记录"),
            _metric(
                "采集时间缺失记录数",
                capture_missing_count,
                clean_count,
                "置为空并标记",
                "清洗后唯一记录",
            ),
            _metric(
                "采集时间异常记录数",
                capture_invalid_count,
                clean_count,
                "无法解析或缺少时区，置为空并标记；去重时有效时间优先",
                "清洗后唯一记录",
            ),
            _metric("首映日期非日精度记录数", non_day_date_count, clean_count, "不虚构月份或日期", "清洗后唯一记录"),
            _metric("片长缺失或异常记录数", missing_runtime_count, clean_count, "片长分钟置为空", "清洗后唯一记录"),
            _metric("类型缺失记录数", int(missing_type_mask.sum()), clean_count, "类型填为未知并标记", "清洗后唯一记录"),
            _metric("国家地区缺失记录数", int(missing_country_mask.sum()), clean_count, "国家地区填为未知并标记", "清洗后唯一记录"),
            _metric(
                "原始片名缺失记录数",
                input_missing_counts["原始片名"],
                original_count,
                "保留；可能表示没有单独的外文或原始片名",
                "原始输入",
            ),
            _metric("导演缺失记录数", input_missing_counts["导演"], original_count, "保留并披露", "原始输入"),
            _metric("主演缺失记录数", input_missing_counts["主演"], original_count, "保留并披露", "原始输入"),
            _metric("计数字段异常记录数", int(count_invalid_mask.sum()), clean_count, "置为空，不四舍五入或裁剪", "清洗后唯一记录"),
            _metric("无评分但有短评记录数", int(no_score_but_reviews_mask.sum()), clean_count, "保留短评总数，评分分析排除", "清洗后唯一记录"),
        ]
    )

    rules = pd.DataFrame(
        [
            {
                "规则ID": "R01",
                "字段": "文本字段",
                "判定标准": "首尾/重复空白、占位符、多值分隔不一致",
                "处理方式": "去空白、占位符转缺失、类型和国家地区统一为“ / ”分隔",
                "选择原因": "统一格式但不改变实体含义",
                "未采用方法": "不对片名和人名做模糊合并",
                "命中记录数": normalized_record_count,
            },
            {
                "规则ID": "R02",
                "字段": "豆瓣ID",
                "判定标准": "豆瓣ID重复",
                "处理方式": "按采集时间保留最新快照",
                "选择原因": "同一实体只保留一个分析时点",
                "未采用方法": "不按电影名称去重，同名电影可能是不同作品",
                "命中记录数": duplicate_removed_count,
            },
            {
                "规则ID": "R03",
                "字段": "豆瓣ID",
                "判定标准": "主键缺失",
                "处理方式": "从清洗表删除，原始表保留",
                "选择原因": "无法与标签、评论表可靠关联",
                "未采用方法": "不人工生成替代ID",
                "命中记录数": missing_id_count,
            },
            {
                "规则ID": "R04",
                "字段": "豆瓣评分/评价人数",
                "判定标准": "评分不在(0,10]或评价人数<=0",
                "处理方式": "评分置为空，记录保留，排除课题A",
                "选择原因": "0代表未形成有效评分，不代表作品得0分",
                "未采用方法": "不以0分或总体均值填补",
                "命中记录数": invalid_rating_count,
            },
            {
                "规则ID": "R05",
                "字段": "评价人数/短评总数/长评总数",
                "判定标准": "非数字、负数或非整数",
                "处理方式": "置为空并标记",
                "选择原因": "计数必须为非负整数",
                "未采用方法": "不四舍五入、不裁剪为0",
                "命中记录数": int(count_invalid_mask.sum()),
            },
            {
                "规则ID": "R06",
                "字段": "上映年份",
                "判定标准": "缺失、非整数、早于1888或晚于采集年份+1",
                "处理方式": "置为空并标记",
                "选择原因": "采用电影史和原始时区年份；单条时间无效时回退到数据集最大有效采集年，整列无效时回退到研究结束年+1",
                "未采用方法": "不直接删除整行",
                "命中记录数": missing_year_count + invalid_year_count,
            },
            {
                "规则ID": "R07",
                "字段": "首映日期",
                "判定标准": "识别年、年月、完整日期和异常四种精度",
                "处理方式": "保留原文，另建标准日期和精度字段",
                "选择原因": "避免把只有年份的数据虚构为1月1日",
                "未采用方法": "不强制填充缺失的月和日",
                "命中记录数": non_day_date_count,
            },
            {
                "规则ID": "R08",
                "字段": "片长",
                "判定标准": "提取首个1—1440分钟整数",
                "处理方式": "生成片长分钟，无法提取则置空",
                "选择原因": "原始片长文本可能包含版本说明",
                "未采用方法": "不丢弃原始片长文本",
                "命中记录数": missing_runtime_count,
            },
            {
                "规则ID": "R09",
                "字段": "国家/地区",
                "判定标准": "中国大陆、港澳台与海外组合",
                "处理方式": "分为中国大陆、合拍、港澳台、进口、未知",
                "选择原因": "避免把合拍片强行二分",
                "未采用方法": "不简单按国产/进口二分类",
                "命中记录数": len(df),
            },
            {
                "规则ID": "R10",
                "字段": "课题A样本",
                "判定标准": "评分>0且评价人数>0",
                "处理方式": "生成纳入评分分析标志",
                "选择原因": "评分可信度分析需要有效评分和分母",
                "未采用方法": "不按评价人数主观删掉小众作品",
                "命中记录数": analysis_a_count,
            },
            {
                "规则ID": "R11",
                "字段": "课题B样本",
                "判定标准": f"上映年份在{study_year_start}—{study_year_end}",
                "处理方式": "生成纳入类型趋势分析标志",
                "选择原因": "与研究时间边界一致，清洗主表仍保留其他年份",
                "未采用方法": "不提前删除研究期外数据",
                "命中记录数": analysis_b_count,
            },
            {
                "规则ID": "R12",
                "字段": "贝叶斯加权评分",
                "判定标准": "C为有效样本均值，m为评价人数中位数",
                "处理方式": "对小样本极端评分向总体均值收缩",
                "选择原因": "保留小众作品，同时降低小样本波动影响",
                "未采用方法": "不设置单一评价人数硬门槛",
                "命中记录数": analysis_a_count,
            },
            {
                "规则ID": "R13",
                "字段": "采集时间",
                "判定标准": "时间缺失、不能解析或原文不含时区",
                "处理方式": "置为空并标记；去重时有效时间优先",
                "选择原因": "防止把无效时间误认为最新快照",
                "未采用方法": "不根据文件顺序伪造采集时间",
                "命中记录数": capture_time_issue_count,
            },
        ]
    )
    hit_types = {
        "R01": "格式标准化",
        "R02": "删除记录",
        "R03": "删除记录",
        "R04": "置空并排除",
        "R05": "置空",
        "R06": "置空",
        "R07": "精度分类",
        "R08": "置空",
        "R09": "派生字段",
        "R10": "纳入样本",
        "R11": "纳入样本",
        "R12": "派生指标",
        "R13": "质量异常",
    }
    rules.insert(4, "命中类型", rules["规则ID"].map(hit_types))

    df = df.drop(columns=["_原始顺序", "_采集时间解析"])
    return df, report, rules


def clean_movies(df: pd.DataFrame) -> pd.DataFrame:
    cleaned, _, _ = clean_movies_with_audit(df)
    return cleaned


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates(subset=["短评ID", "采样方式"], keep="last")
    df["评分值"] = pd.to_numeric(df["评分"].astype("string").str.extract(r"(\d+)", expand=False), errors="coerce")
    df.loc[~df["评分值"].between(1, 5), "评分值"] = np.nan
    df["有用数"] = pd.to_numeric(df["有用数"], errors="coerce").fillna(0).clip(lower=0).astype("Int64")
    df["排序位置"] = pd.to_numeric(df["排序位置"], errors="coerce").astype("Int64")
    df["评论时间"] = pd.to_datetime(df["评论时间"], errors="coerce")
    df["采集时间"] = pd.to_datetime(df["采集时间"], errors="coerce", utc=True)
    return df


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (math.nan, math.nan)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (center - margin, center + margin)


def review_metrics(reviews: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = reviews.dropna(subset=["评分值"]).groupby(["豆瓣ID", "电影名称", "采样方式"], dropna=False)
    for (movie_id, title, sample_type), group in grouped:
        ratings = group["评分值"].astype(float)
        useful = group["有用数"].astype(float)
        raw_weights = useful
        log_weights = np.log1p(useful) + 1
        five_stars = int((ratings == 5).sum())
        low, high = wilson_interval(five_stars, len(ratings))
        probabilities = ratings.value_counts(normalize=True)
        entropy = float(-(probabilities * np.log2(probabilities)).sum())
        rows.append(
            {
                "豆瓣ID": movie_id,
                "电影名称": title,
                "采样方式": sample_type,
                "有效评分样本数": len(ratings),
                "平均星级": ratings.mean(),
                "原始有用数加权星级": (
                    np.average(ratings, weights=raw_weights) if raw_weights.sum() > 0 else ratings.mean()
                ),
                "对数有用数加权星级": np.average(ratings, weights=log_weights),
                "五星样本占比": five_stars / len(ratings),
                "五星占比95%CI下限": low,
                "五星占比95%CI上限": high,
                "星级分布熵": entropy,
            }
        )
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, filename: str) -> str:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已保存: {path} ({len(df)} 条)")
    return path


def run_full_cleaning() -> None:
    movies, report, rules = clean_movies_with_audit(load_csv("movies.csv"))
    save(movies, "movies_cleaned.csv")
    save(report, "movies_cleaning_report.csv")
    save(rules, "movies_cleaning_rules.csv")

    reviews_path = os.path.join(DATA_DIR, "reviews.csv")
    if os.path.exists(reviews_path):
        reviews = clean_reviews(load_csv("reviews.csv"))
        save(reviews, "reviews_cleaned.csv")
        save(review_metrics(reviews), "review_metrics.csv")
    else:
        print("尚未找到 reviews.csv，本次只清洗电影表。")


if __name__ == "__main__":
    run_full_cleaning()
