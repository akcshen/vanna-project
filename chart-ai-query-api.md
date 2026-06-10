# 图表 AI 数据查询接口文档

## 概述

前端在用户编辑图表数据时，将**自然语言查询文本**发送给后端。后端负责：

1. 将自然语言转换为 SQL
2. 查询数据库
3. 将结果格式化为二维表格数据返回给前端

前端收到 `tableMatrix` 后会自动填充到图表编辑器的表格中。

---

## 接口信息

| 项目 | 说明 |
|------|------|
| 基础地址 | `http://192.200.125.150:8080` |
| 接口地址 | `POST /tools/chart_ai_query` |
| 完整 URL | `http://192.200.125.150:8080/tools/chart_ai_query` |
| Content-Type | `application/json` |
| 开发环境代理 | 前端请求 `/chart-api/tools/chart_ai_query`，由 Vite 代理到 `http://192.200.125.150:8080` |
| 生产环境 | 直接请求 `http://192.200.125.150:8080/tools/chart_ai_query` |

---

## 请求参数

### Body（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 用户输入的自然语言，例如：`查询各季度销售额` |
| chartType | string | 是 | 当前图表类型，用于后端按类型裁剪数据 |
| dataPeriod | object | 是 | 时间选择期，日期格式 `YYYYMMDD` |
| dataPeriod.start | string | 是 | 开始日期，例如：`20260601` |
| dataPeriod.end | string | 是 | 结束日期，例如：`20260609` |
| baselinePeriod | object | 是 | 基准选择期，日期格式 `YYYYMMDD` |
| baselinePeriod.start | string | 是 | 基准开始日期 |
| baselinePeriod.end | string | 是 | 基准结束日期 |

### chartType 枚举值

| 值 | 说明 |
|----|------|
| bar | 柱状图 |
| column | 条形图 |
| line | 折线图 |
| area | 面积图 |
| scatter | 散点图（至少需要 2 列数值） |
| pie | 饼图（仅使用第一列数值） |
| ring | 环形图（仅使用第一列数值） |
| radar | 雷达图 |

### 请求示例

```json
{
  "query": "查询各季度销售额",
  "chartType": "bar",
  "dataPeriod": {
    "start": "20260601",
    "end": "20260609"
  },
  "baselinePeriod": {
    "start": "20250601",
    "end": "20250609"
  }
}
```

---

## 响应参数

### 成功响应

HTTP Status: `200`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| sql | string | 否 | 图表数据 SQL，前端会展示给用户 |
| baselineSql | string | 否 | 基准数据 SQL，前端会展示给用户（可选） |
| tableMatrix | string[][] | 是 | 二维表格数据，用于填充图表编辑器 |
| baselineValues | number[] | 否 | **已废弃**，后端不再返回 |
| baselineMatrix | string[][] | 否 | **已废弃**，后端不再返回 |

### tableMatrix 格式说明

`tableMatrix` 是一个二维字符串数组，结构与 Excel 粘贴格式一致：

- **第 1 行**：表头行
  - `[0][0]` 为空字符串（左上角占位）
  - `[0][1]` 起为系列名（legends）
- **第 2 行起**：数据行
  - 第 1 列（`[row][0]`）为类别名（labels / X 轴）
  - 第 2 列起为数值（转为数字后作为 series）

#### 示例：单系列（柱状图 / 折线图 / 饼图）

```json
{
  "state": 0,
  "sql": "SELECT quarter AS 季度, ROUND(SUM(amount)/10000, 2) AS 销售额, ROUND(AVG(target_amount)/10000, 2) AS 基准 FROM sales GROUP BY quarter",
  "tableMatrix": [
    ["", "销售额", "基准"],
    ["Q1", "26.6", "24.5"],
    ["Q2", "27.9", "26.0"],
    ["Q3", "28.1", "27.2"],
    ["Q4", "32.1", "30.0"]
  ],
  "baselineSql": "SELECT quarter AS 季度, ROUND(AVG(target_amount)/10000, 2) AS 基准 FROM sales_target GROUP BY quarter"
}
```

#### 柱形图基准数据（「基准」列）

当 `chartType` 为 `bar` 时，在 `tableMatrix` 首行增加名为 **「基准」** 的系列列即可：

- 列名必须为 `基准`（与前端 `BASELINE_COLUMN_NAME` 一致）
- 每行对应一个 X 轴类别的基准值
- 保存图表时前端自动解析该列并写入 `options.baselineValues`，渲染为基准折线

```json
{
  "state": 0,
  "tableMatrix": [
    ["", "销售额", "基准"],
    ["Q1", "26.6", "24.5"],
    ["Q2", "27.9", "26.0"]
  ]
}
```

#### 示例：多系列（柱状图 / 折线图）

```json
{
  "state": 0,
  "sql": "SELECT month AS 月份, SUM(product_a) AS 产品A, SUM(product_b) AS 产品B FROM sales GROUP BY month",
  "tableMatrix": [
    ["", "产品A", "产品B"],
    ["1月", "120", "80"],
    ["2月", "150", "95"],
    ["3月", "130", "110"]
  ]
}
```

#### 示例：散点图（至少 2 列数值）

```json
{
  "state": 0,
  "tableMatrix": [
    ["", "X", "Y"],
    ["点1", "12", "7"],
    ["点2", "19", "11"],
    ["点3", "5", "13"]
  ]
}
```

### 失败响应

HTTP Status: `200`（建议与现有 PPTist 接口保持一致，用 body 里的 state 表示失败）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`-1` 表示失败 |
| message | string | 是 | 错误提示，前端会直接展示 |

```json
{
  "state": -1,
  "message": "无法理解该查询，请尝试更明确的描述"
}
```

SQL 校验或执行失败时，可能额外返回 `sql` 字段，便于前端展示问题语句：

```json
{
  "state": -1,
  "message": "SQL 执行失败: ...",
  "sql": "SELECT ..."
}
```

---

## 后端实现说明

本服务基于 Vanna + DeepSeek，接口地址 `POST /tools/chart_ai_query`。

### 1. Text → SQL

- 根据已训练的数据库 schema，将 `query` 转为 **SELECT** 语句
- 仅允许单条 SELECT，禁止 INSERT / UPDATE / DELETE / DROP 等
- 使用 `dataPeriod` 将 SQL 中的时间条件替换为 `BETWEEN` 过滤（字段由环境变量 `DATE_COLUMN` 配置）

### 2. 执行 SQL

- 复用 MySQL 长连接执行查询，断线自动重连
- 查询结果至少包含：**1 列类别 + 1 列数值**（散点图需要 2 列数值）

### 3. 结果转换规则

| 查询结果列 | 映射到 tableMatrix |
|-----------|-------------------|
| 第 1 列 | 类别名 → 每行 `[row][0]` |
| 第 2 列起 | 数值系列 → 表头 `[0][col]` + 数据 `[row][col]` |

### 4. 按 chartType 裁剪

| chartType | 处理 |
|-----------|------|
| pie / ring | 只保留第 1 个数值系列 |
| scatter | 至少保留 2 个数值系列，不足则报错 |
| 其他 | 保留全部系列 |

### 5. 柱形图基准（chartType = bar）

- 使用 `baselinePeriod` 再生成并执行一条基准 SQL
- 将基准值写入 `tableMatrix` 的 **「基准」** 列（列名固定）
- 同时返回 `baselineSql` 供前端展示，**不再返回** `baselineValues` / `baselineMatrix`

---

## 前端调用代码

前端已在 `src/services/index.ts` 中封装：

```typescript
ChartAI_Query({
  query: '查询各季度销售额',
  chartType: 'bar',
  dataPeriod: { start: '20260601', end: '20260609' },
  baselinePeriod: { start: '20250601', end: '20250609' },
})
```

调用成功后，前端读取 `res.tableMatrix` 写入图表编辑器表格；若表格包含「基准」列，保存柱形图时会自动解析为基准折线配置。

---

## 联调 Mock 响应

后端未就绪时，可用以下 JSON 做联调：

```bash
curl -X POST http://your-backend/tools/chart_ai_query \
  -H "Content-Type: application/json" \
  -d '{"query":"查询各季度销售额","chartType":"bar","dataPeriod":{"start":"20260601","end":"20260609"},"baselinePeriod":{"start":"20250601","end":"20250609"}}'
```

期望返回：

```json
{
  "state": 0,
  "sql": "SELECT quarter, SUM(amount) AS 销售额, AVG(target_amount) AS 基准 FROM sales GROUP BY quarter",
  "tableMatrix": [
    ["", "销售额", "基准"],
    ["Q1", "26.6", "24.5"],
    ["Q2", "27.9", "26.0"],
    ["Q3", "28.1", "27.2"],
    ["Q4", "32.1", "30.0"]
  ]
}
```

---

## 错误码

| state | 说明 |
|-------|------|
| 0 | 成功 |
| -1 | 失败，详见 message |

---

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 初始版本，前端仅传 query + chartType |
| v1.1 | 2026-06-09 | 增加 baselineValues / baselineSql / baselineMatrix 基准数据返回 |
| v1.2 | 2026-06-09 | 增加 dataPeriod / baselinePeriod 时间选择期与基准选择期参数 |
| v1.3 | 2026-06-09 | 柱形图基准改为 tableMatrix「基准」列，不再使用 baselineValues / baselineMatrix |
| v1.4 | 2026-06-09 | 后端实现对齐：bar 自动追加「基准」列，废弃字段不再返回 |
