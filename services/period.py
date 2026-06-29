"""日期选择期校验与 SQL 过滤。

与基准相关的两个关键函数：
  - apply_date_period_to_sql：把 dataPeriod / baselinePeriod 写入 SQL 的 WHERE
  - normalize_base_sql_for_period_merge：合并基准前，清理 AI 在 SELECT 里写死的日期 CASE
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from services.config import get_env


def get_date_column() -> str:
    column = get_env("DATE_COLUMN", "stat_time")
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


def build_ai_question_with_period(
    query: str,
    data_period: Optional[DatePeriod] = None,
) -> str:
    """单期 AI 问题（配合 generate_and_run_sql，needBaseline=false）。

    只注入 dataPeriod。双日期场景请用 build_bar_base_ai_question。
    """
    question = (query or "").strip()
    if not question or data_period is None:
        return question

    date_column = _strip_column_backticks(get_date_column())
    return "\n".join(
        [
            question,
            f"数据日期范围：{_format_period_label(data_period)}。",
            (
                f"请使用字段 `{date_column}` 过滤，"
                f"仅统计 {data_period.mysql_start()} 至 {data_period.mysql_end()} 范围内的数据。"
            ),
        ]
    )


def build_bar_base_ai_question(
    query: str,
    data_period: DatePeriod,
    baseline_period: DatePeriod,
) -> str:
    """双期 AI 问题（配合 generate_and_run_bar_sql，needBaseline=true）。

    同时告知 AI 数据期与基准期的范围，但只让 AI 生成不含具体日期的基础 SQL；
    data_period / baseline_period 由后端分别注入子查询 d、b 的 WHERE。
    """
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


def normalize_base_sql_for_period_merge(base_sql: str) -> str:
    """合并基准前的 SQL 清洗。

    问题背景：AI 常生成
      SUM(CASE WHEN stat_time >= '2025-10-10' THEN mileage ELSE 0 END)
    若基准子查询的 WHERE 是 10-01~10-09，CASE 里仍要求 >= 10-10，
    则基准期每一行聚合结果都是 0，最终「基准」列全为 0。

    处理：把含 stat_time（DATE_COLUMN）的 CASE 还原成 SUM(mileage)，
    日期范围只由 apply_date_period_to_sql 写入 WHERE。
    """
    date_col = _strip_column_backticks(get_date_column())
    col_pattern = rf"(?:`{re.escape(date_col)}`|{re.escape(date_col)})"
    cleaned = base_sql

    round_case_pattern = re.compile(
        rf"ROUND\s*\(\s*SUM\s*\(\s*CASE\s+WHEN\s+.*?{col_pattern}.*?"
        rf"THEN\s+(.+?)\s+ELSE\s+(?:0|NULL)\s+END\s*\)\s*,\s*(\d+)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = round_case_pattern.sub(r"ROUND(SUM(\1), \2)", cleaned)

    agg_case_pattern = re.compile(
        rf"(SUM|AVG)\s*\(\s*CASE\s+WHEN\s+.*?{col_pattern}.*?"
        rf"THEN\s+(.+?)\s+ELSE\s+(?:0|NULL)\s+END\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    while agg_case_pattern.search(cleaned):
        cleaned = agg_case_pattern.sub(r"\1(\2)", cleaned)

    return cleaned


def apply_date_period_to_sql(sql: str, period: DatePeriod, date_column: Optional[str] = None) -> str:
    """在 SQL 的 WHERE 中注入日期 BETWEEN 条件（DATE_COLUMN，默认 stat_time）。

    用于把同一份基础 SQL 变成：
      - 数据期子查询：BETWEEN dataPeriod.start AND dataPeriod.end
      - 基准期子查询：BETWEEN baselinePeriod.start AND baselinePeriod.end

    若原 SQL 为 `stat_time IS NOT NULL`，会替换为 BETWEEN，避免重复过滤。
    """
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
    if tail and not tail.startswith((" ", "\n", "\t")):
        tail = f" {tail.lstrip()}"

    if re.search(r"\bWHERE\b", head, re.IGNORECASE):
        bare_col = _strip_column_backticks(column)
        is_null_pattern = re.compile(
            rf"`?{re.escape(bare_col)}`?\s+IS\s+NOT\s+NULL",
            re.IGNORECASE,
        )
        if is_null_pattern.search(head):
            head = is_null_pattern.sub(condition, head, count=1)
        else:
            head = f"{head} AND {condition}"
    else:
        head = f"{head} WHERE {condition}"

    return f"{head}{tail}"
