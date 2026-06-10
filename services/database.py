"""数据库连接与 schema 获取。"""

import os
import re
import sqlite3
from typing import List, Optional

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def get_db_type() -> str:
    return _get_env("DB_TYPE", "sqlite").lower()


def get_sql_dialect() -> str:
    return "MySQL" if get_db_type() == "mysql" else "SQLite"


def get_mysql_config() -> dict:
    host = _get_env("MYSQL_HOST")
    port = _get_env("MYSQL_PORT", "3306")
    user = _get_env("MYSQL_USER")
    password = _get_env("MYSQL_PASSWORD")
    database = _get_env("MYSQL_DATABASE")

    missing = [
        key
        for key, value in {
            "MYSQL_HOST": host,
            "MYSQL_USER": user,
            "MYSQL_PASSWORD": password,
            "MYSQL_DATABASE": database,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"未配置 MySQL 连接信息: {', '.join(missing)}")

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
    }


def get_sqlite_path() -> str:
    return _get_env("DATABASE_PATH", os.path.join(BASE_DIR, "data", "sales.db"))


def get_mysql_tables_filter() -> Optional[List[str]]:
    raw = _get_env("MYSQL_TABLES")
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


_mysql_conn = None
_sqlite_conn = None


def reset_db_connection() -> None:
    """关闭并清空缓存的数据库连接，下次查询时自动重建。"""
    global _mysql_conn, _sqlite_conn

    if _mysql_conn is not None:
        try:
            _mysql_conn.close()
        except Exception:
            pass
        _mysql_conn = None

    if _sqlite_conn is not None:
        try:
            _sqlite_conn.close()
        except Exception:
            pass
        _sqlite_conn = None


def _create_mysql_connection():
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("请先安装 PyMySQL: pip install PyMySQL") from exc

    cfg = get_mysql_config()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        connect_timeout=30,
        read_timeout=120,
        write_timeout=120,
        autocommit=True,
    )


def _get_mysql_connection():
    global _mysql_conn
    if _mysql_conn is None:
        _mysql_conn = _create_mysql_connection()
    return _mysql_conn


def _get_sqlite_connection():
    global _sqlite_conn
    if _sqlite_conn is None:
        _sqlite_conn = sqlite3.connect(get_sqlite_path(), check_same_thread=False)
    return _sqlite_conn


def run_select_query(sql: str) -> pd.DataFrame:
    """执行 SELECT 查询，复用长连接；断线时自动 ping 重连，失败则重建连接重试一次。"""
    db_type = get_db_type()
    last_exc: Optional[Exception] = None

    for attempt in range(2):
        try:
            if db_type == "mysql":
                return _run_mysql_select(sql)
            if db_type == "sqlite":
                return _run_sqlite_select(sql)
            raise RuntimeError(f"不支持的 DB_TYPE: {db_type}，可选值: sqlite / mysql")
        except Exception as exc:
            last_exc = exc
            if attempt == 0 and _is_connection_error(exc):
                reset_db_connection()
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("SQL 执行失败")


def _is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 9:
        return True

    try:
        import pymysql
    except ImportError:
        return False

    return isinstance(exc, (pymysql.Error, pymysql.OperationalError, pymysql.InterfaceError))


def _run_mysql_select(sql: str) -> pd.DataFrame:
    conn = _get_mysql_connection()
    conn.ping(reconnect=True)

    with conn.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(rows, columns=columns)


def _run_sqlite_select(sql: str) -> pd.DataFrame:
    conn = _get_sqlite_connection()
    return pd.read_sql_query(sql, conn)


def connect_database(vn) -> None:
    db_type = get_db_type()

    if db_type == "mysql":
        cfg = get_mysql_config()
        vn.connect_to_mysql(
            host=cfg["host"],
            dbname=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            port=cfg["port"],
        )
        vn.dialect = "MySQL"
        return

    if db_type == "sqlite":
        database_path = get_sqlite_path()
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        vn.connect_to_sqlite(database_path)
        vn.dialect = "SQLite"
        return

    raise RuntimeError(f"不支持的 DB_TYPE: {db_type}，可选值: sqlite / mysql")


def fetch_mysql_ddls() -> List[str]:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("请先安装 PyMySQL: pip install PyMySQL") from exc

    cfg = get_mysql_config()
    table_filter = get_mysql_tables_filter()

    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
    )

    ddls: List[str] = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            if table_filter:
                tables = [name for name in tables if name in table_filter]

            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                row = cursor.fetchone()
                if row and len(row) > 1 and row[1]:
                    ddls.append(f"{row[1]};")
    finally:
        conn.close()

    if not ddls:
        raise RuntimeError("未从 MySQL 读取到任何表结构，请检查 MYSQL_DATABASE / MYSQL_TABLES 配置")

    return ddls


def list_mysql_tables() -> List[str]:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("请先安装 PyMySQL: pip install PyMySQL") from exc

    cfg = get_mysql_config()
    table_filter = get_mysql_tables_filter()

    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    if table_filter:
        tables = [name for name in tables if name in table_filter]

    return tables


def list_sqlite_tables() -> List[str]:
    database_path = get_sqlite_path()
    if not os.path.exists(database_path):
        return []

    conn = sqlite3.connect(database_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def list_connected_tables() -> dict:
    """查询当前数据库连接可访问的表。"""
    db_type = get_db_type()

    if db_type == "mysql":
        cfg = get_mysql_config()
        tables = list_mysql_tables()
        return {
            "dbType": "mysql",
            "database": cfg["database"],
            "host": cfg["host"],
            "port": cfg["port"],
            "tables": tables,
            "count": len(tables),
        }

    if db_type == "sqlite":
        tables = list_sqlite_tables()
        return {
            "dbType": "sqlite",
            "database": get_sqlite_path(),
            "tables": tables,
            "count": len(tables),
        }

    raise RuntimeError(f"不支持的 DB_TYPE: {db_type}")


def extract_table_names_from_ddls(ddls: List[str]) -> List[str]:
    names: List[str] = []
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`'\"]?(\w+)[`'\"]?",
        re.IGNORECASE,
    )

    for ddl in ddls:
        match = pattern.search(ddl)
        if match:
            names.append(match.group(1))

    return names


def list_trained_tables() -> dict:
    """查询已训练进 Vanna 向量库的表结构。"""
    from services.vanna_service import get_vanna

    vn = get_vanna()
    training_data = vn.get_training_data()

    if training_data is None or training_data.empty:
        return {"tables": [], "count": 0, "ddls": []}

    ddl_rows = training_data[training_data["training_data_type"] == "ddl"]
    ddls = [str(content) for content in ddl_rows["content"].tolist() if content]
    tables = extract_table_names_from_ddls(ddls)

    return {
        "tables": tables,
        "count": len(tables),
        "ddls": ddls,
    }
