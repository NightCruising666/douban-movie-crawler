"""阶段二失败记录与永久不可用判定。"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from . import config


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PERMANENT_HTTP_REASONS = {"HTTP 400", "HTTP 404", "HTTP 410"}


def _path(relative_path: str) -> Path:
    return DATA_DIR / Path(relative_path).name


def _as_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding=config.CSV_ENCODING, newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=config.DETAIL_FAILURE_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)
    os.replace(temp, path)


def load_failure_records() -> dict[str, dict]:
    path = _path(config.DETAIL_FAILURES_CSV)
    if not path.exists():
        return {}
    with path.open("r", encoding=config.CSV_ENCODING, newline="") as file:
        return {
            row["豆瓣ID"].strip(): row
            for row in csv.DictReader(file)
            if row.get("豆瓣ID", "").strip()
        }


def _save_states(states: dict[str, dict]) -> None:
    records = list(states.values())
    _write_records(_path(config.DETAIL_FAILURES_CSV), records)
    unavailable = [record for record in records if record.get("状态") == "不可用"]
    _write_records(_path(config.UNAVAILABLE_MOVIES_CSV), unavailable)


def is_permanent_reason(reason: str) -> bool:
    return reason in PERMANENT_HTTP_REASONS


def record_failure(
    movie_id: str,
    title: str,
    reason: str,
    round_number: int,
    captured_at: str,
) -> dict:
    """记录一部电影在某轮的最终失败；同一轮重复调用不重复计数。"""
    states = load_failure_records()
    state = states.get(movie_id)
    if state is None:
        state = {field: "" for field in config.DETAIL_FAILURE_FIELDS}
        state.update(
            {
                "豆瓣ID": movie_id,
                "电影名称": title,
                "首次失败轮次": str(round_number),
                "失败轮次数": "0",
                "永久失败轮次数": "0",
                "连续永久失败轮次数": "0",
                "首次失败时间": captured_at,
            }
        )

    previous_round = _as_int(state.get("最后失败轮次"))
    previous_reason = state.get("最后失败原因", "")
    new_round = previous_round != round_number
    if new_round:
        state["失败轮次数"] = str(_as_int(state.get("失败轮次数")) + 1)
        if is_permanent_reason(reason):
            state["永久失败轮次数"] = str(_as_int(state.get("永久失败轮次数")) + 1)
            previous_was_consecutive = (
                previous_round == round_number - 1 and is_permanent_reason(previous_reason)
            )
            state["连续永久失败轮次数"] = str(
                _as_int(state.get("连续永久失败轮次数")) + 1
                if previous_was_consecutive
                else 1
            )
        else:
            state["连续永久失败轮次数"] = "0"

    state.update(
        {
            "电影名称": title,
            "最后失败原因": reason,
            "最后失败轮次": str(round_number),
            "最后更新时间": captured_at,
        }
    )
    state["状态"] = (
        "不可用" if _as_int(state.get("连续永久失败轮次数")) >= 2 else "待复核"
    )
    states[movie_id] = state
    _save_states(states)
    return state.copy()


def mark_success(movie_id: str, captured_at: str) -> None:
    states = load_failure_records()
    state = states.get(movie_id)
    if state is None:
        return
    state["状态"] = "已恢复"
    state["连续永久失败轮次数"] = "0"
    state["最后更新时间"] = captured_at
    _save_states(states)


def load_unavailable_ids() -> set[str]:
    return {
        movie_id
        for movie_id, record in load_failure_records().items()
        if record.get("状态") == "不可用"
    }


def next_round_number() -> int:
    last_round = max(
        (_as_int(record.get("最后失败轮次")) for record in load_failure_records().values()),
        default=0,
    )
    return last_round + 1
