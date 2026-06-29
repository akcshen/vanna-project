"""Vanna + DeepSeek 服务封装。"""

import logging
import os
import re
from functools import lru_cache
from typing import Optional

import pandas as pd
import sqlparse
from openai import OpenAI
from vanna.legacy.chromadb import ChromaDB_VectorStore
from vanna.legacy.openai.openai_chat import OpenAI_Chat

from services.baseline import sanitize_baseline_dataframe
from services.config import BASE_DIR, get_env
from services.database import connect_database, get_sql_dialect, run_select_query
from services.dual_period_sql import build_bar_combined_sql
from services.period import (
    DatePeriod,
    apply_date_period_to_sql,
    build_ai_question_with_period,
    build_bar_base_ai_question,
    normalize_base_sql_for_period_merge,
)
from services.query_log import (
    ai_log_enabled,
    extract_categories,
    log_ai_prompt,
    log_ai_response,
    log_sql_stage,
)

logger = logging.getLogger("vanna.ai")

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "ATTACH",
    "DETACH",
}


class DeepSeekVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, config=None, client=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, client=client, config=config)

    def log(self, message: str, title: str = "Info"):
        if ai_log_enabled():
            logger.debug("[%s] %s", title, message)

    def submit_prompt(self, prompt, **kwargs) -> str:
        log_ai_prompt(prompt)
        content = OpenAI_Chat.submit_prompt(self, prompt, **kwargs)
        log_ai_response(content)
        return content

    def generate_sql(self, question: str, **kwargs) -> str:
        sql = super().generate_sql(question, **kwargs)
        return sql.replace("\\_", "_")


def _normalize_base_url(url: str) -> str:
    """规范化模型 API 地址，兼容带/不带 /v1 后缀。"""
    normalized = url.strip().rstrip("/")
    if not normalized:
        raise RuntimeError("DEEPSEEK_BASE_URL 不能为空")
    return normalized


def _build_initial_prompt() -> str:
    dialect = get_sql_dialect()
    return (
        f"你是 {dialect} 数据分析助手。请根据用户问题生成可执行的 SELECT 语句。"
        "结果第 1 列必须是类别维度（如季度、月份、产品名），"
        "第 2 列起必须是数值指标（如销售额、数量）。"
        "只返回 SQL，不要解释。"
    )


def create_vanna_instance() -> DeepSeekVanna:
    api_key = get_env("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 .env 中设置")

    chroma_path = get_env("CHROMA_PATH", os.path.join(BASE_DIR, "data", "chroma"))
    os.makedirs(chroma_path, exist_ok=True)

    base_url = _normalize_base_url(
        get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    model = get_env("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)

    config = {
        "api_key": api_key,
        "model": model,
        "path": chroma_path,
        "initial_prompt": _build_initial_prompt(),
    }

    vn = DeepSeekVanna(config=config, client=client)
    connect_database(vn)
    return vn


@lru_cache(maxsize=1)
def get_vanna() -> DeepSeekVanna:
    return create_vanna_instance()


def reset_vanna_cache() -> None:
    get_vanna.cache_clear()


def _clean_generated_sql(sql: str) -> str:
    """清理模型输出，尽量提取可执行的 SELECT 语句。"""
    cleaned = (sql or "").strip()

    if cleaned.startswith("The LLM is not allowed to see the data"):
        raise ValueError(
            "模型需要表结构信息才能生成 SQL，请先执行: python scripts/train.py"
        )

    code_block = re.search(r"```(?:sql)?\s*\n(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_block:
        cleaned = code_block.group(1).strip()

    select_candidates = re.findall(
        r"(WITH\b[\s\S]*?SELECT\b[\s\S]*?|SELECT\b[\s\S]*?)(?=;|\Z)",
        cleaned,
        re.IGNORECASE,
    )
    if select_candidates:
        cleaned = select_candidates[-1].strip().rstrip(";")
    else:
        for pattern in (
            r"(CREATE\s+TABLE\b.*?\bAS\b\s+SELECT\b[\s\S]*?)(?=;|\Z)",
            r"(SELECT\b[\s\S]*?)(?=;|\Z)",
        ):
            matches = re.findall(pattern, cleaned, re.DOTALL | re.IGNORECASE)
            if matches:
                cleaned = matches[-1].strip().rstrip(";")
                break

    cleaned = re.sub(r"[\r\n]+[（(]?(?:注|说明|假设).*$", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().rstrip(";")
    return cleaned


def _is_select_query(sql: str) -> bool:
    statements = [stmt for stmt in sqlparse.parse(sql) if str(stmt).strip()]
    if len(statements) != 1:
        return False

    statement_type = statements[0].get_type()
    if statement_type == "SELECT":
        return True

    if statement_type == "UNKNOWN":
        leading = sql.lstrip().upper()
        return leading.startswith("SELECT") or leading.startswith("WITH")

    return False


def validate_select_sql(sql: str) -> str:
    cleaned = _clean_generated_sql(sql)
    if not cleaned:
        raise ValueError("生成的 SQL 为空")

    if not _is_select_query(cleaned):
        preview = cleaned[:200].replace("\n", " ")
        raise ValueError(f"仅允许执行 SELECT 查询，当前生成: {preview}")

    forbidden = set(FORBIDDEN_SQL_KEYWORDS)
    upper_sql = cleaned.upper()
    for keyword in forbidden:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"SQL 包含禁止关键字: {keyword}")

    return cleaned


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", "", (question or "").strip().lower())


def _try_get_trained_sql(vn: DeepSeekVanna, query: str) -> str:
    similar_items = vn.get_similar_question_sql(query) or []
    normalized_query = _normalize_question(query)
    matched_sql: list[str] = []

    for item in similar_items:
        if not isinstance(item, dict):
            continue

        trained_question = str(item.get("question", "")).strip()
        trained_sql = str(item.get("sql", "")).strip()
        if not trained_sql:
            continue

        if _normalize_question(trained_question) == normalized_query:
            matched_sql.append(trained_sql)

    return matched_sql[-1] if matched_sql else ""


def generate_and_run_sql(
    query: str,
    data_period: Optional[DatePeriod] = None,
    stage: str = "SQL 查询",
) -> tuple[str, pd.DataFrame]:
    """单期查询（needBaseline=false）。

    只需 data_period：同时用于 AI 问题说明和 SQL 的 WHERE 日期过滤。

    不含 baseline_period——基准逻辑在 generate_and_run_bar_sql 中处理，
    该函数会同时使用 data_period 与 baseline_period 做 d JOIN b 合并。
    """
    vn = get_vanna()
    trained_sql = _try_get_trained_sql(vn, query)
    ai_question = build_ai_question_with_period(query, data_period)

    if trained_sql:
        raw_sql = trained_sql
        source = "训练缓存"
    else:
        source = "AI 生成"
        raw_sql = vn.generate_sql(ai_question, allow_llm_to_see_data=True)

    sql = validate_select_sql(raw_sql)

    if data_period is not None:
        sql = apply_date_period_to_sql(sql, data_period)

    try:
        df = run_select_query(sql)
    except Exception as exc:
        log_sql_stage(
            stage,
            source=source,
            query=query,
            period=data_period,
            sql=sql,
        )
        raise ValueError(f"SQL 执行失败: {exc} | SQL: {sql}") from exc

    log_sql_stage(
        stage,
        source=source,
        query=query if ai_question == query else ai_question,
        period=data_period,
        sql=sql,
        rows=len(df),
        columns=list(df.columns),
        categories=extract_categories(df),
    )

    return sql, df


def generate_and_run_bar_sql(
    query: str,
    data_period: DatePeriod,
    baseline_period: DatePeriod,
    stage: str = "合并查询（含基准）",
) -> tuple[str, pd.DataFrame]:
    """带基准的合并查询（needBaseline=true）。

    参数分工：
      - data_period：数据期，注入子查询 d 的 WHERE，结果映射为 tableMatrix 主指标列
      - baseline_period：基准期，注入子查询 b 的 WHERE，JOIN 后写入「基准」列

    流程：
    ① 用自然语言 query 让 AI（或训练缓存）生成基础 SQL
    ② normalize_base_sql_for_period_merge 清洗 SELECT 中的日期 CASE
    ③ build_bar_combined_sql 拼成 d JOIN b 的单条 SQL 并执行
    ④ sanitize_baseline_dataframe 去掉多余的「基准总行驶里程」等列，只留「基准」
    """
    vn = get_vanna()
    trained_sql = _try_get_trained_sql(vn, query)
    ai_question = build_bar_base_ai_question(query, data_period, baseline_period)

    # ① 获取基础 SQL（只描述查什么、按什么分组，不含两个具体日期）
    if trained_sql:
        raw_sql = trained_sql
        source = "训练缓存"
    else:
        source = "AI 生成"
        raw_sql = vn.generate_sql(ai_question, allow_llm_to_see_data=True)

    # ② 清洗 + ③ 拼合并 SQL（内部会各注入 dataPeriod / baselinePeriod）
    base_sql = normalize_base_sql_for_period_merge(validate_select_sql(raw_sql))
    combined_sql = build_bar_combined_sql(
        base_sql,
        data_period,
        baseline_period,
    )

    try:
        df = run_select_query(combined_sql)
        # ④ 结果只保留：类别 + 主指标 + 最后一列「基准」
        df = sanitize_baseline_dataframe(df)
    except Exception as exc:
        log_sql_stage(
            stage,
            source=source,
            query=ai_question,
            period=data_period,
            sql=combined_sql,
        )
        raise ValueError(f"SQL 执行失败: {exc} | SQL: {combined_sql}") from exc

    log_sql_stage(
        stage,
        source=source,
        query=ai_question,
        period=data_period,
        sql=combined_sql,
        rows=len(df),
        columns=list(df.columns),
        categories=extract_categories(df),
    )

    return combined_sql, df


def execute_sql(sql: str, stage: str = "SQL 直查") -> tuple[str, pd.DataFrame]:
    validated_sql = validate_select_sql(sql)

    try:
        df = run_select_query(validated_sql)
    except Exception as exc:
        log_sql_stage(stage, source="用户输入", sql=validated_sql)
        raise ValueError(f"SQL 执行失败: {exc} | SQL: {validated_sql}") from exc

    log_sql_stage(
        stage,
        source="用户输入",
        sql=validated_sql,
        rows=len(df),
        columns=list(df.columns),
        categories=extract_categories(df),
    )

    return validated_sql, df
