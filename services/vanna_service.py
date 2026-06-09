"""Vanna + DeepSeek 服务封装。"""

import os
import re
from functools import lru_cache

import pandas as pd
import sqlparse
from dotenv import load_dotenv
from openai import OpenAI
from vanna.legacy.chromadb import ChromaDB_VectorStore
from vanna.legacy.openai.openai_chat import OpenAI_Chat

from services.database import connect_database, get_sql_dialect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

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

    def generate_sql(self, question: str, **kwargs) -> str:
        sql = super().generate_sql(question, **kwargs)
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


def _clean_generated_sql(sql: str) -> str:
    """清理模型输出，尽量提取可执行的 SELECT 语句。"""
    cleaned = (sql or "").strip()

    code_block = re.search(r"```(?:sql)?\s*\n(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_block:
        cleaned = code_block.group(1).strip()

    for pattern in (
        r"(CREATE\s+TABLE\b.*?\bAS\b\s+SELECT\b.*?)(?:;|\Z)",
        r"(WITH\b.*?SELECT\b.*?)(?:;|\Z)",
        r"(SELECT\b.*?)(?:;|\Z)",
    ):
        matches = re.findall(pattern, cleaned, re.DOTALL | re.IGNORECASE)
        if matches:
            cleaned = matches[-1].strip().rstrip(";")
            break

    return cleaned.strip().rstrip(";")


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


def generate_and_run_sql(query: str) -> tuple[str, pd.DataFrame]:
    vn = get_vanna()
    raw_sql = vn.generate_sql(query)
    sql = validate_select_sql(raw_sql)
    df = vn.run_sql(sql)
    return sql, df
