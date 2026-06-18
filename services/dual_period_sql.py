"""柱形图双日期合并为单条 SQL。"""

from services.baseline import BASELINE_COLUMN_NAME, filter_data_metric_columns
from services.database import run_select_query
from services.period import DatePeriod, apply_date_period_to_sql


def _quote_ident(name: str) -> str:
    if name.startswith("`") and name.endswith("`"):
        return name
    return f"`{name}`"


def _get_result_columns(sql: str) -> list[str]:
    preview = run_select_query(f"SELECT * FROM ({sql}) AS _preview LIMIT 1")
    return [str(col) for col in preview.columns.tolist()]


def build_bar_combined_sql(
    base_sql: str,
    data_period: DatePeriod,
    baseline_period: DatePeriod,
) -> str:
    """将基础聚合 SQL 合并为一条同时返回主数据与「基准」列的查询。"""
    data_sql = apply_date_period_to_sql(base_sql, data_period)
    baseline_sql = apply_date_period_to_sql(base_sql, baseline_period)

    columns = _get_result_columns(data_sql)
    if len(columns) < 2:
        raise ValueError("柱形图合并查询至少需要 2 列（类别 + 数值）")

    label_col = columns[0]
    metric_cols = filter_data_metric_columns(columns)
    if not metric_cols:
        raise ValueError("合并查询至少需要 1 列主数据数值指标")
    baseline_metric = metric_cols[0]

    label = _quote_ident(label_col)
    select_parts = [
        f"COALESCE(d.{label}, b.{label}) AS {label}",
    ]
    for metric in metric_cols:
        metric_ident = _quote_ident(metric)
        select_parts.append(f"d.{metric_ident} AS {metric_ident}")
    select_parts.append(
        f"IFNULL(b.{_quote_ident(baseline_metric)}, 0) AS {_quote_ident(BASELINE_COLUMN_NAME)}"
    )

    combined_sql = (
        "SELECT\n  "
        + ",\n  ".join(select_parts)
        + f"\nFROM ({data_sql}) AS d\n"
        + f"LEFT JOIN ({baseline_sql}) AS b\n"
        + f"  ON CAST(d.{label} AS CHAR) = CAST(b.{label} AS CHAR)"
    )
    return combined_sql
