"""训练 Vanna：从 MySQL 导入 schema 和示例问答写入向量库（优化单表版）"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.config import BASE_DIR, get_env
from services.database import fetch_mysql_ddls
from services.vanna_service import create_vanna_instance

MYSQL_TABLE = get_env("MYSQL_TABLES", "vd_daily").split(",")[0].strip() or "vd_daily"


# =========================
# 1. 强化语义 + 约束层
# =========================
DOCUMENTATION = [
    f"{MYSQL_TABLE} 是车辆日度排放统计事实表，仅允许查询此表。",

    "【核心说明】每一条记录表示某个区域、车辆类别、排放标准在某一天的统计数据。",

    "【强约束】只能使用单表 vd_daily，不允许编造任何其他表。",

    "【唯一时间字段】stat_time（必须用于所有时间统计）",
    "禁止使用 create_time 做统计字段。",

    "【维度字段】",
    "gis_area_id：区域ID，用于区域分组统计。",
    "vehicle_category_id：车辆类别ID，用于车辆类型统计。",
    "emission_standard：排放标准，用于排放等级统计。",

    "【指标字段】",
    "online：在线车辆数（SUM统计）",
    "mileage：行驶里程（SUM统计，单位km）",
    "speed：平均速度（AVG统计）",
    "co2：二氧化碳排放（SUM统计，单位kg）",
    "nox：氮氧化物排放（SUM统计，单位kg）",
    "pm：颗粒物排放（SUM统计，单位kg）",
    "vocs：挥发性有机物排放（SUM统计，单位kg）",

    "【字段同义词】",
    "碳排放=co2，二氧化碳=co2",
    "氮氧化物=nox",
    "颗粒物=pm",
    "挥发性有机物=vocs",
    "里程=mileage",
    "速度=speed",
    "在线车辆=online",

    "【统计规则】",
    "区域统计：GROUP BY gis_area_id",
    "车辆类别统计：GROUP BY vehicle_category_id",
    "排放标准统计：GROUP BY emission_standard",

    "【时间规则】",
    "按天：DATE(stat_time)",
    "按月：DATE_FORMAT(stat_time,'%Y-%m')",
    "按季度：CONCAT(YEAR(stat_time),'-Q',QUARTER(stat_time))",
    "按年：YEAR(stat_time)",

    "【聚合规则】",
    "SUM用于：mileage / co2 / nox / pm / vocs / online",
    "AVG用于：speed",

    "【SQL约束】",
    f"只能查询 {MYSQL_TABLE}",
    "禁止使用不存在字段",
    "禁止编造表",
]


# =========================
# 2. 高覆盖 QA 数据集（核心）
# =========================
QUESTION_SQL_PAIRS = [

    # -------- 时间类 --------
    (
        "查询近30天累计行驶里程",
        f"""
        SELECT ROUND(SUM(mileage),2)
        FROM {MYSQL_TABLE}
        WHERE stat_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """.strip(),
    ),
    (
        "查询今年二氧化碳排放量",
        f"""
        SELECT ROUND(SUM(co2),2)
        FROM {MYSQL_TABLE}
        WHERE YEAR(stat_time)=YEAR(CURDATE())
        """.strip(),
    ),
    (
        "按天统计在线车辆数量",
        f"""
        SELECT DATE(stat_time) AS 日期,
               SUM(online) AS 在线车辆数
        FROM {MYSQL_TABLE}
        GROUP BY DATE(stat_time)
        ORDER BY 日期
        """.strip(),
    ),

    # -------- 月/季度 --------
    (
        "按月统计行驶里程",
        f"""
        SELECT DATE_FORMAT(stat_time,'%Y-%m') AS 月份,
               ROUND(SUM(mileage),2) AS 行驶里程
        FROM {MYSQL_TABLE}
        GROUP BY DATE_FORMAT(stat_time,'%Y-%m')
        ORDER BY 月份
        """.strip(),
    ),
    (
        "按季度统计氮氧化物排放",
        f"""
        SELECT CONCAT(YEAR(stat_time),'-Q',QUARTER(stat_time)) AS 季度,
               ROUND(SUM(nox),2) AS 氮氧化物
        FROM {MYSQL_TABLE}
        GROUP BY CONCAT(YEAR(stat_time),'-Q',QUARTER(stat_time))
        ORDER BY 季度
        """.strip(),
    ),

    # -------- 区域统计 --------
    (
        "查询各区域累计行驶里程",
        f"""
        SELECT gis_area_id,
               ROUND(SUM(mileage),2) AS 行驶里程
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY 行驶里程 DESC
        """.strip(),
    ),
    (
        "查询各区域二氧化碳排放量",
        f"""
        SELECT gis_area_id,
               ROUND(SUM(co2),2) AS 二氧化碳
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY 二氧化碳 DESC
        """.strip(),
    ),
    (
        "查询各区域平均速度",
        f"""
        SELECT gis_area_id,
               ROUND(AVG(speed),2) AS 平均速度
        FROM {MYSQL_TABLE}
        WHERE speed IS NOT NULL
        GROUP BY gis_area_id
        """.strip(),
    ),

    # -------- 排名TOP --------
    (
        "查询行驶里程最高的10个区域",
        f"""
        SELECT gis_area_id,
               SUM(mileage) AS mileage
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY mileage DESC
        LIMIT 10
        """.strip(),
    ),
    (
        "查询二氧化碳排放最高的区域",
        f"""
        SELECT gis_area_id,
               SUM(co2) AS co2
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY co2 DESC
        LIMIT 1
        """.strip(),
    ),

    # -------- 多指标 --------
    (
        "查询各区域行驶里程和碳排放",
        f"""
        SELECT gis_area_id,
               SUM(mileage) AS mileage,
               SUM(co2) AS co2
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        """.strip(),
    ),

    # -------- 模糊问法（重点提升） --------
    (
        "哪个区域污染最严重",
        f"""
        SELECT gis_area_id,
               SUM(co2) AS co2
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY co2 DESC
        """.strip(),
    ),
    (
        "哪个区域车跑得最多",
        f"""
        SELECT gis_area_id,
               SUM(mileage) AS mileage
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY mileage DESC
        """.strip(),
    ),
    (
        "哪个区域车辆最快",
        f"""
        SELECT gis_area_id,
               AVG(speed) AS speed
        FROM {MYSQL_TABLE}
        GROUP BY gis_area_id
        ORDER BY speed DESC
        """.strip(),
    ),
    (
        "排放标准分布情况",
        f"""
        SELECT emission_standard,
               COUNT(*) AS cnt
        FROM {MYSQL_TABLE}
        GROUP BY emission_standard
        """.strip(),
    ),
]


# =========================
# 3. 清理向量库
# =========================
def _reset_chroma_store() -> None:
    chroma_path = get_env("CHROMA_PATH", os.path.join(BASE_DIR, "data", "chroma"))
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"已清空旧向量库: {chroma_path}")


# =========================
# 4. 训练入口
# =========================
def train() -> None:
    _reset_chroma_store()
    vn = create_vanna_instance()

    ddls = fetch_mysql_ddls()
    print(f"已从 MySQL 读取 {len(ddls)} 张表结构，当前训练表: {MYSQL_TABLE}")

    # schema
    for ddl in ddls:
        vn.train(ddl=ddl)

    # documentation
    for doc in DOCUMENTATION:
        vn.train(documentation=doc)

    # QA
    for question, sql in QUESTION_SQL_PAIRS:
        vn.train(question=question, sql=sql)

    print("Vanna 训练完成（优化版单表模型已构建）")


if __name__ == "__main__":
    train()