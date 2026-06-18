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


def _strip_column_backticks(column: str) -> str:
    if column.startswith("`") and column.endswith("`"):
        return column[1:-1]
    return column


def _format_period_label(period: DatePeriod) -> str:
    return (
        f"{period.start} 至 {period.end}"
        f"（{period.mysql_start()} 至 {period.mysql_end()}）"
    )


def build_ai_question_with_periods(
    query: str,
    active_period: Optional[DatePeriod] = None,
    data_period: Optional[DatePeriod] = None,
    baseline_period: Optional[DatePeriod] = None,
) -> str:
    """将数据日期与基准日期注入 AI 问题，便于生成带正确时间过滤的 SQL。"""
    question = (query or "").strip()
    if not question:
        return question

    if active_period is None and data_period is None and baseline_period is None:
        return question

    date_column = _strip_column_backticks(get_date_column())
    lines = [question]

    period_lines: list[str] = []
    if data_period is not None:
        period_lines.append(f"数据日期范围：{_format_period_label(data_period)}")
    if baseline_period is not None:
        period_lines.append(f"基准日期范围：{_format_period_label(baseline_period)}")

    if period_lines:
        lines.append("时间选择期：" + "；".join(period_lines) + "。")

    filter_period = active_period or data_period
    if filter_period is not None:
        lines.append(
            f"请使用字段 `{date_column}` 过滤，"
            f"仅统计 {filter_period.mysql_start()} 至 {filter_period.mysql_end()} 范围内的数据。"
        )

    return "\n".join(lines)


def build_bar_base_ai_question(
    query: str,
    data_period: DatePeriod,
    baseline_period: DatePeriod,
) -> str:
    """柱形图单 SQL 模式：让 AI 生成不含具体日期范围的基础聚合 SQL。"""
    question = (query or "").strip()
    if not question:
        return question

    date_column = _strip_column_backticks(get_date_column())
    lines = [
        question,
        (
            "时间选择期："
            f"数据日期范围：{_format_period_label(data_period)}；"
            f"基准日期范围：{_format_period_label(baseline_period)}。"
        ),
        (
            f"请生成按维度聚合的 SELECT（可用 `{date_column} IS NOT NULL`，"
            "不要写死具体日期范围）。"
            "只输出类别列和主数据数值列，不要生成「基准」或「基准」开头的列"
            "（如基准总行驶里程），系统会自动合并标准「基准」列。"
        ),
    ]
    return "\n".join(lines)


def apply_date_period_to_sql(sql: str, period: DatePeriod, date_column: Optional[str] = None) -> str:
    column = date_column or get_date_column()
    condition = (
        f"{column} BETWEEN '{period.mysql_start()}' AND '{period.mysql_end()}'"
    )

    cleaned = sql.strip().rstrip(";")
    clause_match = re.search(
        r"\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT)\b",
        cleaned,
        re.IGNORECASE,
    )
    insert_pos = clause_match.start() if clause_match else len(cleaned)

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
