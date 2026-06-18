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
    "query":"查询各区域累计行驶里程",
    "chartType":"bar",
    "needBaseline": true,
    "dataPeriod":{"start":"20251010","end":"20251019"},
    "baselinePeriod":{"start":"20251001","end":"20251009"}
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

## 项目文件说明

### 根目录

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 服务入口，定义 HTTP 路由（`chart_ai_query`、`chart_sql_query`、`database_tables` 等），加载 `.env` 与日志配置 |
| `start.sh` | 一键启动脚本：激活 `venv` 后执行 `python app.py` |
| `requirements.txt` | Python 依赖清单 |
| `.env` | 本地环境配置（API Key、数据库、日志等，不提交 Git） |
| `.env.example` | 环境变量模板，复制为 `.env` 后修改 |
| `chart-ai-query-api.md` | 自然语言图表查询接口文档（请求/响应、`needBaseline`、日期参数等） |
| `chart-sql-query-api.md` | 直接 SQL 查询接口文档 |

### `services/` 业务代码

| 文件 | 作用 |
|------|------|
| `chart_query.py` | **接口编排层**。根据 `needBaseline` 分流：为 `true` 时走合并基准 SQL；为 `false` 时走普通单期查询；统一返回 `tableMatrix` |
| `vanna_service.py` | **AI + SQL 核心**。封装 Vanna + DeepSeek：生成 SQL、校验 SELECT、执行查询；`generate_and_run_bar_sql` 负责 needBaseline 四步流程 |
| `dual_period_sql.py` | **基准合并 SQL**。将同一份基础 SQL 分别套上 `dataPeriod` / `baselinePeriod`，用 `LEFT JOIN` 拼成一条查询，产出「基准」列（详见文件顶部注释） |
| `period.py` | **日期处理**。校验 `YYYYMMDD` 格式；`apply_date_period_to_sql` 向 WHERE 注入日期；`normalize_base_sql_for_period_merge` 清理 AI 写死的日期 CASE |
| `baseline.py` | **基准列后处理**。约定列名为「基准」且固定最后一列；过滤「基准总行驶里程」等冗余列；调整 `tableMatrix` 列顺序 |
| `table_matrix.py` | **结果格式转换**。将 `DataFrame` 转为前端所需的 `tableMatrix`（二维字符串数组），并按 `chartType` 裁剪列数 |
| `database.py` | **数据库访问**。MySQL / SQLite 连接池、执行 SELECT、`SHOW CREATE TABLE` 拉取表结构供训练使用 |
| `query_log.py` | **结构化日志**。按请求阶段输出 SQL、行数、类别等；`LOG_LEVEL=DEBUG` 时可看完整 AI Prompt |

### 模块调用关系（needBaseline=true）

```
app.py
  └── chart_query.handle_chart_ai_query
        └── vanna_service.generate_and_run_bar_sql
              ├── period.normalize_base_sql_for_period_merge   # 清洗 AI SQL
              ├── dual_period_sql.build_bar_combined_sql       # d JOIN b 合并
              └── baseline.sanitize_baseline_dataframe         # 整理「基准」列
                    └── table_matrix.dataframe_to_table_matrix # 转 tableMatrix
```

### `scripts/` 脚本

| 文件 | 作用 |
|------|------|
| `train.py` | 训练 Vanna 向量库：导入表结构 DDL、字段说明、示例问答；切换业务库后需重新执行 |
| `init_db.py` | 初始化本地示例 SQLite 数据库（`data/sales.db`） |
| `list_tables.py` | 命令行查看「数据库已连接表」与「Vanna 已训练表」 |

### `data/` 运行时数据

| 路径 | 作用 |
|------|------|
| `data/chroma/` | ChromaDB 向量库，存储 schema 与训练问答，供 Vanna 检索 |
| `data/sales.db` | SQLite 示例库（`DB_TYPE=sqlite` 时使用） |

## 目录结构

```
vanna-project/
├── app.py                      # FastAPI 入口
├── start.sh                    # 启动脚本
├── chart-ai-query-api.md       # AI 查询接口文档
├── chart-sql-query-api.md      # SQL 查询接口文档
├── services/
│   ├── chart_query.py          # 接口编排
│   ├── vanna_service.py        # Vanna + DeepSeek + SQL 执行
│   ├── dual_period_sql.py      # 基准期/数据期合并 SQL
│   ├── period.py               # 日期校验与 SQL 注入
│   ├── baseline.py             # 「基准」列清洗与列序
│   ├── table_matrix.py         # tableMatrix 转换
│   ├── database.py             # 数据库连接与查询
│   └── query_log.py            # 查询日志
├── scripts/
│   ├── init_db.py              # 初始化示例 SQLite
│   ├── train.py                # 训练 Vanna 向量库
│   └── list_tables.py          # 查看已连接/已训练表
└── data/
    ├── sales.db                # 示例数据库
    └── chroma/                 # 向量库
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
| `LOG_LEVEL` | 日志等级（`DEBUG` 可看完整 AI Prompt） | `INFO` |
| `AI_LOG_ENABLED` | 是否打印 AI 查询业务日志 | `true` |
| `RELOAD` | 是否开启热重载（开发可 true，生产建议 false） | `false` |
| `DATABASE_PATH` | SQLite 路径 | `./data/sales.db` |
| `CHROMA_PATH` | 向量库路径 | `./data/chroma` |
