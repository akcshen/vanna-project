"""训练 Vanna：将数据库 schema 和示例问答写入向量库。"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

from services.database import fetch_mysql_ddls, get_db_type
from services.vanna_service import create_vanna_instance

load_dotenv(os.path.join(BASE_DIR, ".env"))

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

DOCUMENTATION = [
    "sales 表存储销售记录，amount 单位为人民币元。",
    "quarter 字段取值：Q1、Q2、Q3、Q4。",
    "month 字段取值：1月、2月、3月...12月。",
    "product_name 与 products.name 对应，常见值：产品A、产品B、产品C。",
    "查询各季度销售额时，按 quarter 分组，对 amount 求和后除以 10000 得到万元。",
    "查询月度多产品对比时，按 month 分组，对不同 product_name 的 amount 分别求和。",
]

QUESTION_SQL_PAIRS = [
    (
        "查询各季度销售额",
        "SELECT quarter AS 季度, ROUND(SUM(amount) / 10000.0, 2) AS 销售额 FROM sales GROUP BY quarter ORDER BY quarter",
    ),
    (
        "查询各月产品A和产品B的销售额",
        "SELECT month AS 月份, ROUND(SUM(CASE WHEN product_name = '产品A' THEN amount ELSE 0 END) / 10000.0, 2) AS 产品A, ROUND(SUM(CASE WHEN product_name = '产品B' THEN amount ELSE 0 END) / 10000.0, 2) AS 产品B FROM sales GROUP BY month ORDER BY month",
    ),
]


def get_ddl_statements() -> list[str]:
    if get_db_type() == "mysql":
        ddls = fetch_mysql_ddls()
        print(f"已从 MySQL 读取 {len(ddls)} 张表结构")
        return ddls
    return [item.strip() for item in SQLITE_DDL_STATEMENTS]


def train() -> None:
    vn = create_vanna_instance()
    db_type = get_db_type()

    for ddl in get_ddl_statements():
        vn.train(ddl=ddl)

    if db_type == "sqlite":
        for doc in DOCUMENTATION:
            vn.train(documentation=doc)

        for question, sql in QUESTION_SQL_PAIRS:
            vn.train(question=question, sql=sql)
    else:
        print("MySQL 模式已导入表结构。")
        print("如需提升准确率，请在 scripts/train.py 中补充 DOCUMENTATION 和 QUESTION_SQL_PAIRS。")

    print("Vanna 训练完成，schema 与示例问答已写入向量库。")


if __name__ == "__main__":
    train()
