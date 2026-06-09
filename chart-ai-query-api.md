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
| 接口地址 | `POST /tools/chart_ai_query` |
| Content-Type | `application/json` |
| 开发环境代理 | 前端请求 `/api/tools/chart_ai_query`，由 Vite 代理到后端 |
| 生产环境 | 请求 `https://server.pptist.cn/tools/chart_ai_query`（或你们自己的域名） |

---

## 请求参数

### Body（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 用户输入的自然语言，例如：`查询各季度销售额` |
| chartType | string | 是 | 当前图表类型，用于后端按类型裁剪数据 |

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
  "chartType": "bar"
}
```

---

## 响应参数

### 成功响应

HTTP Status: `200`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| sql | string | 否 | 生成的 SQL，前端会展示给用户 |
| tableMatrix | string[][] | 是 | 二维表格数据，用于填充图表编辑器 |

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
  "sql": "SELECT quarter AS 季度, ROUND(SUM(amount)/10000, 2) AS 销售额 FROM sales GROUP BY quarter",
  "tableMatrix": [
    ["", "销售额"],
    ["Q1", "26.6"],
    ["Q2", "27.9"],
    ["Q3", "28.1"],
    ["Q4", "32.1"]
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

---

## 后端处理建议

### 1. Text → SQL

- 根据你们的数据库 schema，将 `query` 转为 **SELECT** 语句
- 建议只允许 SELECT，禁止 INSERT / UPDATE / DELETE / DROP 等

### 2. 执行 SQL

- 在业务数据库执行生成的 SQL
- 查询结果至少包含：**1 列类别 + 1 列数值**（散点图需要 2 列数值）

### 3. 结果转换规则

| 查询结果列 | 映射到 tableMatrix |
|-----------|-------------------|
| 第 1 列 | 类别名 → 每行 `[row][0]` |
| 第 2 列起 | 数值系列 → 表头 `[0][col]` + 数据 `[row][col]` |

### 4. 按 chartType 裁剪（可选）

| chartType | 建议处理 |
|-----------|---------|
| pie / ring | 只保留第 1 个数值系列 |
| scatter | 至少保留 2 个数值系列，不足则补全或报错 |
| 其他 | 保留全部系列 |

---

## 前端调用代码

前端已在 `src/services/index.ts` 中封装：

```typescript
ChartAI_Query({
  query: '查询各季度销售额',
  chartType: 'bar',
})
```

调用成功后，前端读取 `res.tableMatrix` 写入图表编辑器表格。

---

## 联调 Mock 响应

后端未就绪时，可用以下 JSON 做联调：

```bash
curl -X POST http://your-backend/tools/chart_ai_query \
  -H "Content-Type: application/json" \
  -d '{"query":"查询各季度销售额","chartType":"bar"}'
```

期望返回：

```json
{
  "state": 0,
  "sql": "SELECT quarter, SUM(amount) FROM sales GROUP BY quarter",
  "tableMatrix": [
    ["", "销售额"],
    ["Q1", "26.6"],
    ["Q2", "27.9"],
    ["Q3", "28.1"],
    ["Q4", "32.1"]
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
