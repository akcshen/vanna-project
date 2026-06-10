"""柱形图基准数据构建。"""

from typing import List

import pandas as pd

BASELINE_COLUMN_NAME = "基准"


def extract_labels_from_matrix(table_matrix: List[List[str]]) -> List[str]:
    return [row[0] for row in table_matrix[1:] if row]


def _format_baseline_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(round(value, 4)).rstrip("0").rstrip(".")


def _build_baseline_mapping(baseline_df: pd.DataFrame) -> dict[str, float]:
    if baseline_df is None or baseline_df.empty:
        raise ValueError("基准查询结果为空，无法生成基准列")

    if len(baseline_df.columns) < 2:
        raise ValueError("基准查询结果至少需要 2 列（类别 + 数值）")

    label_col = baseline_df.columns[0]
    value_col = baseline_df.columns[1]

    mapping: dict[str, float] = {}
    for _, row in baseline_df.iterrows():
        key = str(row[label_col])
        value = row[value_col]
        if pd.isna(value):
            mapping[key] = 0.0
        else:
            mapping[key] = float(value)

    return mapping


def append_baseline_column(
    table_matrix: List[List[str]],
    baseline_df: pd.DataFrame,
) -> List[List[str]]:
    """在 tableMatrix 中追加或更新「基准」列，与前端 BASELINE_COLUMN_NAME 一致。"""
    labels = extract_labels_from_matrix(table_matrix)
    if not labels:
        return table_matrix

    mapping = _build_baseline_mapping(baseline_df)
    values: List[str] = []
    for label in labels:
        if label not in mapping:
            raise ValueError(f"基准数据缺少类别: {label}")
        values.append(_format_baseline_value(mapping[label]))

    header = table_matrix[0]
    if BASELINE_COLUMN_NAME in header:
        col_idx = header.index(BASELINE_COLUMN_NAME)
        updated = [header]
        for row_idx, row in enumerate(table_matrix[1:], start=0):
            new_row = list(row)
            while len(new_row) <= col_idx:
                new_row.append("")
            new_row[col_idx] = values[row_idx]
            updated.append(new_row)
        return updated

    updated = [header + [BASELINE_COLUMN_NAME]]
    for row_idx, row in enumerate(table_matrix[1:], start=0):
        updated.append(list(row) + [values[row_idx]])
    return updated
