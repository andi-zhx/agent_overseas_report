# 企业出海方案生成 Agent API 说明

当前项目实现的是框架无关的主流程服务：API 层可直接调用 `OverseasPlanGenerationService.generate()` 做同步生成，也可先调用 `create_generation()` 返回 `draft` 任务，再由未来异步队列调用 `run_generation()`。现阶段没有引入 FastAPI/Django 路由，以下为推荐对外 REST 契约。

## 1. 创建并生成方案

`POST /api/overseas-plans/generations`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `enterprise_id` | string | 是 | 企业 ID，服务会读取企业基础信息。 |
| `product_ids` | string[] | 是 | 本次选择的企业关联产品 ID；服务会读取 HS 编码、认证、产能、MOQ、价格带等产品字段。 |
| `selected_industry` | string | 是 | 目标行业，用于匹配行业模板库和规则引擎。 |
| `target_countries` | string[] | 是 | 目标国家/地区，用于匹配国家模板、资源模板和国家推荐。 |
| `generated_by` | string | 是 | 发起人用户 ID，用于审计日志。 |
| `extra_context` | object | 否 | 额外上下文，例如方案语言、运营备注。 |

### 请求示例

```json
{
  "enterprise_id": "ent-1",
  "product_ids": ["prod-1", "prod-2"],
  "selected_industry": "医疗器械",
  "target_countries": ["德国", "美国"],
  "generated_by": "user-1001",
  "extra_context": {
    "language": "zh-CN",
    "scenario": "enterprise_detail_page"
  }
}
```

### 成功响应示例

```json
{
  "project": {
    "id": "ogp_2f5e...",
    "enterprise_id": "ent-1",
    "product_ids": ["prod-1", "prod-2"],
    "selected_industry": "医疗器械",
    "target_countries": ["德国", "美国"],
    "generation_status": "completed",
    "generated_by": "user-1001",
    "version": 1,
    "final_score": 82.5,
    "maturity_level": "全球化布局型",
    "error_reason": null,
    "metadata": {
      "execution_mode": "inline_sync",
      "json_repaired": false,
      "prompt_model": "deepseek-chat"
    }
  },
  "preview": {
    "sections": {
      "01_enterprise_diagnosis": {},
      "02_overseas_market_selection": {},
      "03_entry_mode_design": {},
      "04_overseas_resource_matching_plan": {},
      "05_exhibition_and_marketing_plan": {},
      "06_financing_and_capacity_expansion_plan": {},
      "07_12_24_month_implementation_roadmap": {}
    }
  },
  "audit_log": {
    "generated_by": "user-1001",
    "enterprise_id": "ent-1",
    "product_ids": ["prod-1", "prod-2"],
    "target_countries": ["德国", "美国"],
    "success": true,
    "error_reason": null
  }
}
```

## 2. 重新生成

`POST /api/overseas-plans/generations/{project_id}/regenerate`

重新生成会创建新版本，历史方案不会被覆盖；新版本的 `metadata.extra_context.regenerated_from_project_id` 会记录来源项目。

### 请求示例

```json
{
  "generated_by": "user-1002",
  "extra_context": {
    "reason": "更新目标国家和展会建议"
  }
}
```

## 3. 生成失败响应示例

```json
{
  "project": {
    "id": "ogp_2f5e...",
    "enterprise_id": "ent-1",
    "product_ids": ["prod-1"],
    "selected_industry": "医疗器械",
    "target_countries": ["德国"],
    "generation_status": "failed",
    "generated_by": "user-1001",
    "version": 1,
    "error_reason": "DeepSeek JSON validation failed after one repair retry: DeepSeek returned invalid JSON",
    "metadata": {
      "execution_mode": "inline_sync",
      "failed_at": "2026-05-07T00:00:00+00:00",
      "error_reason": "DeepSeek JSON validation failed after one repair retry: DeepSeek returned invalid JSON"
    }
  },
  "preview": null,
  "audit_log": {
    "generated_by": "user-1001",
    "enterprise_id": "ent-1",
    "product_ids": ["prod-1"],
    "target_countries": ["德国"],
    "success": false,
    "error_reason": "DeepSeek JSON validation failed after one repair retry: DeepSeek returned invalid JSON"
  }
}
```

## 4. 状态说明

| 状态 | 说明 |
| --- | --- |
| `draft` | 已创建方案版本，尚未进入生成。 |
| `generating` | 正在读取企业/产品/模板并调用规则引擎、DeepSeek。 |
| `completed` | DeepSeek JSON 校验通过，方案已保存并可预览。 |
| `failed` | 生成失败，`error_reason` 会保存失败原因，并写入审计日志。 |

## 5. 导出 Word 方案

`POST /api/overseas-plans/{project_id}/exports/word`

当前代码提供框架无关服务方法 `OverseasPlanGenerationService.export_word()`，API 层可直接映射为上述接口。导出不会修改 `output_excel` 字段，因此不影响现有 Excel 导出能力。

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `exported_by` | string | 是 | 发起导出的用户 ID，用于审计日志记录“谁导出”。 |
| `output_dir` | string | 否 | Word 文件保存根目录；默认 `/tmp/agent_overseas_report/exports/word`。 |
| `system_name` | string | 否 | 封面展示的生成机构/系统名称，默认“企业出海方案智能生成系统”。 |

### 请求示例

```json
{
  "exported_by": "user-1001",
  "output_dir": "/tmp/agent_overseas_report/exports/word",
  "system_name": "企业出海方案智能生成系统"
}
```

### 成功响应示例

```json
{
  "project_id": "ogp_2f5e...",
  "plan_name": "示例医疗科技企业出海解决方案",
  "export_type": "Word",
  "file_path": "/tmp/agent_overseas_report/exports/word/ogp_2f5e.../示例医疗科技企业出海解决方案_v1_20260507080000.docx",
  "exported_by": "user-1001",
  "exported_at": "2026-05-07T08:00:00Z"
}
```

### Word 文档内容

导出文档标题固定为《`{企业名称}企业出海解决方案`》，并包含封面、目录和 01-08 正文章节：

1. 企业现状诊断
2. 海外市场选择
3. 出海模式设计
4. 海外资源对接方案
5. 展会与市场推广计划
6. 投融资与扩产规划
7. 12-24个月实施路线图
8. 风险提示与下一步建议

文档使用统一标题样式、微软雅黑中文字体声明、商务蓝色标题和统一表格边框/表头底色；文件写入系统可访问路径后，项目的 `output_word.file_path` 会保存该路径。

### 导出审计日志

每次 Word 导出都会写入独立的导出审计日志，可通过 `InMemoryGenerationStore.list_export_audit_logs(project_id)` 查询，字段包括：

| 字段 | 说明 |
| --- | --- |
| `exported_by` | 谁导出。 |
| `exported_at` | 什么时候导出。 |
| `enterprise_id` / `enterprise_name` | 哪个企业。 |
| `project_id` / `version` / `plan_name` | 哪份方案。 |
| `export_type` | 固定为 `Word`。 |
| `file_path` | 实际生成文件路径。 |

### 本地服务调用示例

```python
from agent_overseas_report.services import WordExportRequest

result = service.export_word(
    WordExportRequest(
        project_id="ogp_xxx",
        exported_by="user-1001",
        output_dir="/tmp/agent_overseas_report/exports/word",
    )
)
print(result.file_path)
```

## 6. 导出 PPT 方案

`POST /api/overseas-plans/{project_id}/exports/ppt`

当前代码提供框架无关服务方法 `OverseasPlanGenerationService.export_ppt()`，API 层可直接映射为上述接口。PPT 导出只更新 `output_ppt` 字段和独立导出审计日志，不修改 `output_word`、`output_excel`，因此不会影响现有 Word/Excel 导出能力。

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `exported_by` | string | 是 | 发起导出的用户 ID，用于审计日志记录“谁导出”。 |
| `output_dir` | string | 否 | PPT 文件保存根目录；默认 `/tmp/agent_overseas_report/exports/ppt`。 |
| `system_name` | string | 否 | 封面展示的生成机构/系统名称，默认“企业出海方案智能生成系统”。 |

### 请求示例

```json
{
  "exported_by": "user-1001",
  "output_dir": "/tmp/agent_overseas_report/exports/ppt",
  "system_name": "企业出海方案智能生成系统"
}
```

### 成功响应示例

```json
{
  "project_id": "ogp_2f5e...",
  "plan_name": "示例医疗科技出海解决方案",
  "export_type": "PPT",
  "file_path": "/tmp/agent_overseas_report/exports/ppt/ogp_2f5e.../示例医疗科技出海解决方案_v1_20260507080000.pptx",
  "exported_by": "user-1001",
  "exported_at": "2026-05-07T08:00:00Z"
}
```

### PPT 内容结构

导出 PPT 标题固定为《`{企业名称}出海解决方案`》，默认生成 12 页商务咨询风格宽屏演示稿：

1. 封面：企业名称、所属行业、目标国家、生成日期。
2. 方案总览：企业当前阶段、推荐目标市场、推荐进入模式、核心资源对接方向、12-24个月目标。
3. 企业现状诊断：基础情况、产品竞争力、出海成熟度评分。
4. 产品竞争力分析：技术壁垒、成本优势、交付能力、产品差异化、品牌能力。
5. 海外市场选择逻辑：国家选择五维模型、一级/二级/长期市场。
6. 国家优先级矩阵：用统一矩阵表格表达市场潜力、进入难度、推荐国家位置。
7. 出海模式设计：经销代理、跨境电商、本地 KA、海外合资/办事处和分阶段进入路径。
8. 海外资源对接方案：渠道、技术、供应链、政府/商协会资源。
9. 展会与市场推广计划：推荐展会、推介会、采购对接会、海外获客漏斗。
10. 投融资与扩产规划：初期、中期、后期资金与产能安排。
11. 12-24个月实施路线图：1-3个月、3-6个月、6-9个月、9-12个月、12-24个月。
12. 风险提示与下一步行动：主要风险、应对动作、近期执行清单。

PPT 使用统一观点式页标题、商务蓝/浅灰配色、微软雅黑中文字体声明，并统一表格、矩阵和时间轴表格样式；文件写入系统可访问路径后，项目的 `output_ppt.file_path` 会保存该路径。

### 导出审计日志

每次 PPT 导出都会写入独立的导出审计日志，可通过 `InMemoryGenerationStore.list_export_audit_logs(project_id)` 查询，字段包括：

| 字段 | 说明 |
| --- | --- |
| `exported_by` | 谁导出。 |
| `exported_at` | 什么时候导出。 |
| `enterprise_id` / `enterprise_name` | 哪个企业。 |
| `project_id` / `version` / `plan_name` | 哪份方案。 |
| `export_type` | 固定为 `PPT`。 |
| `file_path` | 实际生成文件路径。 |

### 本地服务调用示例

```python
from agent_overseas_report.services import PPTExportRequest

result = service.export_ppt(
    PPTExportRequest(
        project_id="ogp_xxx",
        exported_by="user-1001",
        output_dir="/tmp/agent_overseas_report/exports/ppt",
    )
)
print(result.file_path)
```
