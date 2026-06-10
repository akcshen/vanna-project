"""日期选择期校验与 SQL 过滤。"""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_date_column() -> str:
    column = _get_env("DATE_COLUMN", "销售日期")
    if column.startswith("`") and column.endswith("`"):
        return column
    return f"`{column}`"


@dataclass
class DatePeriod:
    start: str
    end: str

    def mysql_start(self) -> str:
        return _yyyymmdd_to_mysql_date(self.start)

    def mysql_end(self) -> str:
        return _yyyymmdd_to_mysql_date(self.end)


def _yyyymmdd_to_mysql_date(value: str) -> str:
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def parse_date_period(raw: Optional[Dict[str, Any]], field_name: str) -> DatePeriod:
    if not raw or not isinstance(raw, dict):
        raise ValueError(f"{field_name} 不能为空")

    start = str(raw.get("start") or "").strip()
    end = str(raw.get("end") or "").strip()

    if not start or not end:
        raise ValueError(f"{field_name}.start 和 {field_name}.end 不能为空")

    date_pattern = re.compile(r"^\d{8}$")
    if not date_pattern.match(start) or not date_pattern.match(end):
        raise ValueError(f"{field_name} 日期格式必须为 YYYYMMDD")

    try:
        start_date = datetime.strptime(start, "%Y%m%d")
        end_date = datetime.strptime(end, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} 日期无效") from exc

    if start_date > end_date:
        raise ValueError(f"{field_name}.start 不能晚于 {field_name}.end")

    return DatePeriod(start=start, end=end)


def apply_date_period_to_sql(sql: str, period: DatePeriod, date_column: Optional[str] = None) -> str:
    column = date_column or get_date_column()
    condition = (
        f"{column} BETWEEN '{period.mysql_start()}' AND '{period.mysql_end()}'"
    )

    cleaned = sql.strip().rstrip(";")
    upper = cleaned.upper()

    insert_pos = len(cleaned)
    for keyword in (" GROUP BY ", " ORDER BY ", " HAVING ", " LIMIT "):
        idx = upper.find(keyword)
        if idx != -1 and idx < insert_pos:
            insert_pos = idx

    head = cleaned[:insert_pos].rstrip()
    tail = cleaned[insert_pos:]

    if re.search(r"\bWHERE\b", head, re.IGNORECASE):
        is_null_pattern = re.compile(
            rf"{re.escape(column)}\s+IS\s+NOT\s+NULL",
            re.IGNORECASE,
        )
        if is_null_pattern.search(head):
            head = is_null_pattern.sub(condition, head, count=1)
        else:
            head = f"{head} AND {condition}"
    else:
        head = f"{head} WHERE {condition}"

    return f"{head}{tail}"
