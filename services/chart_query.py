"""图表 AI 查询业务逻辑。"""

import re
from typing import Any, Dict, Optional

from services.baseline import append_baseline_column
from services.period import DatePeriod, parse_date_period
from services.table_matrix import dataframe_to_table_matrix
from services.vanna_service import execute_sql, generate_and_run_sql

BAR_CHART_TYPES = {"bar"}


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
        baseline_period = parse_date_period(baseline_period_raw, "baselinePeriod")

        sql, df = generate_and_run_sql(query, date_period=data_period)
        table_matrix = dataframe_to_table_matrix(df, chart_type)

        payload = {
            "state": 0,
            "sql": sql,
            "tableMatrix": table_matrix,
        }

        if chart_type in BAR_CHART_TYPES:
            baseline_sql, baseline_df = generate_and_run_sql(
                query,
                date_period=baseline_period,
            )
            payload["baselineSql"] = baseline_sql
            payload["tableMatrix"] = append_baseline_column(table_matrix, baseline_df)

        return payload
    except ValueError as exc:
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
        executed_sql, df = execute_sql(sql)
        table_matrix = dataframe_to_table_matrix(df, chart_type)

        return {
            "state": 0,
            "sql": executed_sql,
            "tableMatrix": table_matrix,
        }
    except ValueError as exc:
        return _build_error_payload(exc)
    except RuntimeError as exc:
        return {"state": -1, "message": str(exc)}
    except Exception as exc:
        return {
            "state": -1,
            "message": f"SQL 执行失败: {exc}",
        }
