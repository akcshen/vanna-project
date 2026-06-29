"""needBaseline=true 时，将「数据期」与「基准期」合并为一条 SQL。

整体思路（不依赖 AI 在一条 SQL 里写两个日期，而是后端拼装）：

  1. AI / 训练缓存 生成「基础 SQL」——只描述查什么、按什么分组，例如：
       SELECT 排放标准, ROUND(SUM(mileage),2) AS 总行驶里程
       FROM vd_daily WHERE stat_time IS NOT NULL GROUP BY 排放标准

  2. 同一份基础 SQL 复制两份，分别注入不同日期（apply_date_period_to_sql）：
       - 子查询 d：dataPeriod    → 主数据（柱子的当前值）
       - 子查询 b：baselinePeriod → 基准数据（对比用的历史值）

  3. 用 LEFT JOIN 按「类别列」（第 1 列）对齐，拼成最终结果：
       SELECT
         d.排放标准,
         d.总行驶里程,                              -- 来自数据期
         IFNULL(b.总行驶里程, 0) AS `基准`          -- 来自基准期，缺失补 0
       FROM (数据期 SQL) d
       LEFT JOIN (基准期 SQL) b ON d.排放标准 = b.排放标准

  4. 前端 tableMatrix 最后一列固定为「基准」，用于渲染基准折线。

注意：若 AI 在 SELECT 里写了 CASE WHEN stat_time >= '某天' 这类日期条件，
     基准子查询里该表达式可能恒为 0；因此合并前会调用
     normalize_base_sql_for_period_merge() 去掉这些 CASE，日期统一由 WHERE 控制。
"""

from services.baseline import (
    BASELINE_COLUMN_NAME,
    filter_data_metric_columns,
    is_redundant_baseline_column,
)
from services.database import run_select_query
from services.period import DatePeriod, apply_date_period_to_sql


def _quote_ident(name: str) -> str:
    if name.startswith("`") and name.endswith("`"):
        return name
    return f"`{name}`"


def _get_result_columns(sql: str) -> list[str]:
    """执行 LIMIT 1 预览，拿到子查询结果的真实列名（含中文别名）。"""
    preview = run_select_query(f"SELECT * FROM ({sql}) AS _preview LIMIT 1")
    return [str(col) for col in preview.columns.tolist()]


def _resolve_baseline_value_column(
    columns: list[str],
    data_metric_cols: list[str],
) -> str:
    """决定 JOIN 后「基准」列从基准子查询的哪一列取值。

    数据期与基准期来自同一份 base_sql，列结构一致，无需二次预览查询。

    优先级：
      1. 列名以「基准」开头（如 基准总行驶里程）——AI 若多生成了这类列，优先用它
      2. 否则用第一个主数据数值列（与 d 侧指标同名，如 总行驶里程）
    """
    for col in columns[1:]:
        if is_redundant_baseline_column(col):
            return col

    if data_metric_cols:
        return data_metric_cols[0]
    raise ValueError("无法从子查询中解析数值列")


def build_bar_combined_sql(
    base_sql: str,
    data_period: DatePeriod,
    baseline_period: DatePeriod,
) -> str:
    """将基础 SQL 包装为「数据期 d + 基准期 b + LEFT JOIN」的单条查询。"""
    # 同一份基础 SQL，分别套上数据期 / 基准期的 WHERE 日期过滤
    data_sql = apply_date_period_to_sql(base_sql, data_period)
    baseline_sql = apply_date_period_to_sql(base_sql, baseline_period)

    columns = _get_result_columns(data_sql)
    if len(columns) < 2:
        raise ValueError("柱形图合并查询至少需要 2 列（类别 + 数值）")

    label_col = columns[0]  # 类别维度，JOIN 对齐键，如 排放标准 / 车型
    metric_cols = filter_data_metric_columns(columns)  # 主数据数值列，排除 AI 多余的「基准*」列
    if not metric_cols:
        raise ValueError("合并查询至少需要 1 列主数据数值指标")
    baseline_value_col = _resolve_baseline_value_column(columns, metric_cols)

    label = _quote_ident(label_col)
    select_parts = [
        # 类别以数据期为准，基准期缺该类时仍保留数据期行
        f"COALESCE(d.{label}, b.{label}) AS {label}",
    ]
    for metric in metric_cols:
        metric_ident = _quote_ident(metric)
        select_parts.append(f"d.{metric_ident} AS {metric_ident}")
    # 基准值只从基准期子查询 b 取；对不上或为空则 0
    select_parts.append(
        f"IFNULL(b.{_quote_ident(baseline_value_col)}, 0) AS {_quote_ident(BASELINE_COLUMN_NAME)}"
    )

    combined_sql = (
        "SELECT\n  "
        + ",\n  ".join(select_parts)
        + f"\nFROM ({data_sql}) AS d\n"
        + f"LEFT JOIN ({baseline_sql}) AS b\n"
        + f"  ON CAST(d.{label} AS CHAR) = CAST(b.{label} AS CHAR)"
    )
    return combined_sql
