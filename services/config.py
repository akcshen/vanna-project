"""环境变量与路径配置。"""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()
