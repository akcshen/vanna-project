"""图表 AI 数据查询 API 服务。"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.chart_query import handle_chart_ai_query
from services.database import list_connected_tables, list_trained_tables

load_dotenv()

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


class ChartAIQueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    chartType: str = Field(..., description="图表类型")


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
    return handle_chart_ai_query(body.query, body.chartType)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host=host, port=port, reload=True)
