# 图表 SQL 数据查询接口文档

## 概述

前端在图表数据编辑器中，允许用户**直接输入 SQL 语句**查询数据库。后端执行 SQL 后将结果格式化为 `tableMatrix` 返回，前端自动填充到图表编辑表格中。

与 [chart-ai-query-api.md](./chart-ai-query-api.md) 的区别：

| 对比项 | AI 查询 | SQL 查询 |
|--------|---------|----------|
| 接口 | `/tools/chart_ai_query` | `/tools/chart_sql_query` |
| 输入 | 自然语言 + 时间期 | SQL 语句 |
| 是否需要时间选择期 | 是 | 使用占位符时必填 |

---

## 接口信息

| 项目 | 说明 |
|------|------|
| 基础地址 | `http://192.200.125.150:8080` |
| 接口地址 | `POST /tools/chart_sql_query` |
| 完整 URL | `http://192.200.125.150:8080/tools/chart_sql_query` |
| Content-Type | `application/json` |
| 开发环境代理 | 前端请求 `/chart-api/tools/chart_sql_query`，由 Vite 代理到后端 |
| 生产环境 | 直接请求 `http://192.200.125.150:8080/tools/chart_sql_query` |

---

## 请求参数

### Body（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql | string | 是 | SELECT 语句 |
| chartType | string | 是 | 当前图表类型 |

### chartType 枚举值

| 值 | 说明 |
|----|------|
| bar | 柱状图 |
| column | 条形图 |
| line | 折线图 |
| area | 面积图 |
| scatter | 散点图 |
| pie | 饼图 |
| ring | 环形图 |
| radar | 雷达图 |

### 请求示例

```bash
curl -X POST http://localhost:8080/tools/chart_sql_query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily GROUP BY gis_area_id",
    "chartType": "bar"
  }'
```

```json
{
  "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily GROUP BY gis_area_id",
  "chartType": "bar"
}
```

---

## 响应参数

响应结构与 AI 查询接口一致，详见 [chart-ai-query-api.md](./chart-ai-query-api.md#响应参数)。

### 成功响应示例

```json
{
  "state": 0,
  "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily GROUP BY gis_area_id",
  "tableMatrix": [
    ["", "行驶里程"],
    ["区域A", "1234.56"],
    ["区域B", "987.65"]
  ]
}
```

### 失败响应

```json
{
  "state": -1,
  "message": "SQL 执行失败：表不存在"
}
```

---

## SQL 占位符替换规则

提交前前端会按以下规则替换 SQL 中的占位符（配置来自页面顶部）。占位符写法为 **`{KEY}`**（外层带花括号）：

| 占位符 | 替换为 | 来源 | 格式 |
|--------|--------|------|------|
| `{MYSQL_TABLE}` | MySQL 表名 | 环境变量 `VITE_MYSQL_TABLE` | 字符串 |
| `{ANALYSIS_START}` | 分析开始时间 | 时间选择期开始 | `YYYYMMDD` |
| `{ANALYSIS_END}` | 分析结束时间 | 时间选择期结束 | `YYYYMMDD` |
| `{BASELINE_START}` | 基准开始时间 | 基准选择期开始 | `YYYYMMDD` |
| `{BASELINE_END}` | 基准结束时间 | 基准选择期结束 | `YYYYMMDD` |

### 示例

顶部配置：

- 环境变量 `VITE_MYSQL_TABLE=vd_daily`（项目根目录 `.env` 或 `.env.local`）
- 时间选择期：`20260601` ~ `20260609`
- 基准选择期：`20250501` ~ `20250509`

输入 SQL：

```sql
SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程
FROM {MYSQL_TABLE}
WHERE stat_date >= '{ANALYSIS_START}' AND stat_date <= '{ANALYSIS_END}'
GROUP BY gis_area_id
```

实际请求（替换 + 压缩单行后）：

```json
{
  "sql": "SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily WHERE stat_date >= '20260601' AND stat_date <= '20260609' GROUP BY gis_area_id",
  "chartType": "bar"
}
```

实现位置：

- 规则定义：`src/configs/sqlReplaceRules.ts`
- 替换逻辑：`src/utils/sqlReplaceRules.ts`
- 表名配置：`src/configs/env.ts` → `VITE_MYSQL_TABLE`

---

## 后端实现说明

本服务接口地址 `POST /tools/chart_sql_query`，仅接收 `sql` + `chartType` 两个字段。

1. **占位符替换由前端完成**，后端收到的 `sql` 已是替换后的最终语句
2. 仅允许 **SELECT** 语句，禁止 INSERT / UPDATE / DELETE / DROP 等
3. 复用 MySQL 长连接执行，断线自动重连，适合前端批量连续请求
4. 查询结果至少包含：**1 列类别 + 1 列数值**（散点图需要 2 列数值）
5. 结果转换为 `tableMatrix`（与 AI 查询相同）：
   - 第 1 行：`["", 系列名1, 系列名2, ...]`
   - 后续行：`[类别名, 数值1, 数值2, ...]`
6. 柱形图基准线：在 SQL 中直接查询出名为 **「基准」** 的列即可，后端原样映射到 `tableMatrix`，例如：

```sql
SELECT gis_area_id AS 区域,
       ROUND(SUM(mileage), 2) AS 行驶里程,
       ROUND(AVG(target_mileage), 2) AS 基准
FROM vd_daily
WHERE stat_time >= '20260601' AND stat_time <= '20260609'
GROUP BY gis_area_id
```

### 失败响应补充

SQL 校验或执行失败时，可能额外返回 `sql` 字段：

```json
{
  "state": -1,
  "message": "SQL 执行失败: ...",
  "sql": "SELECT ..."
}
```

---

## 前端调用代码

封装位置：`src/services/index.ts`

```typescript
ChartSQL_Query({
  sql: 'SELECT gis_area_id AS 区域, ROUND(SUM(mileage), 2) AS 行驶里程 FROM vd_daily GROUP BY gis_area_id',
  chartType: 'bar',
})
```

UI 入口：`src/components/ChartDataEditor.vue` → 「SQL 数据查询」面板 → 「SQL 查询」按钮。

提交前前端会自动处理 SQL（**不会修改输入框内容**）：

- 输入框：保持你编写的原始 SQL（含 `{KEY}` 占位符）
- 实际请求：内部替换占位符 → 压缩单行后发送
- 「实际执行 SQL」：展示发给后端的最终语句

提交前处理：`src/utils/formatSql.ts`（`compactSql`）、`src/utils/sqlReplaceRules.ts`（`applySqlReplaceRules`）

---

## SQL 保存与导入导出

SQL 作为**图表元素属性**保存，写入 `PPTChartElement.sqlMeta`，与图表数据一起持久化。

### 保存时机

1. SQL 查询成功 → 编辑器内关联 SQL（提示「点击确认后随图表一起保存」）
2. 点击「确认」→ 将 `sqlMeta` 写入当前图表元素

### sqlMeta 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| rawSql | string | 输入框原始 SQL（含占位符） |
| executedSql | string | 实际发给后端的 SQL |
| updatedAt | number | 更新时间戳 |

类型定义：`src/types/slides.ts` → `ChartSqlMeta`

### 导入导出

通过 PPT 自带的 **导出 JSON / .pptist** 即可携带 SQL，无需单独导出 SQL 文件。重新打开图表数据编辑器时会自动恢复 SQL 输入框内容。

示例（图表元素片段）：

```json
{
  "type": "chart",
  "chartType": "bar",
  "data": { "labels": [], "legends": [], "series": [] },
  "sqlMeta": {
    "rawSql": "SELECT ... FROM {MYSQL_TABLE} WHERE stat_date >= '{ANALYSIS_START}' ...",
    "executedSql": "SELECT ... FROM vd_daily WHERE stat_date >= '20240101' ...",
    "updatedAt": 1717891200000
  }
}
```

相关代码：

- 类型：`src/types/slides.ts`（`ChartSqlMeta`、`PPTChartElement.sqlMeta`）
- 保存逻辑：`src/components/ChartDataEditor.vue`、`src/views/Editor/ChartDataEditorDialog.vue`

---

## 时间期变更后批量刷新

顶部修改「时间选择期 / 基准选择期」后：

- **更新时间**：更新全部幻灯片右下角的数据期 / 基准期标注
- **更新图表**：遍历全部幻灯片中带有 `sqlMeta.rawSql` 的图表，用新时间期重新查询并刷新数据

相关代码：

- 工具：`src/utils/chartSqlQuery.ts`（`buildExecutedSql`、`refreshChartBySqlMeta`）
- Hook：`src/hooks/useRefreshChartsByPeriod.ts`
- 入口：`src/views/Editor/PeriodBar/index.vue` → `handleUpdateTime` / `handleUpdateCharts`

仅 SQL 查询保存过的图表会被刷新；AI 查询图表需单独扩展。

---

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 初始版本，支持直接 SQL 查询图表数据 |
| v1.1 | 2026-06-09 | 增加 SQL 占位符替换（表名、分析/基准时间） |
| v1.2 | 2026-06-09 | 提交前 SQL 格式化 |
| v1.3 | 2026-06-09 | SQL 作为图表元素属性保存，随 PPT 导入导出 |
| v1.4 | 2026-06-09 | 顶部确认时间期后批量刷新 SQL 图表 |
| v1.5 | 2026-06-09 | 后端实现对齐：仅 sql + chartType，基准通过 SQL 结果列「基准」返回 |
