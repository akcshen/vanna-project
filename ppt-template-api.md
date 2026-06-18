# PPT 模板管理接口文档

## 概述

前端在编辑器顶部标题栏提供 **模板选择** 与 **保存模板** 功能：

1. **保存模板**：将当前演示文稿的 JSON 数据上传到服务端持久化
2. **选择模板**：从服务端模板列表中选择一项，加载并**替换**当前全部内容（标题、幻灯片、主题、时间期等）

模板数据格式与「导出 JSON」完全一致，后端只需存储/返回该 JSON 对象，无需额外转换。

---

## 接口信息（通用）

| 项目 | 说明 |
|------|------|
| 基础地址 | `http://192.200.125.150:8080` |
| Content-Type | `application/json`（POST 请求） |
| 开发环境代理 | 前端请求 `/chart-api/tools/...`，由 Vite 代理到后端 |
| 生产环境 | 直接请求 `http://192.200.125.150:8080/tools/...` |
| 状态码约定 | 响应体 `state: 0` 表示成功，非 `0` 表示失败 |

与图表查询接口共用同一后端地址，详见 [chart-ai-query-api.md](./chart-ai-query-api.md#接口信息)。

---

## 1. 获取模板列表

### 接口信息

| 项目 | 说明 |
|------|------|
| 方法 | `GET` |
| 接口地址 | `/tools/ppt_templates` |
| 完整 URL | `http://192.200.125.150:8080/tools/ppt_templates` |
| 开发环境请求 | `GET /chart-api/tools/ppt_templates` |

### 请求参数

无 Query / Body 参数。

### 请求示例

```bash
curl -X GET http://localhost:8080/tools/ppt_templates
```

### 响应参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| list | array | 是 | 模板列表 |
| list[].id | string | 是 | 模板唯一 ID |
| list[].name | string | 是 | 模板名称（展示在下拉框中） |
| list[].createdAt | string | 否 | 创建时间，建议 ISO 8601 或 `YYYY-MM-DD HH:mm:ss` |
| list[].updatedAt | string | 否 | 更新时间 |
| message | string | 否 | 失败时的错误信息 |

### 成功响应示例

```json
{
  "state": 0,
  "list": [
    {
      "id": "tpl_001",
      "name": "Q3 经营分析汇报",
      "createdAt": "2026-06-18 10:30:00",
      "updatedAt": "2026-06-18 14:20:00"
    },
    {
      "id": "tpl_002",
      "name": "月度车险复盘模板",
      "createdAt": "2026-06-10 09:00:00"
    }
  ]
}
```

### 失败响应示例

```json
{
  "state": -1,
  "list": [],
  "message": "数据库连接失败"
}
```

---

## 2. 保存模板

### 接口信息

| 项目 | 说明 |
|------|------|
| 方法 | `POST` |
| 接口地址 | `/tools/ppt_template_save` |
| 完整 URL | `http://192.200.125.150:8080/tools/ppt_template_save` |
| 开发环境请求 | `POST /chart-api/tools/ppt_template_save` |

### 请求参数

#### Body（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 否 | 模板 ID；传入时表示**覆盖更新**已有模板，不传则新建 |
| name | string | 是 | 模板名称，前端会 trim 后提交，最长 50 字符 |
| data | object | 是 | 演示文稿 JSON，结构与「导出 JSON」一致，见下文 [data 字段结构](#data-字段结构) |

> 从模板加载后再次保存时，前端会提示用户选择「覆盖原模板」或「保存为新模板」。选择覆盖时会在请求体中附带原模板的 `id`。

### 请求示例

#### 新建模板

```bash
curl -X POST http://localhost:8080/tools/ppt_template_save \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q3 经营分析汇报",
    "data": {
      "title": "Q3 经营分析汇报",
      "width": 1000,
      "height": 562.5,
      "theme": {
        "themeColors": ["#5b9bd5", "#ed7d31"],
        "fontColor": "#333",
        "backgroundColor": "#fff"
      },
      "slides": [],
      "dataPeriod": { "start": "20251010", "end": "20251019" },
      "baselinePeriod": { "start": "20251001", "end": "20251009" }
    }
  }'
```

#### 覆盖已有模板

```bash
curl -X POST http://localhost:8080/tools/ppt_template_save \
  -H "Content-Type: application/json" \
  -d '{
    "id": "tpl_001",
    "name": "Q3 经营分析汇报",
    "data": { "...": "..." }
  }'
```

### 响应参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| id | string | 是 | 新建模板的唯一 ID，前端保存成功后会选中该模板 |
| message | string | 否 | 失败时的错误信息 |

### 成功响应示例

```json
{
  "state": 0,
  "id": "tpl_003"
}
```

### 失败响应示例

```json
{
  "state": -1,
  "message": "模板名称不能为空"
}
```

---

## 3. 获取模板详情

### 接口信息

| 项目 | 说明 |
|------|------|
| 方法 | `GET` |
| 接口地址 | `/tools/ppt_template_detail` |
| 完整 URL | `http://192.200.125.150:8080/tools/ppt_template_detail?id={id}` |
| 开发环境请求 | `GET /chart-api/tools/ppt_template_detail?id={id}` |

### 请求参数

#### Query

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 模板 ID，来自列表接口的 `list[].id` |

### 请求示例

```bash
curl -X GET "http://localhost:8080/tools/ppt_template_detail?id=tpl_001"
```

### 响应参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| data | object | 是 | 模板详情 |
| data.id | string | 是 | 模板 ID |
| data.name | string | 是 | 模板名称 |
| data.data | object | 是 | 演示文稿 JSON，结构与保存时 `data` 字段一致 |
| data.createdAt | string | 否 | 创建时间 |
| data.updatedAt | string | 否 | 更新时间 |
| message | string | 否 | 失败时的错误信息 |

### 成功响应示例

```json
{
  "state": 0,
  "data": {
    "id": "tpl_001",
    "name": "Q3 经营分析汇报",
    "createdAt": "2026-06-18 10:30:00",
    "updatedAt": "2026-06-18 14:20:00",
    "data": {
      "title": "Q3 经营分析汇报",
      "width": 1000,
      "height": 562.5,
      "theme": {
        "themeColors": ["#5b9bd5", "#ed7d31", "#a5a5a5", "#ffc000", "#4472c4", "#70ad47"],
        "fontColor": "#333",
        "fontName": "",
        "backgroundColor": "#fff"
      },
      "slides": [
        {
          "id": "slide_xxx",
          "elements": [],
          "background": { "type": "solid", "color": "#ffffff" }
        }
      ],
      "dataPeriod": {
        "start": "20251010",
        "end": "20251019"
      },
      "baselinePeriod": {
        "start": "20251001",
        "end": "20251009"
      }
    }
  }
}
```

### 失败响应示例

```json
{
  "state": -1,
  "message": "模板不存在"
}
```

---

## 4. 删除模板

### 接口信息

| 项目 | 说明 |
|------|------|
| 方法 | `POST` |
| 接口地址 | `/tools/ppt_template_delete` |
| 完整 URL | `http://192.200.125.150:8080/tools/ppt_template_delete` |
| 开发环境请求 | `POST /chart-api/tools/ppt_template_delete` |

### 请求参数

#### Body（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 要删除的模板 ID |

### 请求示例

```bash
curl -X POST http://localhost:8080/tools/ppt_template_delete \
  -H "Content-Type: application/json" \
  -d '{ "id": "tpl_001" }'
```

### 响应参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| state | number | 是 | 状态码，`0` 表示成功 |
| message | string | 否 | 失败时的错误信息 |

### 成功响应示例

```json
{
  "state": 0
}
```

### 失败响应示例

```json
{
  "state": -1,
  "message": "模板不存在"
}
```

---

## data 字段结构

`data` 与前端「导出 JSON」文件内容一致，由 `buildExportPayload` 生成。

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 演示文稿标题 |
| width | number | 是 | 画布宽度基数，默认 `1000` |
| height | number | 是 | 画布高度，`width × viewportRatio` |
| theme | object | 是 | 主题配置，类型 `SlideTheme` |
| slides | array | 是 | 幻灯片页面数组，至少 1 页；类型 `Slide[]` |
| dataPeriod | object | 否 | 时间选择期，存在时一并保存 |
| baselinePeriod | object | 否 | 基准选择期，存在时一并保存 |

### dataPeriod / baselinePeriod

| 字段 | 类型 | 说明 |
|------|------|------|
| start | string | 开始日期，格式 `YYYYMMDD` |
| end | string | 结束日期，格式 `YYYYMMDD` |

类型定义：`src/types/period.ts` → `DatePeriod`

### slides / theme 完整结构

参见项目数据文档：[DirectoryAndData.md](../doc/DirectoryAndData.md) 及类型定义 `src/types/slides.ts`。

`slides` 中可包含图表元素的 `sqlMeta`、`aiMeta` 等扩展字段，加载模板后会完整恢复，与导入 JSON 文件行为相同。

---

## 前端交互流程

### 保存模板

1. 用户点击顶部「保存模板」
2. 若当前内容来自已加载的模板，弹出对话框并提供两种方式：
   - **覆盖原模板**：请求体携带原模板 `id`，更新已有记录
   - **保存为新模板**：不传 `id`，创建新记录
3. 若当前非模板来源，直接输入名称后新建保存
4. 成功后刷新模板列表，并选中对应模板

### 加载模板

1. 页面挂载时调用 `GET /tools/ppt_templates` 填充下拉列表
2. 用户选择模板后弹出确认：「加载模板将替换当前全部内容」
3. 确认后调用 `GET /tools/ppt_template_detail?id=xxx`
4. 将 `data.data` 传入 `applyImportedProject`，等效于导入 JSON 文件

### 删除模板

1. 点击「删除模板」打开模板列表弹窗
2. 选择要删除的模板，确认后调用 `POST /tools/ppt_template_delete`
3. 成功后刷新列表；若删除的是当前已加载模板，会清空选中状态

---

## 前端调用代码

### API 封装

位置：`src/services/index.ts`

```typescript
// 获取模板列表
PPTTemplate_List()

// 获取模板详情
PPTTemplate_Detail(id: string)

// 保存模板
PPTTemplate_Save({
  name: '模板名称',
  data: { title, width, height, theme, slides, ... },
})

// 删除模板
PPTTemplate_Delete('tpl_001')
```

### 业务 Hook

位置：`src/hooks/usePPTTemplate.ts`

| 方法 | 说明 |
|------|------|
| `fetchTemplateList()` | 拉取模板列表 |
| `saveTemplate(name)` | 保存当前演示文稿为模板 |
| `loadTemplate(id)` | 加载指定模板并替换当前内容 |
| `deleteTemplate(id)` | 删除指定模板 |

### UI 入口

位置：`src/views/Editor/EditorHeader/TemplateSelector.vue`

挂载于编辑器顶部标题栏：`src/views/Editor/EditorHeader/index.vue`

### 类型定义

位置：`src/types/pptTemplate.ts`

---

## 后端处理建议

1. **存储**：将 `data` 字段以 JSON 原文存入数据库（MySQL `JSON` 列或 `TEXT`/`LONGTEXT`），避免丢失 `slides` 内嵌套结构
2. **校验**：
   - `name` 非空，建议限制长度 ≤ 50
   - `data.slides` 必须为数组且 `length > 0`
   - `data.title`、`data.width`、`data.theme` 建议做基本存在性校验
3. **列表接口**：只返回 `id`、`name`、时间等元信息，**不要**在列表中返回完整 `data`，避免响应过大
4. **详情接口**：返回完整 `data` 对象，供前端一次性加载
5. **ID 生成**：建议使用全局唯一 ID（如 UUID、雪花 ID），保存成功后通过 `id` 字段返回
6. **同名模板**：是否允许重名由业务决定；若不允许，返回 `state !== 0` 及明确 `message`
7. **鉴权**：生产环境建议增加用户/租户维度，列表与保存按权限隔离（当前前端未传鉴权头，可按需扩展）

---

## 与导入导出的关系

| 操作 | 等价行为 |
|------|----------|
| 保存模板 | 导出 JSON 的内容上传服务端 |
| 加载模板 | 导入 JSON 文件替换当前项目 |
| 导出 JSON | 菜单 → 导出 → JSON，本地下载同结构文件 |

相关代码：

- 构建 payload：`src/hooks/useExport.ts` → `buildExportPayload`
- 加载 payload：`src/hooks/useImport.ts` → `applyImportedProject`

---

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-18 | 初始版本：模板列表、保存、详情三个接口 |
| v1.1 | 2026-06-18 | 保存接口支持传入 `id` 覆盖已有模板；从模板加载后保存时前端提示覆盖或新建 |
| v1.2 | 2026-06-18 | 新增删除模板接口 `POST /tools/ppt_template_delete` |
