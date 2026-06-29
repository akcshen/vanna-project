"""训练 Vanna：从 MySQL 导入 schema 和示例问答写入向量库。"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.config import BASE_DIR, get_env
from services.database import fetch_mysql_ddls
from services.vanna_service import create_vanna_instance

MYSQL_TABLE = get_env("MYSQL_TABLES", "vd_daily").split(",")[0].strip() or "vd_daily"

DOCUMENTATION = [
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

QUESTION_SQL_PAIRS = [
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


def _reset_chroma_store() -> None:
    chroma_path = get_env("CHROMA_PATH", os.path.join(BASE_DIR, "data", "chroma"))
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"已清空旧向量库: {chroma_path}")


def train() -> None:
    _reset_chroma_store()
    vn = create_vanna_instance()

    ddls = fetch_mysql_ddls()
    print(f"已从 MySQL 读取 {len(ddls)} 张表结构，当前训练表: {MYSQL_TABLE}")

    for ddl in ddls:
        vn.train(ddl=ddl)

    for doc in DOCUMENTATION:
        vn.train(documentation=doc)

    for question, sql in QUESTION_SQL_PAIRS:
        vn.train(question=question, sql=sql)

    print("Vanna 训练完成，schema 与示例问答已写入向量库。")


if __name__ == "__main__":
    train()
