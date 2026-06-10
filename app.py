"""图表 AI 数据查询 API 服务。"""

import logging
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.chart_query import handle_chart_ai_query, handle_chart_sql_query
from services.database import list_connected_tables, list_trained_tables

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("vanna.ai").setLevel(getattr(logging, log_level, logging.INFO))

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
    baselinePeriod: DatePeriodModel = Field(..., description="基准数据时间选择期")


class ChartSqlQueryRequest(BaseModel):
    sql: str = Field(..., description="用户输入的 SELECT SQL")
    chartType: str = Field(..., description="图表类型")


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
        data_period_raw=body.dataPeriod.model_dump(),
        baseline_period_raw=body.baselinePeriod.model_dump(),
    )


@app.post("/tools/chart_sql_query")
def chart_sql_query(body: ChartSqlQueryRequest):
    """用户直接输入 SQL 执行，返回 tableMatrix。"""
    return handle_chart_sql_query(
        sql=body.sql,
        chart_type=body.chartType,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("app:app", host=host, port=port, reload=reload)
