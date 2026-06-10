# Vanna + DeepSeek 图表 AI 查询服务

基于 [Vanna](https://vanna.ai/) 和云端 DeepSeek 模型，将自然语言转换为 SQL 并返回前端图表所需的 `tableMatrix` 数据。

接口规范：

- AI 自然语言查询：[chart-ai-query-api.md](./chart-ai-query-api.md)
- 直接 SQL 查询：[chart-sql-query-api.md](./chart-sql-query-api.md)

## 快速开始

### 1. 创建虚拟环境并安装依赖

```bash
cd vanna-project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 DeepSeek API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

如果使用代理或私有部署的 OpenAI 兼容接口，修改 `DEEPSEEK_BASE_URL` 即可，例如：

```env
DEEPSEEK_BASE_URL=https://your-proxy.example.com/v1
```

### 3. 配置数据库

#### 使用 MySQL（推荐生产环境）

编辑 `.env`：

```env
DB_TYPE=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your_database

# 可选：只导入指定表结构
# MYSQL_TABLES=sales,orders
```

安装 MySQL 驱动并训练（会自动从库里读取表结构）：

```bash
pip install PyMySQL
python scripts/train.py
```

#### 使用 SQLite（本地示例）

```env
DB_TYPE=sqlite
DATABASE_PATH=./data/sales.db
```

```bash
python scripts/init_db.py
python scripts/train.py
```

### 4. 启动服务

**必须先激活虚拟环境**，否则会用到系统 Python，导致依赖错误或启动极慢：

```bash
source venv/bin/activate
python app.py
```

或使用一键启动脚本（推荐）：

```bash
chmod +x start.sh
./start.sh
```

服务默认运行在 `http://localhost:8080`。

> 首次启动时 pandas / chromadb 加载可能需要几秒，属正常现象，请耐心等待。
> 首次 AI 查询可能需要 30～60 秒，请耐心等待，不要中途 Ctrl+C。
> 若 curl 出现 `Empty reply from server`，通常是服务正在热重载或进程崩溃，请重启服务并确保 `.env` 中 `RELOAD=false`。

## 查看已连接的表

### 命令行

```bash
python scripts/list_tables.py
```

会输出两部分：

- **数据库已连接表**：当前 MySQL / SQLite 里能查到的表
- **Vanna 已训练表**：`python scripts/train.py` 后写入向量库的表结构

### HTTP 接口

```bash
curl http://localhost:8080/tools/database_tables
```

返回示例：

```json
{
  "state": 0,
  "connected": {
    "dbType": "mysql",
    "database": "your_database",
    "host": "127.0.0.1",
    "port": 3306,
    "tables": ["sales", "orders"],
    "count": 2
  },
  "trained": {
    "tables": ["sales", "orders"],
    "count": 2
  }
}
```

## 直接执行 SQL

无需 AI，用户自行输入 SELECT 语句：

```bash
curl -X POST http://localhost:8080/tools/chart_sql_query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily GROUP BY gis_area_id",
    "chartType": "bar"
  }'
```

- 仅允许 SELECT
- 占位符替换由前端完成，后端执行最终 SQL
- 柱形图基准：在 SQL 中查询出列名为「基准」的列即可

详见 [chart-sql-query-api.md](./chart-sql-query-api.md)。

## 接口测试

```bash
curl -X POST http://localhost:8080/tools/chart_ai_query \
  -H "Content-Type: application/json" \
  -d '{
    "query":"查询各季度销售额",
    "chartType":"bar",
    "dataPeriod":{"start":"20250101","end":"20251231"},
    "baselinePeriod":{"start":"20240101","end":"20241231"}
  }'
```

## 前端联调

Vite 开发环境可将 `/api` 代理到本服务：

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

前端请求 `/api/tools/chart_ai_query` 即可联调。

## 目录结构

```
vanna-project/
├── app.py                  # FastAPI 入口
├── chart-ai-query-api.md   # AI 查询接口文档
├── chart-sql-query-api.md  # SQL 查询接口文档
├── services/
│   ├── chart_query.py      # 业务编排
│   ├── table_matrix.py     # 结果格式转换
│   └── vanna_service.py    # Vanna + DeepSeek 封装
├── scripts/
│   ├── init_db.py          # 初始化示例 SQLite
│   └── train.py            # 训练 schema / 示例问答
└── data/
    ├── sales.db            # 示例数据库
    └── chroma/             # 向量库
```

## 切换业务数据库

修改 `.env` 中的数据库配置后，重新执行训练脚本：

```bash
python scripts/train.py
```

MySQL 模式会自动 `SHOW CREATE TABLE` 导入表结构。为提升准确率，建议在 `scripts/train.py` 中补充：

- `DOCUMENTATION`：业务字段说明
- `QUESTION_SQL_PAIRS`：典型问答示例

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 必填 |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |
| `DEEPSEEK_BASE_URL` | 模型 API 地址（支持代理/私有部署） | `https://api.deepseek.com` |
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8080` |
| `DB_TYPE` | 数据库类型 | `sqlite` |
| `MYSQL_HOST` | MySQL 主机 | - |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户名 | - |
| `MYSQL_PASSWORD` | MySQL 密码 | - |
| `MYSQL_DATABASE` | MySQL 库名 | - |
| `MYSQL_TABLES` | 仅训练指定表 | 全部表 |
| `DATE_COLUMN` | 时间过滤字段（AI 查询 dataPeriod 注入） | `销售日期` |
| `AI_LOG_ENABLED` | 是否打印 AI 请求/返回日志 | `true` |
| `RELOAD` | 是否开启热重载（生产建议 false） | `false` |
| `DATABASE_PATH` | SQLite 路径 | `./data/sales.db` |
| `CHROMA_PATH` | 向量库路径 | `./data/chroma` |
