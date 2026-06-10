"""Vanna + DeepSeek 服务封装。"""

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Optional

import pandas as pd
import sqlparse
from dotenv import load_dotenv
from openai import OpenAI
from vanna.legacy.chromadb import ChromaDB_VectorStore
from vanna.legacy.openai.openai_chat import OpenAI_Chat

from services.database import connect_database, get_sql_dialect, run_select_query
from services.period import DatePeriod, apply_date_period_to_sql

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger("vanna.ai")


def _ai_log_enabled() -> bool:
    return _get_env("AI_LOG_ENABLED", "true").lower() in {"1", "true", "yes"}


def _format_prompt_for_log(prompt: Any) -> str:
    try:
        return json.dumps(prompt, ensure_ascii=False, indent=2)
    except TypeError:
        return str(prompt)

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

SQLITE_ONLY_KEYWORDS = {"PRAGMA"}


class DeepSeekVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, config=None, client=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, client=client, config=config)

    def log(self, message: str, title: str = "Info"):
        if _ai_log_enabled():
            logger.info("[%s] %s", title, message)
        else:
            print(f"{title}: {message}")

    def submit_prompt(self, prompt, **kwargs) -> str:
        if _ai_log_enabled():
            logger.info("=" * 60)
            logger.info("[AI Prompt]\n%s", _format_prompt_for_log(prompt))

        content = OpenAI_Chat.submit_prompt(self, prompt, **kwargs)

        if _ai_log_enabled():
            logger.info("[AI 原始返回]\n%s", content)
            logger.info("=" * 60)

        return content

    def generate_sql(self, question: str, **kwargs) -> str:
        if _ai_log_enabled():
            logger.info("[AI 生成 SQL] question=%s", question)

        sql = super().generate_sql(question, **kwargs)

        if _ai_log_enabled():
            logger.info("[AI 提取 SQL]\n%s", sql)

        return sql.replace("\\_", "_")


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


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
    api_key = _get_env("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 .env 中设置")

    chroma_path = _get_env("CHROMA_PATH", os.path.join(BASE_DIR, "data", "chroma"))
    os.makedirs(chroma_path, exist_ok=True)

    base_url = _normalize_base_url(
        _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    model = _get_env("DEEPSEEK_MODEL", "deepseek-chat")

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
    if get_sql_dialect() == "SQLite":
        forbidden |= SQLITE_ONLY_KEYWORDS

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
    date_period: Optional[DatePeriod] = None,
) -> tuple[str, pd.DataFrame]:
    vn = get_vanna()
    trained_sql = _try_get_trained_sql(vn, query)

    if trained_sql:
        raw_sql = trained_sql
        if _ai_log_enabled():
            logger.info("[命中训练缓存] query=%s，跳过 AI 调用", query)
            logger.info("[训练缓存 SQL]\n%s", raw_sql)
    else:
        if _ai_log_enabled():
            logger.info("[调用 AI] query=%s", query)
        raw_sql = vn.generate_sql(query, allow_llm_to_see_data=True)

    sql = validate_select_sql(raw_sql)

    if date_period is not None:
        sql = apply_date_period_to_sql(sql, date_period)

    if _ai_log_enabled():
        logger.info("[最终执行 SQL]\n%s", sql)

    try:
        df = run_select_query(sql)
    except Exception as exc:
        raise ValueError(f"SQL 执行失败: {exc} | SQL: {sql}") from exc

    if _ai_log_enabled():
        logger.info("[查询结果] rows=%s, columns=%s", len(df), list(df.columns))

    return sql, df


def execute_sql(sql: str) -> tuple[str, pd.DataFrame]:
    validated_sql = validate_select_sql(sql)

    if _ai_log_enabled():
        logger.info("[直接执行 SQL]\n%s", validated_sql)

    try:
        df = run_select_query(validated_sql)
    except Exception as exc:
        raise ValueError(f"SQL 执行失败: {exc} | SQL: {validated_sql}") from exc

    if _ai_log_enabled():
        logger.info("[查询结果] rows=%s, columns=%s", len(df), list(df.columns))

    return validated_sql, df
