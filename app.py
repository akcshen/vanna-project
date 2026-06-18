"""图表 AI 数据查询 API 服务。"""

import logging
import os
import traceback
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.chart_query import handle_chart_ai_query, handle_chart_sql_query
from services.database import list_connected_tables, list_trained_tables
from services.ppt_template import (
    delete_template,
    get_template_detail,
    list_templates,
    save_template_with_id,
)

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)
logging.getLogger("vanna.ai").setLevel(getattr(logging, log_level, logging.INFO))
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(
    title="Chart AI Query API",
    description="基于 Vanna + DeepSeek 的自然语言图表数据查询接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DatePeriodModel(BaseModel):
    start: str = Field(..., description="开始日期，格式 YYYYMMDD")
    end: str = Field(..., description="结束日期，格式 YYYYMMDD")


class ChartAIQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    chartType: str = Field(..., description="图表类型")
    dataPeriod: DatePeriodModel = Field(..., description="图表数据时间选择期")
    needBaseline: bool = Field(False, description="是否需要基准数据")
    baselinePeriod: Optional[DatePeriodModel] = Field(
        None,
        description="基准数据时间选择期，needBaseline=true 时必填",
    )


class ChartSqlQueryRequest(BaseModel):
    sql: str = Field(..., description="用户输入的 SELECT SQL")
    chartType: str = Field(..., description="图表类型")


class PPTTemplateSaveRequest(BaseModel):
    id: Optional[str] = Field(None, description="模板 ID；传入时表示覆盖更新已有模板")
    name: str = Field(..., description="模板名称，最长 50 字符")
    data: dict = Field(..., description="演示文稿 JSON，与导出 JSON 结构一致")


class PPTTemplateDeleteRequest(BaseModel):
    id: str = Field(..., description="要删除的模板 ID")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc)
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=200,
        content={
            "state": -1,
            "message": f"服务内部错误: {exc}",
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tools/database_tables")
def database_tables():
    """查看数据库已连接表，以及 Vanna 已训练表。"""
    try:
        connected = list_connected_tables()
        trained = list_trained_tables()
        return {
            "state": 0,
            "connected": connected,
            "trained": {
                "tables": trained["tables"],
                "count": trained["count"],
            },
        }
    except Exception as exc:
        return {"state": -1, "message": str(exc)}


@app.post("/tools/chart_ai_query")
def chart_ai_query(body: ChartAIQueryRequest):
    return handle_chart_ai_query(
        query=body.query,
        chart_type=body.chartType,
        need_baseline=body.needBaseline,
        data_period_raw=body.dataPeriod.model_dump(),
        baseline_period_raw=(
            body.baselinePeriod.model_dump() if body.baselinePeriod else None
        ),
    )


@app.post("/tools/chart_sql_query")
def chart_sql_query(body: ChartSqlQueryRequest):
    """用户直接输入 SQL 执行，返回 tableMatrix。"""
    return handle_chart_sql_query(
        sql=body.sql,
        chart_type=body.chartType,
    )


@app.get("/tools/ppt_templates")
def ppt_templates():
    """获取 PPT 模板列表（仅元信息）。"""
    return list_templates()


@app.post("/tools/ppt_template_save")
def ppt_template_save(body: PPTTemplateSaveRequest):
    """保存当前演示文稿为 PPT 模板。"""
    return save_template_with_id(template_id=body.id, name=body.name, data=body.data)


@app.get("/tools/ppt_template_detail")
def ppt_template_detail(id: str):
    """获取 PPT 模板详情（含完整演示文稿 JSON）。"""
    return get_template_detail(template_id=id)


@app.post("/tools/ppt_template_delete")
def ppt_template_delete(body: PPTTemplateDeleteRequest):
    """删除 PPT 模板。"""
    return delete_template(template_id=body.id)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("app:app", host=host, port=port, reload=reload)
