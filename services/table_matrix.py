"""将 SQL 查询结果转换为前端 chart-ai-query-api 所需的 tableMatrix 格式。"""

from typing import List

import pandas as pd

VALID_CHART_TYPES = {
    "bar",
    "column",
    "line",
    "area",
    "scatter",
    "pie",
    "ring",
    "radar",
}


def validate_chart_type(chart_type: str) -> None:
    if chart_type not in VALID_CHART_TYPES:
        raise ValueError(f"不支持的 chartType: {chart_type}")


def dataframe_to_table_matrix(df: pd.DataFrame, chart_type: str) -> List[List[str]]:
    validate_chart_type(chart_type)

    if df is None or df.empty:
        raise ValueError("查询结果为空，无法生成图表数据")

    if len(df.columns) < 2:
        raise ValueError("查询结果至少需要 2 列（1 列类别 + 1 列数值）")

    working_df = df.copy()
    working_df = _apply_chart_type_rules(working_df, chart_type)

    label_col = working_df.columns[0]
    series_cols = list(working_df.columns[1:])

    header = [""] + [str(col) for col in series_cols]
    rows: List[List[str]] = [header]

    for _, row in working_df.iterrows():
        label = _format_cell(row[label_col])
        values = [_format_cell(row[col]) for col in series_cols]
        rows.append([label] + values)

    return rows


def _apply_chart_type_rules(df: pd.DataFrame, chart_type: str) -> pd.DataFrame:
    if chart_type in {"pie", "ring"}:
        if len(df.columns) < 2:
            raise ValueError("饼图/环形图至少需要 1 列类别和 1 列数值")
        return df.iloc[:, :2]

    if chart_type == "scatter":
        if len(df.columns) < 3:
            raise ValueError("散点图至少需要 1 列类别和 2 列数值")
        return df.iloc[:, :3]

    return df


def _format_cell(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(round(value, 4)).rstrip("0").rstrip(".")
    return str(value)
