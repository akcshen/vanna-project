"""图表查询日志工具。"""

import logging
import os
from typing import Any, Iterable, Optional

import pandas as pd

from services.period import DatePeriod

logger = logging.getLogger("vanna.ai")


def ai_log_enabled() -> bool:
    return os.getenv("AI_LOG_ENABLED", "true").lower() in {"1", "true", "yes"}


def is_debug() -> bool:
    return logger.isEnabledFor(logging.DEBUG)


def compact_sql(sql: str, max_len: int = 600) -> str:
    normalized = " ".join((sql or "").split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[:max_len]}..."


def format_period(period: Optional[DatePeriod]) -> str:
    if period is None:
        return "-"
    return f"{period.start}~{period.end}"


def log_section(title: str, lines: Iterable[str], level: int = logging.INFO) -> None:
    if not ai_log_enabled():
        return
    logger.log(level, "┌─ %s", title)
    for line in lines:
        logger.log(level, "│ %s", line)
    logger.log(level, "└─")


def log_request_start(
    endpoint: str,
    query: str = "",
    chart_type: str = "",
    need_baseline: bool = False,
    data_period: Optional[DatePeriod] = None,
    baseline_period: Optional[DatePeriod] = None,
    sql: str = "",
) -> None:
    if not ai_log_enabled():
        return
    lines = []
    if query:
        lines.append(f"query: {query}")
    if chart_type:
        lines.append(f"chartType: {chart_type}")
    lines.append(f"needBaseline: {need_baseline}")
    if data_period is not None:
        lines.append(f"dataPeriod: {format_period(data_period)}")
    if need_baseline and baseline_period is not None:
        lines.append(f"baselinePeriod: {format_period(baseline_period)}")
    if sql:
        lines.append(f"sql: {compact_sql(sql)}")
    log_section(endpoint, lines)


def log_sql_stage(
    stage: str,
    *,
    source: str = "",
    query: str = "",
    period: Optional[DatePeriod] = None,
    sql: str = "",
    rows: Optional[int] = None,
    columns: Optional[list[str]] = None,
    categories: Optional[list[str]] = None,
) -> None:
    if not ai_log_enabled():
        return

    lines: list[str] = []
    if source:
        lines.append(f"来源: {source}")
    if query:
        lines.append(f"问题: {query}")
    if period is not None:
        lines.append(f"日期: {format_period(period)}")
    if sql:
        if is_debug():
            lines.append("SQL:")
            for sql_line in sql.splitlines():
                lines.append(f"  {sql_line}")
        else:
            lines.append(f"SQL: {compact_sql(sql)}")
    if rows is not None:
        line = f"结果: {rows} 行"
        if columns:
            line += f", 列={columns}"
        lines.append(line)
    if categories:
        preview = categories[:8]
        suffix = "..." if len(categories) > 8 else ""
        lines.append(f"类别: {preview}{suffix}")

    log_section(stage, lines)


def log_ai_prompt(prompt: Any) -> None:
    if not ai_log_enabled():
        return
    if is_debug():
        import json

        try:
            body = json.dumps(prompt, ensure_ascii=False, indent=2)
        except TypeError:
            body = str(prompt)
        log_section("AI Prompt", body.splitlines(), level=logging.DEBUG)
    else:
        logger.info("AI Prompt 已发送（完整内容请设置 LOG_LEVEL=DEBUG）")


def log_ai_response(content: str) -> None:
    if not ai_log_enabled():
        return
    if is_debug():
        log_section("AI 返回", content.splitlines(), level=logging.DEBUG)
    else:
        logger.info("AI 返回已收到（完整内容请设置 LOG_LEVEL=DEBUG）")


def log_baseline_merge_error(
    main_labels: list[str],
    baseline_labels: list[str],
    missing_label: str,
) -> None:
    if not ai_log_enabled():
        return
    main_set = set(main_labels)
    baseline_set = set(baseline_labels)
    missing = sorted(main_set - baseline_set)
    extra = sorted(baseline_set - main_set)
    log_section(
        "基准列合并失败",
        [
            f"缺失类别: {missing_label}",
            f"主数据类别({len(main_labels)}): {main_labels[:10]}{'...' if len(main_labels) > 10 else ''}",
            f"基准类别({len(baseline_labels)}): {baseline_labels[:10]}{'...' if len(baseline_labels) > 10 else ''}",
            f"主数据有、基准无: {missing[:10]}{'...' if len(missing) > 10 else ''}",
            f"基准有、主数据无: {extra[:10]}{'...' if len(extra) > 10 else ''}",
        ],
        level=logging.WARNING,
    )


def extract_categories(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    return [str(value) for value in df.iloc[:, 0].tolist()]
