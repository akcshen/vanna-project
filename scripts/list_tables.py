"""查看已连接数据库中的表，以及已训练进 Vanna 的表。"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

from services.database import list_connected_tables, list_trained_tables

load_dotenv(os.path.join(BASE_DIR, ".env"))


def main() -> None:
    connected = list_connected_tables()
    trained = list_trained_tables()

    print("=== 数据库已连接表 ===")
    print(json.dumps(connected, ensure_ascii=False, indent=2))

    print("\n=== Vanna 已训练表 ===")
    print(
        json.dumps(
            {
                "tables": trained["tables"],
                "count": trained["count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
