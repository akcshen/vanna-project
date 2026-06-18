"""图表 AI 查询业务逻辑。

基准相关入口：handle_chart_ai_query(need_baseline=True)
  → generate_and_run_bar_sql → dual_period_sql.build_bar_combined_sql
详见 services/dual_period_sql.py 模块注释。
"""

import logging
import re
from typing import Any, Dict, Optional

from services.baseline import normalize_baseline_column_position
from services.period import DatePeriod, parse_date_period
from services.query_log import ai_log_enabled, log_request_start, log_section
from services.table_matrix import dataframe_to_table_matrix
from services.vanna_service import (
    execute_sql,
    generate_and_run_bar_sql,
    generate_and_run_sql,
)

logger = logging.getLogger("vanna.ai")


def _parse_baseline_period(
    need_baseline: bool,
    baseline_period_raw: Optional[Dict[str, Any]],
) -> Optional[DatePeriod]:
    """解析 baselinePeriod。仅 needBaseline=true 时必填，否则返回 None。"""
    if not need_baseline:
        return None
    if not baseline_period_raw:
        raise ValueError("needBaseline=true 时 baselinePeriod 不能为空")
    return parse_date_period(baseline_period_raw, "baselinePeriod")


def _extract_sql_from_message(message: str) -> str:
    match = re.search(r"\|\s*SQL:\s*(.+)$", message, re.DOTALL)
    return match.group(1).strip() if match else ""


def _build_error_payload(exc: Exception) -> dict:
    message = str(exc)
    payload = {"state": -1, "message": message}
    if "当前生成:" in message:
        payload["sql"] = message.split("当前生成:", 1)[-1].strip()
    elif " | SQL: " in message:
        payload["message"] = message.split(" | SQL: ", 1)[0]
        payload["sql"] = _extract_sql_from_message(message)
    return payload


def handle_chart_ai_query(
    query: str,
    chart_type: str,
    need_baseline: bool = False,
    data_period_raw: Optional[Dict[str, Any]] = None,
    baseline_period_raw: Optional[Dict[str, Any]] = None,
) -> dict:
    query = (query or "").strip()
    if not query:
        return {"state": -1, "message": "query 不能为空"}

    chart_type = (chart_type or "").strip()
    if not chart_type:
        return {"state": -1, "message": "chartType 不能为空"}

    try:
        data_period = parse_date_period(data_period_raw, "dataPeriod")
        baseline_period = _parse_baseline_period(need_baseline, baseline_period_raw)

        log_request_start(
            "chart_ai_query",
            query=query,
            chart_type=chart_type,
            data_period=data_period,
            baseline_period=baseline_period,
            need_baseline=need_baseline,
        )

        # ── 查询分流 ──────────────────────────────────────────────
        # needBaseline=true  → generate_and_run_bar_sql(data_period + baseline_period)
        # needBaseline=false → generate_and_run_sql(仅 data_period，无基准列)
        if need_baseline:
            # baseline_period 只传给 generate_and_run_bar_sql，用于基准期子查询 b
            sql, df = generate_and_run_bar_sql(
                query,
                data_period=data_period,
                baseline_period=baseline_period,
                stage="合并查询（含基准）",
            )
            table_matrix = normalize_baseline_column_position(
                dataframe_to_table_matrix(df, chart_type)
            )
            # 返回的 sql 已是合并后的完整 SQL；tableMatrix 末列为「基准」
            payload = {
                "state": 0,
                "sql": sql,
                "tableMatrix": table_matrix,
            }
        else:
            # 单期查询：只需 data_period，不需要 baseline_period
            sql, df = generate_and_run_sql(
                query,
                data_period=data_period,
                stage="数据查询",
            )
            table_matrix = dataframe_to_table_matrix(df, chart_type)
            payload = {
                "state": 0,
                "sql": sql,
                "tableMatrix": table_matrix,
            }

        if ai_log_enabled():
            rows = len(payload["tableMatrix"]) - 1
            cols = len(payload["tableMatrix"][0]) if payload["tableMatrix"] else 0
            lines = [f"state: 0", f"tableMatrix: {rows} 行 x {cols} 列"]
            if need_baseline:
                lines.append("单 SQL 已含基准列")
            log_section("chart_ai_query 完成", lines)

        return payload
    except ValueError as exc:
        if ai_log_enabled():
            log_section("chart_ai_query 失败", [str(exc)], level=logging.WARNING)
        return _build_error_payload(exc)
    except RuntimeError as exc:
        return {"state": -1, "message": str(exc)}
    except Exception as exc:
        return {
            "state": -1,
            "message": f"查询失败: {exc}",
        }


def handle_chart_sql_query(
    sql: str,
    chart_type: str,
) -> dict:
    sql = (sql or "").strip()
    if not sql:
        return {"state": -1, "message": "sql 不能为空"}

    chart_type = (chart_type or "").strip()
    if not chart_type:
        return {"state": -1, "message": "chartType 不能为空"}

    try:
        log_request_start(
            "chart_sql_query",
            chart_type=chart_type,
            sql=sql,
        )
        executed_sql, df = execute_sql(sql, stage="SQL 直查")
        table_matrix = normalize_baseline_column_position(
            dataframe_to_table_matrix(df, chart_type)
        )

        if ai_log_enabled():
            rows = len(table_matrix) - 1
            cols = len(table_matrix[0]) if table_matrix else 0
            log_section("chart_sql_query 完成", [f"state: 0", f"tableMatrix: {rows} 行 x {cols} 列"])

        return {
            "state": 0,
            "sql": executed_sql,
            "tableMatrix": table_matrix,
        }
    except ValueError as exc:
        if ai_log_enabled():
            log_section("chart_sql_query 失败", [str(exc)], level=logging.WARNING)
        return _build_error_payload(exc)
    except RuntimeError as exc:
        return {"state": -1, "message": str(exc)}
    except Exception as exc:
        return {
            "state": -1,
            "message": f"SQL 执行失败: {exc}",
        }
