"""训练 Vanna：将数据库 schema 和示例问答写入向量库。"""

import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

from services.database import fetch_mysql_ddls, get_db_type
from services.vanna_service import _get_env, create_vanna_instance

load_dotenv(os.path.join(BASE_DIR, ".env"))

MYSQL_TABLE = _get_env("MYSQL_TABLES", "vd_daily").split(",")[0].strip() or "vd_daily"

SQLITE_DDL_STATEMENTS = [
    """
    CREATE TABLE sales (
        id INTEGER PRIMARY KEY,
        quarter TEXT NOT NULL,
        month TEXT NOT NULL,
        product_name TEXT NOT NULL,
        amount REAL NOT NULL
    );
    """,
    """
    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL
    );
    """,
]

SQLITE_DOCUMENTATION = [
    "sales 表存储销售记录，amount 单位为人民币元。",
    "quarter 字段取值：Q1、Q2、Q3、Q4。",
    "month 字段取值：1月、2月、3月...12月。",
    "product_name 与 products.name 对应，常见值：产品A、产品B、产品C。",
    "查询各季度销售额时，按 quarter 分组，对 amount 求和后除以 10000 得到万元。",
    "查询月度多产品对比时，按 month 分组，对不同 product_name 的 amount 分别求和。",
]

MYSQL_DOCUMENTATION = [
    f"{MYSQL_TABLE} 表存储车辆日度排放与运行统计数据。",
    "字段 id：数据表主键，bigint(20)，自增，非空。",
    "字段 gis_area_id：区域 ID，varchar(20)，非空。",
    "字段 vehicle_category_id：车辆类别 ID，int(10)，非空。",
    "字段 emission_standard：车辆排放标准（国标），varchar(20)，非空。",
    "字段 online：累计车辆在线数，int(10)，可为 NULL。",
    "字段 mileage：累计行驶里程，double，单位 km，可为 NULL。",
    "字段 nox：累计氮氧化物排放量，double，单位 kg，可为 NULL。",
    "字段 pm：累计颗粒物排放量，double，单位 kg，可为 NULL。",
    "字段 vocs：累计挥发性有机物排放量，double，单位 kg，可为 NULL。",
    "字段 co2：累计二氧化碳排放量，double，单位 kg，可为 NULL。",
    "字段 speed：车辆平均速度，double，可为 NULL。",
    "字段 stat_time：数据统计记录时间，datetime，非空，用于时间范围过滤和按日/月/季度统计。",
    "字段 create_time：数据创建时间，datetime，非空。",
    f"只使用 {MYSQL_TABLE} 这一张表，不要编造其他表名。",
    "时间范围过滤使用 stat_time 字段。",
    "按区域统计时使用 gis_area_id 分组，按排放标准统计时使用 emission_standard 分组，按车辆类别统计时使用 vehicle_category_id 分组。",
]

SQLITE_QUESTION_SQL_PAIRS = [
    (
        "查询各季度销售额",
        "SELECT quarter AS 季度, ROUND(SUM(amount) / 10000.0, 2) AS 销售额 FROM sales GROUP BY quarter ORDER BY quarter",
    ),
    (
        "查询各月产品A和产品B的销售额",
        "SELECT month AS 月份, ROUND(SUM(CASE WHEN product_name = '产品A' THEN amount ELSE 0 END) / 10000.0, 2) AS 产品A, ROUND(SUM(CASE WHEN product_name = '产品B' THEN amount ELSE 0 END) / 10000.0, 2) AS 产品B FROM sales GROUP BY month ORDER BY month",
    ),
]

MYSQL_QUESTION_SQL_PAIRS = [
    (
        "查询各区域累计行驶里程",
        f"""
        SELECT
            gis_area_id AS 区域,
            ROUND(SUM(mileage), 2) AS 行驶里程
        FROM {MYSQL_TABLE}
        WHERE stat_time IS NOT NULL
        GROUP BY gis_area_id
        ORDER BY 行驶里程 DESC
        """.strip(),
    ),
    (
        "查询各排放标准二氧化碳排放量",
        f"""
        SELECT
            emission_standard AS 排放标准,
            ROUND(SUM(co2), 2) AS 二氧化碳排放量
        FROM {MYSQL_TABLE}
        WHERE stat_time IS NOT NULL
        GROUP BY emission_standard
        ORDER BY 二氧化碳排放量 DESC
        """.strip(),
    ),
    (
        "查询各季度累计氮氧化物排放量",
        f"""
        SELECT
            CONCAT(YEAR(stat_time), '-Q', QUARTER(stat_time)) AS 季度,
            ROUND(SUM(nox), 2) AS 氮氧化物排放量
        FROM {MYSQL_TABLE}
        WHERE stat_time IS NOT NULL
        GROUP BY CONCAT(YEAR(stat_time), '-Q', QUARTER(stat_time))
        ORDER BY MIN(stat_time)
        """.strip(),
    ),
    (
        "查询各车辆类别平均速度",
        f"""
        SELECT
            vehicle_category_id AS 车辆类别,
            ROUND(AVG(speed), 2) AS 平均速度
        FROM {MYSQL_TABLE}
        WHERE stat_time IS NOT NULL AND speed IS NOT NULL
        GROUP BY vehicle_category_id
        ORDER BY 平均速度 DESC
        """.strip(),
    ),
]


def get_ddl_statements() -> list[str]:
    if get_db_type() == "mysql":
        ddls = fetch_mysql_ddls()
        print(f"已从 MySQL 读取 {len(ddls)} 张表结构")
        return ddls
    return [item.strip() for item in SQLITE_DDL_STATEMENTS]


def _reset_chroma_store() -> None:
    chroma_path = _get_env("CHROMA_PATH", os.path.join(BASE_DIR, "data", "chroma"))
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"已清空旧向量库: {chroma_path}")


def train() -> None:
    _reset_chroma_store()
    vn = create_vanna_instance()
    db_type = get_db_type()

    for ddl in get_ddl_statements():
        vn.train(ddl=ddl)

    if db_type == "sqlite":
        documentation = SQLITE_DOCUMENTATION
        question_sql_pairs = SQLITE_QUESTION_SQL_PAIRS
    else:
        documentation = MYSQL_DOCUMENTATION
        question_sql_pairs = MYSQL_QUESTION_SQL_PAIRS
        print(f"MySQL 模式已导入表结构，当前训练表: {MYSQL_TABLE}")

    for doc in documentation:
        vn.train(documentation=doc)

    for question, sql in question_sql_pairs:
        vn.train(question=question, sql=sql)

    print("Vanna 训练完成，schema 与示例问答已写入向量库。")


if __name__ == "__main__":
    train()
