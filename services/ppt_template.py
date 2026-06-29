"""PPT 模板存储与业务逻辑。"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.config import BASE_DIR, get_env


def _get_db_path() -> str:
    return get_env(
        "PPT_TEMPLATE_DB_PATH",
        os.path.join(BASE_DIR, "data", "ppt_templates.db"),
    )


MAX_NAME_LENGTH = 50


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ppt_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _generate_id() -> str:
    return f"tpl_{uuid.uuid4().hex[:12]}"


def _validate_name(name: str) -> Optional[str]:
    trimmed = (name or "").strip()
    if not trimmed:
        return "模板名称不能为空"
    if len(trimmed) > MAX_NAME_LENGTH:
        return f"模板名称不能超过 {MAX_NAME_LENGTH} 个字符"
    return None


def _validate_data(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return "data 必须为对象"

    title = data.get("title")
    if not title or not isinstance(title, str):
        return "data.title 不能为空"

    width = data.get("width")
    if width is None or not isinstance(width, (int, float)):
        return "data.width 必须为数字"

    theme = data.get("theme")
    if not isinstance(theme, dict):
        return "data.theme 必须为对象"

    slides = data.get("slides")
    if not isinstance(slides, list):
        return "data.slides 必须为数组"
    if len(slides) < 1:
        return "data.slides 至少需要 1 页"

    return None


def list_templates() -> dict:
    """获取模板列表（仅元信息）。"""
    conn = _get_connection()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            """
            SELECT id, name, created_at, updated_at
            FROM ppt_templates
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()

        items: List[Dict[str, str]] = []
        for row in rows:
            item: Dict[str, str] = {
                "id": row["id"],
                "name": row["name"],
                "createdAt": row["created_at"],
            }
            if row["updated_at"]:
                item["updatedAt"] = row["updated_at"]
            items.append(item)

        return {"state": 0, "list": items}
    except Exception as exc:
        return {"state": -1, "list": [], "message": str(exc)}
    finally:
        conn.close()


def save_template(name: str, data: Dict[str, Any]) -> dict:
    """保存模板。

    - template_id 为空：新建模板
    - template_id 非空：覆盖更新已有模板
    """
    return save_template_with_id(template_id=None, name=name, data=data)


def save_template_with_id(
    *,
    template_id: Optional[str],
    name: str,
    data: Dict[str, Any],
) -> dict:
    """保存或覆盖更新模板。"""
    name_error = _validate_name(name)
    if name_error:
        return {"state": -1, "message": name_error}

    data_error = _validate_data(data)
    if data_error:
        return {"state": -1, "message": data_error}

    trimmed_name = name.strip()
    now = _now_str()
    data_json = json.dumps(data, ensure_ascii=False)

    conn = _get_connection()
    try:
        _ensure_table(conn)
        if template_id is None or not str(template_id).strip():
            new_id = _generate_id()
            conn.execute(
                """
                INSERT INTO ppt_templates (id, name, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (new_id, trimmed_name, data_json, now, now),
            )
            conn.commit()
            return {"state": 0, "id": new_id}

        target_id = str(template_id).strip()
        row = conn.execute(
            "SELECT id FROM ppt_templates WHERE id = ?",
            (target_id,),
        ).fetchone()
        if row is None:
            return {"state": -1, "message": "模板不存在"}

        conn.execute(
            """
            UPDATE ppt_templates
            SET name = ?, data = ?, updated_at = ?
            WHERE id = ?
            """,
            (trimmed_name, data_json, now, target_id),
        )
        conn.commit()
        return {"state": 0, "id": target_id}
    except Exception as exc:
        return {"state": -1, "message": str(exc)}
    finally:
        conn.close()


def get_template_detail(template_id: str) -> dict:
    """获取模板详情（含完整 data）。"""
    if not (template_id or "").strip():
        return {"state": -1, "message": "模板 ID 不能为空"}

    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute(
            """
            SELECT id, name, data, created_at, updated_at
            FROM ppt_templates
            WHERE id = ?
            """,
            (template_id.strip(),),
        ).fetchone()

        if row is None:
            return {"state": -1, "message": "模板不存在"}

        payload: Dict[str, Any] = {
            "id": row["id"],
            "name": row["name"],
            "data": json.loads(row["data"]),
            "createdAt": row["created_at"],
        }
        if row["updated_at"]:
            payload["updatedAt"] = row["updated_at"]

        return {"state": 0, "data": payload}
    except json.JSONDecodeError:
        return {"state": -1, "message": "模板数据损坏，无法解析"}
    except Exception as exc:
        return {"state": -1, "message": str(exc)}
    finally:
        conn.close()


def delete_template(template_id: str) -> dict:
    """删除模板。"""
    if not (template_id or "").strip():
        return {"state": -1, "message": "模板 ID 不能为空"}

    conn = _get_connection()
    try:
        _ensure_table(conn)
        target_id = template_id.strip()
        row = conn.execute(
            "SELECT id FROM ppt_templates WHERE id = ?",
            (target_id,),
        ).fetchone()
        if row is None:
            return {"state": -1, "message": "模板不存在"}

        conn.execute("DELETE FROM ppt_templates WHERE id = ?", (target_id,))
        conn.commit()
        return {"state": 0}
    except Exception as exc:
        return {"state": -1, "message": str(exc)}
    finally:
        conn.close()
