# 部署文档

本文档说明如何将 **Vanna + DeepSeek 图表 AI 查询服务** 部署到开发、生产及 Docker 环境。

## 目录

- [服务概述](#服务概述)
- [环境要求](#环境要求)
- [配置说明](#配置说明)
- [本地开发部署](#本地开发部署)
- [生产环境部署（Linux + systemd）](#生产环境部署linux--systemd)
- [Docker 部署](#docker-部署)
- [当前构建方式（test155）](#当前构建方式test155)
- [首次训练与数据初始化](#首次训练与数据初始化)
- [上线验证](#上线验证)
- [前端联调](#前端联调)
- [发布更新](#发布更新)
- [持久化与备份](#持久化与备份)
- [常见问题](#常见问题)

---

## 服务概述

本服务基于 FastAPI，对外提供以下能力：

| 能力 | 接口前缀 | 文档 |
|------|----------|------|
| AI 自然语言图表查询 | `POST /tools/chart_ai_query` | [chart-ai-query-api.md](./chart-ai-query-api.md) |
| SQL 直查图表数据 | `POST /tools/chart_sql_query` | [chart-sql-query-api.md](./chart-sql-query-api.md) |
| PPT 模板管理 | `GET/POST /tools/ppt_template_*` | [ppt-template-api.md](./ppt-template-api.md) |
| 健康检查 | `GET /health` | - |
| 数据库/训练表查看 | `GET /tools/database_tables` | - |

### 架构示意

```
前端
  ↓ HTTP
FastAPI (app.py, 默认 8080)
  ├── MySQL              ← 业务数据查询
  ├── data/chroma/       ← Vanna 向量库（AI 训练结果）
  └── data/ppt_templates.db ← PPT 模板（独立 SQLite）
       ↓
大模型 API（DEEPSEEK_BASE_URL）
```

生产环境默认地址示例：`http://192.200.125.150:8080`

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux（推荐）、macOS（开发） |
| Python | 3.10+ |
| 内存 | 建议 2GB+（ChromaDB + pandas 占用较高） |
| 网络 | 可访问 MySQL、大模型 API |
| 端口 | 默认 `8080`（可配置） |

### 外部依赖

- **MySQL**（生产推荐）：业务数据查询
- **大模型 API**：OpenAI 兼容接口（DeepSeek / 硅基流动等）
- **Docker**（可选）：线上容器化部署

---

## 配置说明

复制环境变量模板：

```bash
cp .env.example .env
```

### 必填项

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | 大模型 API Key |
| `DEEPSEEK_MODEL` | 模型名称 |
| `DEEPSEEK_BASE_URL` | API 地址（支持代理） |

生产使用 MySQL 时还需配置：

| 变量 | 说明 |
|------|------|
| `DB_TYPE` | 设为 `mysql` |
| `MYSQL_HOST` | MySQL 主机（容器内不要用 `127.0.0.1` 指宿主机） |
| `MYSQL_PORT` | 端口，默认 `3306` |
| `MYSQL_USER` | 用户名 |
| `MYSQL_PASSWORD` | 密码 |
| `MYSQL_DATABASE` | 库名 |
| `MYSQL_TABLES` | 训练/业务表，多个用逗号分隔 |
| `DATE_COLUMN` | 时间过滤字段，如 `stat_time` |

### 常用可选项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `8080` |
| `RELOAD` | 热重载（生产必须 `false`） | `false` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `AI_LOG_ENABLED` | 业务日志 | `true` |
| `CHROMA_PATH` | 向量库路径 | `./data/chroma` |
| `PPT_TEMPLATE_DB_PATH` | PPT 模板库路径 | `./data/ppt_templates.db` |

> `.env` 含敏感信息，**不要提交 Git**。

---

## 本地开发部署

### 1. 安装依赖

```bash
cd vanna-project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 `.env`

参考 [配置说明](#配置说明) 编辑 `.env`（含 MySQL 连接与 `MYSQL_TABLES`）。

### 3. 训练向量库

```bash
python scripts/train.py
```

### 4. 启动服务

```bash
source venv/bin/activate
./start.sh
# 或
python app.py
```

服务地址：`http://localhost:8080`

### 开发注意

- `RELOAD=true` 仅用于本地开发；长请求时可能导致 `Empty reply from server`
- 首次 AI 查询可能需 30～60 秒，属正常现象

---

## 生产环境部署（Linux + systemd）

适用于单机物理机 / 虚拟机部署。

### 1. 拉取代码

```bash
cd /opt
git clone <仓库地址> vanna-project
cd vanna-project
```

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置 `.env`

```bash
cp .env.example .env
vim .env
```

生产建议：

```env
RELOAD=false
LOG_LEVEL=INFO
DB_TYPE=mysql
```

### 4. 训练向量库

```bash
source venv/bin/activate
python scripts/train.py
```

### 5. 配置 systemd

创建 `/etc/systemd/system/vanna-api.service`：

```ini
[Unit]
Description=Vanna Chart API
After=network.target

[Service]
Type=simple
User=www
WorkingDirectory=/opt/vanna-project
EnvironmentFile=/opt/vanna-project/.env
ExecStart=/opt/vanna-project/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable vanna-api
sudo systemctl start vanna-api
sudo systemctl status vanna-api
```

查看日志：

```bash
journalctl -u vanna-api -f
```

### 6. Nginx 反代（可选）

若需通过 80/443 对外，可在 Nginx 中配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

---

## 打包上传部署（推荐）

适用于无法 `git clone`、或希望手动发包到线上的场景。

### 1. 本地打包

```bash
cd vanna-project
chmod +x scripts/pack.sh scripts/deploy.sh
./scripts/pack.sh
```

会在 `dist/` 生成压缩包，例如：

```
dist/vanna-project-20260618-153000.tar.gz
dist/vanna-project-latest.tar.gz   # 指向最新包
```

**打包会自动排除：**

- `venv/`、`.env`、`.git/`
- `data/chroma/`、`data/*.db`（运行时数据）
- `dist/`、`.codegraph/` 等

### 2. 上传到服务器

```bash
scp dist/vanna-project-latest.tar.gz nobd@test155:~/
```

### 3. 服务器解压

```bash
ssh nobd@test155
tar xzf vanna-project-latest.tar.gz
cd vanna-project
```

### 4. 配置环境变量

```bash
cp .env.example .env
vim .env
```

必填：大模型 API、MySQL 连接、`MYSQL_TABLES`、`DATE_COLUMN` 等。

### 5. 构建并启动（Docker）

```bash
chmod +x scripts/deploy.sh

# 若拉基础镜像 / pip 需要代理，仅本次终端生效：
export HTTP_PROXY=http://192.200.125.170:10808
export HTTPS_PROXY=http://192.200.125.170:10808

./scripts/deploy.sh
```

### 6. 首次训练

```bash
docker-compose exec vanna-api python scripts/train.py
```

### 7. 验证

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/tools/database_tables
```

### 更新发布

本地重新 `./scripts/pack.sh` → `scp` 上传 → 服务器解压覆盖（或解压到新目录）→ 再执行 `./scripts/deploy.sh`。

> 若 `data/` 目录已挂载持久化，更新代码不会丢失 PPT 模板和向量库。

---

## Docker 部署

适用于线上已有 Docker 的环境。项目已包含 `Dockerfile` 与 `docker-compose.yml`。

---

## 当前构建方式（test155）

> 记录时间：2026-06。test155 上 **不在服务器 build**，由本机 Windows 构建完整镜像后离线传到线上。

### 环境分工

| 机器 | Docker | 角色 |
|------|--------|------|
| 本机 Windows（Git Bash + Docker Desktop） | 29.x + Compose 5.x | **构建镜像**、`docker save` 导出 |
| test155 | 19.03.6 + docker-compose 1.18.0 | **只 load 镜像并运行**，宿主机 Python 2.7.5 不参与部署 |

### 为什么不在 test155 上 build

- test155 的 Docker `19.03.6` 过旧，无法在容器内正常执行 `apt-get`（Debian bookworm/trixie 会报 `Post-Invoke` / exit 100）。
- 因此采用 **本机构建 → 导出 tar.gz → 线上 load** 的方式。

### 镜像与产物

| 产物 | 位置 / 名称 | 说明 |
|------|-------------|------|
| 构建后的镜像 | Docker 本地镜像库 | 标签 **`vanna-api:latest`**（不在项目目录里） |
| 导出的离线包 | `dist/vanna-api-latest.tar.gz` | `docker save` 后用于 scp 到 test155 |
| 项目代码包 | `dist/vanna-project-latest.tar.gz` | `./scripts/pack.sh` 生成，含 compose / `.env.example` 等 |

查看本机镜像：

```bash
docker images vanna-api
```

### 本机构建（Windows）

前置：本机代理（Clash 等）已启动，监听 `192.200.125.170:10808`（或确保构建容器能访问该地址）。

`docker-compose.yml` 已**固定**构建代理为 `http://192.200.125.170:10808`（不会被 shell 里 `127.0.0.1:10808` 覆盖）。

```bash
cd vanna-project

# 构建（基础镜像 python:3.10-slim-bookworm，见 Dockerfile）
docker-compose build

# 导出完整应用镜像（非仅 python 基础镜像）
mkdir -p dist
docker save vanna-api:latest | gzip > dist/vanna-api-latest.tar.gz

# 打包项目文件（供 test155 上 docker-compose 使用）
./scripts/pack.sh
```

上传到 test155：

```bash
scp dist/vanna-api-latest.tar.gz dist/vanna-project-latest.tar.gz nobd@test155:~/
```

**构建要点：**

- `Dockerfile` 基础镜像：`python:3.10-slim-bookworm`（避免 `python:3.10-slim` 漂移到 trixie）。
- 构建阶段 apt/pip 走代理；镜像 build 完成后 Dockerfile 会清空 `HTTP_PROXY`，**运行时**访问大模型 API 不走代理。
- **不要把 `HTTP_PROXY` 写进 `.env`**。

### test155 部署（只运行，不 build）

```bash
# 1. 导入应用镜像（首次或镜像更新时）
gunzip -c ~/vanna-api-latest.tar.gz | docker load
docker images | grep vanna-api

# 2. 解压项目（首次或 compose / 脚本更新时）
tar xzf vanna-project-latest.tar.gz
cd vanna-project

# 3. 配置（首次）
cp .env.example .env
vim .env    # MYSQL_HOST 填内网 IP，勿用 127.0.0.1
mkdir -p data

# 4. 启动（关键：--no-build）
docker-compose up -d --no-build

# 5. 首次训练向量库
docker-compose exec vanna-api python scripts/train.py

# 6. 验证
curl http://127.0.0.1:8080/health
docker-compose logs -f vanna-api
```

### 发版更新（当前流程）

代码或依赖有变更时，在本机重新 build 并传镜像：

```bash
# 本机
docker-compose build
docker save vanna-api:latest | gzip > dist/vanna-api-latest.tar.gz
./scripts/pack.sh
scp dist/vanna-api-latest.tar.gz dist/vanna-project-latest.tar.gz nobd@test155:~/

# test155
gunzip -c ~/vanna-api-latest.tar.gz | docker load
cd vanna-project && tar xzf ~/vanna-project-latest.tar.gz -C ..   # 或解压覆盖
docker-compose down
docker-compose up -d --no-build
docker-compose exec vanna-api python scripts/train.py   # 仅表结构变更时
```

| 变更类型 | 是否需要重新 build + 传镜像 |
|----------|----------------------------|
| `requirements.txt` / `Dockerfile` | ✅ 需要 |
| `app.py`、`services/*` 等业务代码 | ✅ 当前流程需要（见下方优化说明） |
| 仅 `.env` | ❌ 改 `.env` 后 `docker-compose restart vanna-api` |

> **后续可优化**：镜像只装 Python 依赖，代码目录挂载到容器，日常发版仅 `pack.sh` + scp + `restart`，无需每次传大镜像。当前尚未启用代码挂载。

### test155 禁止 / 不推荐

- ❌ 在 test155 执行 `docker-compose build`（会 apt 失败）
- ❌ 使用宿主机 `python`（2.7.5）
- ❌ 在 `.env` 中配置 `HTTP_PROXY`

---

### 1. 拉基础镜像（按需，旧流程 / 已不推荐单独使用）

> 当前推荐直接传 **`vanna-api:latest` 完整镜像**。以下仅在使用旧版「服务器 build」流程时需要。

**方式 A：本次终端代理（不改系统配置）**

```bash
export HTTP_PROXY=http://192.200.125.170:10808
export HTTPS_PROXY=http://192.200.125.170:10808
docker pull python:3.10-slim
```

> Docker 19.03 的 `docker pull` 有时仍走守护进程；若失败，用方式 B。

**方式 B：本机打包镜像传到服务器（无需代理）**

```bash
# 在有网络的机器
docker pull python:3.10-slim
docker save python:3.10-slim -o python-3.10-slim.tar
scp python-3.10-slim.tar nobd@test155:~/

# 在 test155
docker load -i python-3.10-slim.tar
```

若 `3.10` 拉不到，改 `Dockerfile` 第一行为 `FROM python:3.9-slim`。

### 2. 配置 `.env`

```bash
cp .env.example .env
vim .env
```

注意：

- `MYSQL_HOST` 填容器可访问的 MySQL 内网 IP，**不要**写 `127.0.0.1`
- 生产环境 `RELOAD=false`
- **不要把 HTTP_PROXY 写进 `.env`**（会被 Python 应用加载，影响容器内 API 请求）
- 构建代理由 `docker-compose.yml` 固定为 `http://192.200.125.170:10808`（本机 IP + 代理端口）

### 3. 构建并启动

> **test155 请使用上文 [当前构建方式](#当前构建方式test155)**：`docker-compose up -d --no-build`。

以下命令仅适用于 **能在本地正常 build 的机器**（非 test155）：

```bash
cd vanna-project

# 使用 docker-compose v1（带横杠）
docker-compose build
docker-compose up -d
```

### 4. 首次训练

```bash
docker-compose exec vanna-api python scripts/train.py
```

### 5. 查看日志与状态

```bash
docker-compose ps
docker-compose logs -f vanna-api
```

### 6. 常用运维命令

```bash
# 重启
docker-compose restart vanna-api

# 停止
docker-compose down

# 更新发布
git pull
docker-compose build
docker-compose up -d
docker-compose exec vanna-api python scripts/train.py   # 表结构变更时
```

### Docker 注意点

| 项目 | 说明 |
|------|------|
| 命令 | test155 使用 `docker-compose`（v1），不是 `docker compose` |
| 构建位置 | **本机 Windows** build；test155 **只 load + `--no-build`** |
| 基础镜像 | `python:3.10-slim-bookworm`（Dockerfile 固定 bookworm） |
| 应用镜像 | `vanna-api:latest`，离线包 `dist/vanna-api-latest.tar.gz` |
| 代理 | 构建时 `docker-compose.yml` 固定 `http://192.200.125.170:10808`；运行时镜像内无代理 |
| 数据卷 | 必须挂载 `./data:/app/data`，否则模板和向量库在重建容器后丢失 |
| 单实例 | `ppt_templates.db` 为本地 SQLite，暂不支持多副本共享 |
| 训练时机 | 首次部署或表结构变更后执行 `train.py`，不必每次启动都跑 |
| 资源 | 建议 2GB+ 内存；网关超时建议 ≥ 120s（AI 查询较慢） |

### Dockerfile / compose 文件说明

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 基于 `python:3.10-slim-bookworm`；构建参数 `HTTP_PROXY`/`HTTPS_PROXY`；运行时清空代理 |
| `docker-compose.yml` | `version: "3"`，兼容 docker-compose 1.18 |
| `.dockerignore` | 排除 `venv/`、`.env`、`data/` 等，减小构建上下文 |

---

## 首次训练与数据初始化

### 训练向量库（必做）

AI 查询依赖 Vanna 向量库，部署后需执行：

```bash
python scripts/train.py
```

Docker 环境：

```bash
docker compose exec vanna-api python scripts/train.py
```

**需要重新训练的情况：**

- 首次部署
- 修改 `MYSQL_TABLES`
- 业务表结构变更
- 清空或丢失 `data/chroma/`

### 查看训练结果

```bash
python scripts/list_tables.py
```

或：

```bash
curl http://localhost:8080/tools/database_tables
```

返回中 `connected` 为数据库可访问表，`trained` 为已写入向量库的表。

### 提升 AI 准确率（可选）

编辑 `scripts/train.py`，补充：

- `MYSQL_DOCUMENTATION`：字段说明、表关系
- `MYSQL_QUESTION_SQL_PAIRS`：典型问答示例

修改后重新执行 `python scripts/train.py`。

---

## 上线验证

### 健康检查

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### 数据库连通

```bash
curl http://localhost:8080/tools/database_tables
```

### PPT 模板

```bash
curl http://localhost:8080/tools/ppt_templates
```

### AI 查询

```bash
curl -X POST http://localhost:8080/tools/chart_ai_query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "查询各区域累计行驶里程",
    "chartType": "bar",
    "needBaseline": false,
    "dataPeriod": {"start": "20251010", "end": "20251019"}
  }'
```

### SQL 直查

```bash
curl -X POST http://localhost:8080/tools/chart_sql_query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily_202510 WHERE stat_time >= '\''20251010'\'' AND stat_time <= '\''20251019'\'' GROUP BY gis_area_id LIMIT 10",
    "chartType": "bar"
  }'
```

> 将表名、字段名替换为实际业务库中的名称。

---

## 前端联调

### 开发环境

前端通过 Vite 代理访问后端：

```
/chart-api/tools/...  →  http://localhost:8080/tools/...
```

### 生产环境

前端直接请求：

```
http://192.200.125.150:8080/tools/...
```

### 接口文档

- [chart-ai-query-api.md](./chart-ai-query-api.md)
- [chart-sql-query-api.md](./chart-sql-query-api.md)
- [ppt-template-api.md](./ppt-template-api.md)

---

## 发布更新

### 裸机 / systemd

```bash
cd /opt/vanna-project
git pull
source venv/bin/activate
pip install -r requirements.txt    # 依赖有变更时
python scripts/train.py            # 表结构有变更时
sudo systemctl restart vanna-api
```

### Docker

```bash
git pull
docker-compose build
docker-compose up -d
docker-compose exec vanna-api python scripts/train.py   # 表结构有变更时
```

### 发布检查清单

- [ ] `.env` 已更新且 `RELOAD=false`
- [ ] MySQL / 大模型 API 网络可达
- [ ] `data/` 目录已持久化
- [ ] 表结构变更后已重新 `train.py`
- [ ] `/health`、`/tools/database_tables` 验证通过
- [ ] 前端联调 AI 查询、SQL 查询、PPT 模板接口

---

## 持久化与备份

| 路径 | 内容 | 是否必须备份 |
|------|------|--------------|
| `data/chroma/` | Vanna 向量库 | 建议备份；丢失后可 `train.py` 重建 |
| `data/ppt_templates.db` | PPT 模板 | **必须备份** |
| `.env` | 环境配置 | 必须备份（不进 Git） |
| MySQL | 业务数据 | 按 DBA 策略备份 |

`.gitignore` 已忽略 `data/*.db` 和 `data/chroma/`，这些运行时数据不应提交仓库。

---

## 常见问题

### 1. curl 返回 `Empty reply from server`

- 检查 `RELOAD` 是否为 `false`
- 查看服务是否崩溃：`journalctl -u vanna-api` 或 `docker compose logs`
- 首次启动加载 chromadb 较慢，等待数秒后重试

### 2. AI 查询很慢或超时

- 首次查询需加载模型与向量库，可能 30～60 秒
- 调大 Nginx / 网关 `proxy_read_timeout`
- 检查大模型 API 网络与 Key 是否有效

### 3. `仅允许执行 SELECT 查询`

SQL 直查仅支持 `SELECT`，禁止 `INSERT/UPDATE/DELETE/DROP` 等。

### 4. Docker 内连不上 MySQL

- `MYSQL_HOST` 不要用 `127.0.0.1`（指向容器自身）
- 使用 MySQL 真实内网 IP 或 Docker 网络中的服务名
- 确认防火墙放行 3306

### 5. PPT 模板保存后重启丢失

- 确认 `data/` 已挂载持久卷
- 检查 `PPT_TEMPLATE_DB_PATH` 是否指向挂载目录

### 6. 多表 SQL 是否支持

- **SQL 直查**：支持 `JOIN`、子查询等多表 `SELECT`
- **AI 查询**：需在 `MYSQL_TABLES` 和 `train.py` 中配置相关表结构及示例

### 7. 如何切换业务库

1. 修改 `.env` 中 MySQL 配置
2. 执行 `python scripts/train.py`
3. 重启服务

### 8. 容器反复重启，`OpenBLAS pthread_create failed`

- **原因**：test155 上 Docker 19.03 的 seccomp 限制，numpy/pandas 默认多线程会报 `Operation not permitted`。
- **处理**（test155 需两项同时配置）：
  1. `OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1` 等环境变量
  2. `security_opt: ["seccomp:unconfined"]`（Docker 19.03 常见必需）

更新 `docker-compose.yml` 后 **无需 rebuild 镜像**：

```bash
grep -E 'OPENBLAS|seccomp' docker-compose.yml   # 确认已包含
docker-compose down
docker-compose up -d --no-build
docker-compose logs --tail=30 vanna-api
docker-compose exec vanna-api python scripts/train.py
```

- 快速验证（不启动服务）：

```bash
docker run --rm --security-opt seccomp=unconfined \
  -e OPENBLAS_NUM_THREADS=1 vanna-api:latest \
  python -c "import pandas; print('ok')"
```

---

## 相关文档

- [README.md](./README.md) — 项目介绍与快速开始
- [chart-ai-query-api.md](./chart-ai-query-api.md) — AI 查询接口
- [chart-sql-query-api.md](./chart-sql-query-api.md) — SQL 直查接口
- [ppt-template-api.md](./ppt-template-api.md) — PPT 模板接口
