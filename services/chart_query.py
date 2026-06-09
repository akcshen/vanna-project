"""图表 AI 查询业务逻辑。"""

from services.table_matrix import dataframe_to_table_matrix
from services.vanna_service import generate_and_run_sql


def handle_chart_ai_query(query: str, chart_type: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {"state": -1, "message": "query 不能为空"}

    chart_type = (chart_type or "").strip()
    if not chart_type:
        return {"state": -1, "message": "chartType 不能为空"}

    try:
        sql, df = generate_and_run_sql(query)
        table_matrix = dataframe_to_table_matrix(df, chart_type)
        return {
            "state": 0,
            "sql": sql,
            "tableMatrix": table_matrix,
        }
    except ValueError as exc:
        payload = {"state": -1, "message": str(exc)}
        if "当前生成:" in str(exc):
            payload["sql"] = str(exc).split("当前生成:", 1)[-1].strip()
        return payload
    except RuntimeError as exc:
        return {"state": -1, "message": str(exc)}
    except Exception:
        return {
            "state": -1,
            "message": "无法理解该查询，请尝试更明确的描述",
        }
