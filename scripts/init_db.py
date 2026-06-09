"""初始化示例销售数据库，用于本地联调。"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sales.db")


def init_database(db_path: str = DB_PATH) -> str:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript(
        """
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS products;

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            quarter TEXT NOT NULL,
            month TEXT NOT NULL,
            product_name TEXT NOT NULL,
            amount REAL NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL
        );

        INSERT INTO products (name, category) VALUES
            ('产品A', '电子产品'),
            ('产品B', '电子产品'),
            ('产品C', '家居用品');

        INSERT INTO sales (quarter, month, product_name, amount) VALUES
            ('Q1', '1月', '产品A', 120000),
            ('Q1', '1月', '产品B', 80000),
            ('Q1', '2月', '产品A', 150000),
            ('Q1', '2月', '产品B', 95000),
            ('Q1', '3月', '产品A', 130000),
            ('Q1', '3月', '产品B', 110000),
            ('Q2', '4月', '产品A', 140000),
            ('Q2', '4月', '产品B', 105000),
            ('Q2', '5月', '产品A', 160000),
            ('Q2', '5月', '产品B', 120000),
            ('Q2', '6月', '产品A', 155000),
            ('Q2', '6月', '产品B', 115000),
            ('Q3', '7月', '产品A', 170000),
            ('Q3', '7月', '产品B', 125000),
            ('Q3', '8月', '产品A', 165000),
            ('Q3', '8月', '产品B', 130000),
            ('Q3', '9月', '产品A', 175000),
            ('Q3', '9月', '产品B', 128000),
            ('Q4', '10月', '产品A', 190000),
            ('Q4', '10月', '产品B', 140000),
            ('Q4', '11月', '产品A', 200000),
            ('Q4', '11月', '产品B', 150000),
            ('Q4', '12月', '产品A', 210000),
            ('Q4', '12月', '产品B', 155000);
        """
    )

    conn.commit()
    conn.close()
    return db_path


if __name__ == "__main__":
    path = init_database()
    print(f"示例数据库已创建: {path}")
