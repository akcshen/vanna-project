"""基准列在 tableMatrix 中的格式与清洗。

前端约定：
  - 基准列列名固定为「基准」（BASELINE_COLUMN_NAME）
  - 基准列始终在最后一列
  - 主数据数值列在「基准」之前

本模块不负责「计算」基准值（计算在 dual_period_sql 的 JOIN 里完成），
只负责结果后处理：去掉 AI 多生成的「基准总行驶里程」等冗余列，并调整列顺序。
"""

from typing import List

import pandas as pd

BASELINE_COLUMN_NAME = "基准"


def is_redundant_baseline_column(name: str) -> bool:
    """判断是否为多余的基准系列列（保留标准列名「基准」）。"""
    text = str(name).strip()
    if text == BASELINE_COLUMN_NAME:
        return False
    return text.startswith("基准")


def filter_data_metric_columns(columns: list[str]) -> list[str]:
    """从查询结果列中筛出主数据数值列，排除基准相关列。"""
    if len(columns) < 2:
        return []
    return [col for col in columns[1:] if not is_redundant_baseline_column(col)]


def sanitize_baseline_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """移除「基准总行驶里程」等冗余基准列，仅保留最后一列「基准」。"""
    if df is None or df.empty or len(df.columns) < 2:
        return df

    label_col = df.columns[0]
    kept: list = []
    baseline_col = None

    for col in df.columns[1:]:
        text = str(col).strip()
        if text == BASELINE_COLUMN_NAME:
            baseline_col = col
        elif is_redundant_baseline_column(text):
            continue
        else:
            kept.append(col)

    if baseline_col is not None:
        kept.append(baseline_col)

    return df[[label_col] + kept]


def _remove_baseline_column(table_matrix: List[List[str]]) -> List[List[str]]:
    if not table_matrix:
        return table_matrix

    header = table_matrix[0]
    if BASELINE_COLUMN_NAME not in header:
        return table_matrix

    col_idx = header.index(BASELINE_COLUMN_NAME)
    updated: List[List[str]] = [header[:col_idx] + header[col_idx + 1 :]]
    for row in table_matrix[1:]:
        row_list = list(row)
        if col_idx < len(row_list):
            updated.append(row_list[:col_idx] + row_list[col_idx + 1 :])
        else:
            updated.append(row_list)
    return updated


def _remove_redundant_baseline_columns_from_matrix(
    table_matrix: List[List[str]],
) -> List[List[str]]:
    if not table_matrix:
        return table_matrix

    header = table_matrix[0]
    keep_indices = [0]
    baseline_idx = None

    for idx, col in enumerate(header):
        if idx == 0:
            continue
        text = str(col).strip()
        if text == BASELINE_COLUMN_NAME:
            baseline_idx = idx
        elif is_redundant_baseline_column(text):
            continue
        else:
            keep_indices.append(idx)

    if baseline_idx is not None and baseline_idx not in keep_indices:
        keep_indices.append(baseline_idx)

    if keep_indices == list(range(len(header))):
        return table_matrix

    updated = [[header[i] for i in keep_indices]]
    for row in table_matrix[1:]:
        updated.append([row[i] if i < len(row) else "" for i in keep_indices])
    return updated


def normalize_baseline_column_position(table_matrix: List[List[str]]) -> List[List[str]]:
    """移除冗余基准列，并将「基准」列移动到最后一列。"""
    table_matrix = _remove_redundant_baseline_columns_from_matrix(table_matrix)
    if not table_matrix or BASELINE_COLUMN_NAME not in table_matrix[0]:
        return table_matrix

    header = table_matrix[0]
    col_idx = header.index(BASELINE_COLUMN_NAME)
    if col_idx == len(header) - 1:
        return table_matrix

    baseline_values = []
    for row in table_matrix[1:]:
        value = row[col_idx] if col_idx < len(row) else ""
        baseline_values.append(value)

    without_baseline = _remove_baseline_column(table_matrix)
    updated = [without_baseline[0] + [BASELINE_COLUMN_NAME]]
    for row_idx, row in enumerate(without_baseline[1:], start=0):
        updated.append(list(row) + [baseline_values[row_idx]])
    return updated
