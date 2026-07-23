"""数据清洗入口。

原始数据保持不变，所有可再生产物写入 ``data/processed``。
"""

from src.data_cleaning import run_full_cleaning


def main() -> int:
    run_full_cleaning()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
