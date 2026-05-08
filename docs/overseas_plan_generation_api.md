# 企业出海方案生成 Agent API 说明

当前项目已在框架无关的主流程服务之上新增 FastAPI 后端入口：API 层直接调用 `OverseasPlanGenerationService.generate()` 做同步生成，也可在未来先调用 `create_generation()` 返回 `draft` 任务，再由异步队列调用 `run_generation()`。以下为 REST 契约说明。

## 1. 创建并生成方案

`POST /api/overseas-plans/generate`

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

`POST /api/overseas-plans/{project_id}/regenerate`

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

## 3. 历史版本、编辑、恢复与最终版

### 数据结构

当前项目仍采用框架无关服务和内存仓储，正文版本使用追加式 `PlanContentVersion` 保存，不覆盖历史 AI 输出。推荐落库表为 `overseas_plan_content_versions`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 版本记录 ID。 |
| `project_id` | string | 所属方案历史组 ID；重新生成项目通过 `metadata.plan_group_id` 归入同一历史组。 |
| `source_project_id` | string | 产生该内容的具体生成项目 ID。 |
| `version_number` | integer | 历史组内递增版本号。 |
| `created_by` | string | 创建人，AI 生成/重新生成取发起用户，用户编辑取编辑人。 |
| `created_at` | datetime | 版本创建时间，UTC ISO-8601。 |
| `generation_source` | enum | `AI生成` / `用户编辑` / `重新生成`。 |
| `change_summary` | string | 本次变化摘要，例如“AI生成完成”“用户编辑：正文内容调整”“恢复自历史版本 v1”。 |
| `content_json` | object | 完整方案 JSON 正文，导出和预览都从这里取数。 |
| `generation_status` | enum | 版本可用状态，默认 `completed`。 |
| `is_final` | boolean | 是否最终版；同一历史组最多一个最终版。 |
| `finalized_by` / `finalized_at` | string / datetime | 设置最终版的人和时间。 |

`GenerationProject.metadata` 新增协作字段：

| 字段 | 说明 |
| --- | --- |
| `plan_group_id` | 同一方案的历史组 ID；初次生成默认为项目 ID，重新生成沿用来源项目历史组。 |
| `current_version_number` | 当前预览/编辑版本号。 |
| `final_version_number` | 已设置的最终版版本号。 |
| `export_version_number` | 导出时实际采用的版本号，仅写入导出上下文。 |

### API 接口

#### 编辑正文

`PUT /api/overseas-plans/{project_id}/content`

请求体：

```json
{
  "edited_by": "user-1001",
  "change_summary": "补充德国渠道策略",
  "content_json": { "sections": {} }
}
```

服务方法：`OverseasPlanGenerationService.update_generated_content()`。编辑会把当前方案正文更新为用户提交内容，并追加一个 `generation_source = 用户编辑` 的新版本。历史 AI 生成结果仅追加保存，不会被覆盖。

#### 查看版本列表

`GET /api/overseas-plans/{project_id}/versions`

响应示例：

```json
{
  "project_id": "ogp_2f5e...",
  "current_version_number": 3,
  "final_version_number": 2,
  "versions": [
    {
      "version_number": 1,
      "created_by": "user-1001",
      "created_at": "2026-05-07T08:00:00+00:00",
      "generation_source": "AI生成",
      "change_summary": "AI生成完成",
      "content_json": {},
      "is_final": false
    }
  ]
}
```

服务方法：`OverseasPlanGenerationService.list_versions()`。

#### 查看单个历史版本

`GET /api/overseas-plans/{project_id}/versions/{version_number}`

服务方法：`OverseasPlanGenerationService.get_version()`。前端切换查看时使用该版本 `content_json` 进行只读预览。

#### 恢复历史版本

`POST /api/overseas-plans/{project_id}/versions/{version_number}/restore`

请求体：

```json
{ "restored_by": "user-1001" }
```

服务方法：`OverseasPlanGenerationService.restore_version()`。恢复不会删除或改写原版本，而是把历史版本正文复制为当前正文，并追加一条 `generation_source = 用户编辑`、`change_summary = 恢复自历史版本 v{version_number}` 的新版本。

#### 设置最终版

`POST /api/overseas-plans/{project_id}/finalize`

请求体：

```json
{ "version_number": 1, "finalized_by": "user-1001" }
```

服务方法：`OverseasPlanGenerationService.mark_final_version()`。同一方案历史组只保留一个最终版标记，新设置会自动取消其他版本的 `is_final`。

### 导出版本选择

Word/PPT/Excel 导出服务统一调用 `_project_for_export()` 选择正文版本：

1. 优先使用同一历史组内 `is_final = true` 且 `generation_status = completed` 的最终版；
2. 如果没有最终版，使用版本号最大的 `completed` 版本；
3. 如果历史组内暂无版本，则回退到当前 `GenerationProject.result`。

### 前端交互说明

方案预览页新增“版本记录”入口：

1. 点击“查看版本记录”展开版本面板；
2. 每条版本显示 `version_number`、生成/编辑时间、创建人、来源和变化摘要；
3. 点击“切换查看”后，预览区展示该版本内容，历史版本以只读方式展示，避免误改历史记录；
4. 点击“恢复为当前版本”调用恢复接口，后端追加恢复版本，前端刷新当前版本与版本列表；
5. 点击“设为最终版”调用最终版接口，版本列表中展示“最终版”标记；
6. 用户保存草稿/编辑内容时，前端提示“已写入版本记录”，后端保存为 `用户编辑` 版本；
7. 导出按钮无需额外选择版本，默认遵循“最终版优先，否则最新完成版”。

## 4. JSON 修复与降级响应示例

DeepSeek 首次返回非法 JSON 时，服务会自动追加一次修复提示并重试解析；如果修复后仍无法通过 JSON 合约校验，服务不会编造正文，而是启用规则引擎降级版，保留成熟度、国家、渠道和资源类型建议，并显式提示人工复核。DeepSeek API 连接、鉴权、超时等调用异常仍会进入 `failed` 状态并返回清晰 `error_reason`。

```json
{
  "project": {
    "id": "ogp_2f5e...",
    "enterprise_id": "ent-1",
    "product_ids": ["prod-1"],
    "selected_industry": "医疗器械",
    "target_countries": ["德国"],
    "generation_status": "completed",
    "generated_by": "user-1001",
    "version": 1,
    "error_reason": null,
    "metadata": {
      "execution_mode": "inline_sync",
      "json_repaired": false,
      "json_fallback_used": true,
      "json_fallback_reason": "DeepSeek JSON validation failed after one repair retry: DeepSeek returned invalid JSON"
    }
  },
  "preview": {
    "version": "fallback-v1",
    "data_quality_notes": ["DeepSeek 输出 JSON 解析/修复失败，系统已启用规则引擎降级方案。"],
    "global_manual_review_items": ["AI JSON 解析失败后生成的降级方案需人工补充/复核。"],
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
    "product_ids": ["prod-1"],
    "target_countries": ["德国"],
    "success": true,
    "error_reason": null
  }
}
```

## 5. 状态说明

| 状态 | 说明 |
| --- | --- |
| `draft` | 已创建方案版本，尚未进入生成。 |
| `generating` | 正在读取企业/产品/模板并调用规则引擎、DeepSeek。 |
| `completed` | DeepSeek JSON 校验通过，或 JSON 修复失败后已启用规则引擎降级方案；方案已保存并可预览。 |
| `failed` | DeepSeek API 调用异常、数据校验拦截或其他不可降级错误；`error_reason` 会保存失败原因，并写入审计日志。 |

## 6. 导出 Word 方案

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


## 7. 导出 Excel 行动计划/资源清单

可映射为两个业务接口：

- `POST /api/overseas-plans/{project_id}/exports/excel-action-plan`：导出“12-24个月行动计划表”。
- `POST /api/overseas-plans/{project_id}/exports/resource-list`：导出“海外资源对接清单”。

当前代码提供框架无关服务方法 `OverseasPlanGenerationService.export_excel()`，API 层只需按接口路径传入对应 `export_kind`：`action_plan` 或 `resource_list`。导出只更新出海方案项目的 `output_excel.file_path` 和独立导出审计日志，不触碰现有企业/产品 Excel 导入导出模块。

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `exported_by` | string | 是 | 发起导出的用户 ID，用于审计日志记录“谁导出”。 |
| `export_kind` | string | 是 | `action_plan` 表示 12-24个月行动计划表；`resource_list` 表示海外资源对接清单。 |
| `output_dir` | string | 否 | Excel 文件保存根目录；默认 `/tmp/agent_overseas_report/exports/excel`。 |
| `system_name` | string | 否 | 生成系统名称，默认“企业出海方案智能生成系统”。 |

### 请求示例

```json
{
  "exported_by": "user-1001",
  "export_kind": "action_plan",
  "output_dir": "/tmp/agent_overseas_report/exports/excel",
  "system_name": "企业出海方案智能生成系统"
}
```

### 成功响应示例

```json
{
  "project_id": "ogp_2f5e...",
  "plan_name": "示例医疗科技12-24个月行动计划表",
  "export_type": "Excel",
  "export_kind": "action_plan",
  "sheet_name": "12-24个月行动计划表",
  "file_path": "/tmp/agent_overseas_report/exports/excel/ogp_2f5e.../示例医疗科技12-24个月行动计划表_v1_20260507080000.xlsx",
  "exported_by": "user-1001",
  "exported_at": "2026-05-07T08:00:00Z",
  "headers": ["阶段", "时间范围", "核心目标", "关键动作", "责任方", "所需资源", "交付物", "优先级", "状态", "备注"],
  "rows": [
    {
      "阶段": "准入准备期",
      "时间范围": "1-3个月",
      "核心目标": "完成准入与渠道长名单",
      "关键动作": "认证复核；渠道筛选",
      "责任方": "海外业务部",
      "所需资源": "认证顾问；德语资料",
      "交付物": "认证清单；渠道长名单",
      "优先级": "高",
      "状态": "待启动",
      "备注": "优先德国市场"
    }
  ]
}
```

### Excel 导出结果结构

#### 12-24个月行动计划表字段

| 字段 | 来源说明 |
| --- | --- |
| 阶段 | 优先从方案 `sections.07_12_24_month_implementation_roadmap.roadmap[].stage/phase` 提取。 |
| 时间范围 | 从 `time_range/timeframe/time/period` 等字段提取。 |
| 核心目标 | 从 `core_goal/goal/target/objective` 等字段提取。 |
| 关键动作 | 从 `key_actions/actions/action/tasks` 等字段提取；数组会以中文分号合并。 |
| 责任方 | 从 `responsible_party/owner/department` 等字段提取。 |
| 所需资源 | 从 `required_resources/resources/resource_needs` 等字段提取。 |
| 交付物 | 从 `deliverables/deliverable/outputs` 等字段提取。 |
| 优先级 | 从 `priority/priority_level` 提取。 |
| 状态 | 从 `status/current_status` 提取。 |
| 备注 | 从 `notes/remark/comment` 提取。 |

#### 海外资源对接清单字段

| 字段 | 来源说明 |
| --- | --- |
| 资源类型 | 从 `resource_type/type/category/subtype` 提取。 |
| 国家/地区 | 从 `country_region/country_name/country/region/market` 提取。 |
| 资源名称 | 从 `resource_name/name/organization/institution/company` 提取；如果 AI 结果没有具体名称，固定写入 `待补充/需人工确认`，不会编造。 |
| 建议对接对象 | 从 `suggested_contact/contact/contact_name/target_contact/department` 提取。 |
| 对接目的 | 从 `purpose/matching_purpose/objective/goal` 提取。 |
| 优先级 | 从 `priority/priority_level` 提取。 |
| 所属阶段 | 从 `stage/phase/related_stage` 提取。 |
| 需要准备的材料 | 从 `materials/required_materials/preparation_materials/documents` 提取；数组会以中文分号合并。 |
| 当前状态 | 从 `current_status/status` 提取。 |
| 备注 | 从 `notes/remark/comment` 提取。 |

### 文件路径

默认保存到系统可访问路径：`/tmp/agent_overseas_report/exports/excel/{project_id}/{企业名称}{表名}_v{version}_{yyyyMMddHHmmss}.xlsx`。也可以通过 `output_dir` 指定其他可访问根目录。

### 导出审计日志

每次 Excel 导出都会写入独立导出审计日志，可通过 `InMemoryGenerationStore.list_export_audit_logs(project_id)` 查询，字段包括：

| 字段 | 说明 |
| --- | --- |
| `exported_by` | 谁导出。 |
| `exported_at` | 什么时候导出。 |
| `enterprise_id` / `enterprise_name` | 哪个企业。 |
| `project_id` / `version` / `plan_name` | 哪份方案。 |
| `export_type` | 固定为 `Excel`。 |
| `file_path` | 实际生成文件路径。 |

### 本地服务调用示例

```python
from agent_overseas_report.services import ExcelExportKind, ExcelExportRequest

result = service.export_excel(
    ExcelExportRequest(
        project_id="ogp_xxx",
        exported_by="user-1001",
        export_kind=ExcelExportKind.ACTION_PLAN,
        output_dir="/tmp/agent_overseas_report/exports/excel",
    )
)
print(result.file_path)
```

## 8. 导出 PPT 方案

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

## 8. 统一审计日志能力（后端预留）

当前项目没有独立 Web/ORM 审计模块，因此服务层复用并扩展 `InMemoryGenerationStore` 的轻量级追加式审计日志。后续接入数据库时可按相同字段落表，例如 `overseas_plan_audit_logs`。

### 审计日志数据结构

每条审计日志至少包含以下字段，且不会写入完整 AI 生成正文：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 审计日志 ID，当前以前缀 `opa_` 生成。 |
| `user_id` | string/null | 操作用户 ID；生成场景来自 `generated_by`，导出场景来自 `exported_by`。 |
| `username` | string/null | 用户名；如 API 层能拿到则传入。 |
| `action_type` | string | 操作类型，见下方动作清单。 |
| `enterprise_id` | string/null | 企业 ID；若方案不存在导致失败则可为空。 |
| `plan_id` / `project_id` | string/null | 出海方案 ID；保留 `project_id` 兼容旧调用。 |
| `product_ids` | array | 关联产品 ID 列表。 |
| `target_countries` | array | 目标国家/地区列表。 |
| `export_type` | string/null | 导出类型：`Word`、`PPT`、`Excel`；非导出动作为空。 |
| `created_at` | string | UTC ISO 时间。 |
| `ip_address` | string/null | 当前项目/API 层可提供时记录。 |
| `user_agent` | string/null | 当前项目/API 层可提供时记录。 |
| `result_status` | string | `success` 或 `failed`。 |
| `error_message` | string/null | 失败原因。 |
| `metadata` | object | 仅保存非正文元数据，例如 `export_kind`、编辑的顶层字段名、来源版本等。 |

兼容字段：`generated_by`、`generated_at`、`success`、`error_reason`、`exported_by`、`exported_at`、`enterprise_name`、`plan_name`、`file_path` 仍会填充，便于现有生成/导出调用平滑迁移。

### 已接入审计日志的动作/接口

| 动作 | `action_type` | 服务方法 / 建议 API |
| --- | --- | --- |
| 创建出海方案 | `create_plan` | `OverseasPlanGenerationService.create_generation()` / `POST /api/overseas-plans/generate` |
| 调用 AI 生成方案 | `ai_generate_plan` | `OverseasPlanGenerationService.run_generation()` / `POST /api/overseas-plans/generate` |
| 重新生成方案 | `regenerate_plan` | `OverseasPlanGenerationService.regenerate()` / `POST /api/overseas-plans/{project_id}/regenerate` |
| 查看方案详情 | `view_plan_detail` | `OverseasPlanGenerationService.view_plan_detail()` / `GET /api/overseas-plans/{project_id}` |
| 编辑 AI 生成内容 | `edit_ai_content` | `OverseasPlanGenerationService.update_generated_content()` / `PATCH /api/overseas-plans/{project_id}/generated-content` |
| 导出 Word | `export_word` | `OverseasPlanGenerationService.export_word()` / `POST /api/overseas-plans/{project_id}/exports/word` |
| 导出 PPT | `export_ppt` | `OverseasPlanGenerationService.export_ppt()` / `POST /api/overseas-plans/{project_id}/exports/ppt` |
| 导出 Excel 行动计划表 | `export_excel_action_plan` | `OverseasPlanGenerationService.export_excel(export_kind="action_plan")` / `POST /api/overseas-plans/{project_id}/exports/excel-action-plan` |
| 导出资源对接清单 | `export_resource_list` | `OverseasPlanGenerationService.export_excel(export_kind="resource_list")` / `POST /api/overseas-plans/{project_id}/exports/resource-list` |
| 归档方案 | `archive_plan` | `OverseasPlanGenerationService.archive_plan()` / `POST /api/overseas-plans/{project_id}/archive` |
| 删除方案 | `delete_plan` | `OverseasPlanGenerationService.delete_plan()` / `DELETE /api/overseas-plans/{project_id}` |

### 查询审计日志的方式

后端接口可预留为：

`GET /api/overseas-plans/audit-logs?enterprise_id=ent-1&user_id=user-1&action_type=ai_generate_plan&created_from=2026-05-07T00:00:00+00:00&created_to=2026-05-08T00:00:00+00:00`

服务层调用示例：

```python
from agent_overseas_report.services import AuditLogQuery

logs = service.list_plan_audit_logs(
    AuditLogQuery(
        enterprise_id="ent-1",
        user_id="user-1",
        action_type="ai_generate_plan",
        created_from="2026-05-07T00:00:00+00:00",
        created_to="2026-05-08T00:00:00+00:00",
    )
)
```

支持筛选条件：企业 `enterprise_id`、用户 `user_id`/`username`、动作类型 `action_type`、方案 `plan_id`、时间范围 `created_from`/`created_to`。

## 8. 生成前校验与缺失信息提醒

### 校验规则

生成服务在调用 DeepSeek 前执行 `assess_generation_readiness()`，按三类字段检查完整性：

| 分类 | 字段 |
| --- | --- |
| 企业层面 | 企业名称、所属行业、主营业务、年营收、当前市场、出口占比、工厂产能、是否已有海外客户、团队国际化能力、资金能力 |
| 产品层面 | 产品名称、产品类别、HS编码、认证情况、MOQ、交期、价格带、产能、是否适合出口、产品图片/资料附件 |
| 出海目标层面 | 目标国家、目标渠道、目标客户类型、是否计划参展、是否需要融资、是否考虑海外仓/海外工厂 |

状态判断：

1. **可生成**：企业名称、所属行业、产品名称、目标国家等基础字段存在，缺失字段较少；
2. **可生成但质量较低**：基础字段存在，但年营收、HS 编码、认证情况、价格带、目标渠道/客户类型等关键字段缺失较多；
3. **不建议生成**：企业名称、所属行业、产品名称、目标国家等基础字段缺失。后端默认不调用 DeepSeek，并返回失败状态；如果前端传入 `continue_on_validation_warning=true`，则允许继续生成。

无论是否阻断，缺失字段都会按照“企业层面 / 产品层面 / 出海目标层面”分类写入项目 `metadata.generation_readiness`，并传入 DeepSeek Prompt。Prompt 明确要求 AI 将缺失项视为数据缺口，不得编造企业事实、认证、价格、产能、客户、资源或联系方式。

### 前端提示逻辑

1. 用户点击“生成方案”后，前端先用同一套字段口径做本地校验；
2. 若状态为“可生成”，直接生成，同时在页面展示缺失字段分类提醒；
3. 若状态为“可生成但质量较低”，仍允许直接生成，但提示方案质量会降低；
4. 若状态为“不建议生成”，弹窗展示三类缺失字段，按钮包括：
   - “返回补充”：关闭弹窗，用户继续完善资料；
   - “继续生成”：提交生成请求，并携带 `continue_on_validation_warning=true`；
5. 用户选择“继续生成”后，后端会在方案结果中追加 `data_quality_review`，并在 `global_manual_review_items` 中标记“因生成前信息缺失，方案需人工补充/复核”。

### 后端返回结构示例

#### 校验通过或缺失不严重

```json
{
  "project": {
    "generation_status": "completed",
    "metadata": {
      "generation_readiness": {
        "status": "可生成",
        "status_code": "ready",
        "message": "信息基本完整，可生成企业出海方案。",
        "missing_categories": [],
        "missing_count": 0,
        "total_required_count": 26,
        "critical_missing_fields": [],
        "should_popup": false,
        "manual_review_required": false,
        "prompt_instruction": "生成前数据完整性状态：可生成……"
      }
    }
  },
  "preview": {
    "sections": {}
  }
}
```

#### 缺失严重且用户未选择继续生成

```json
{
  "project": {
    "generation_status": "failed",
    "error_reason": "缺失企业名称、所属行业、产品名称或目标国家等基础字段，不建议直接生成。",
    "metadata": {
      "generation_readiness": {
        "status": "不建议生成",
        "status_code": "not_recommended",
        "missing_categories": [
          { "category": "企业层面", "fields": ["企业名称"] },
          { "category": "产品层面", "fields": ["产品名称", "认证情况"] },
          { "category": "出海目标层面", "fields": ["目标国家"] }
        ],
        "critical_missing_fields": ["企业名称", "产品名称", "目标国家"],
        "should_popup": true,
        "manual_review_required": true
      }
    }
  },
  "preview": null,
  "audit_log": {
    "success": false,
    "error_reason": "缺失企业名称、所属行业、产品名称或目标国家等基础字段，不建议直接生成。"
  }
}
```

#### 缺失严重但用户选择继续生成

```json
{
  "project": {
    "generation_status": "completed",
    "metadata": {
      "continue_on_validation_warning": true,
      "generation_readiness": {
        "status": "不建议生成",
        "status_code": "not_recommended",
        "should_popup": true,
        "manual_review_required": true
      }
    }
  },
  "preview": {
    "sections": {},
    "data_quality_review": {
      "status": "不建议生成",
      "status_code": "not_recommended",
      "manual_review_required": true,
      "missing_categories": []
    },
    "global_manual_review_items": [
      "因生成前信息缺失，方案需人工补充/复核"
    ]
  }
}
```

## FastAPI 最小启动说明

当前项目已提供 FastAPI 后端入口，并保持生成业务逻辑仍由 `OverseasPlanGenerationService` 执行。现阶段仍不接数据库、不接前端、不接 CrewAI、不做 RAG；API 应用使用内存仓储，默认内置一组演示企业/产品数据用于本地启动验证。

### 安装依赖

```bash
pip install -r requirements-dev.txt
```

### 启动服务

```bash
uvicorn agent_overseas_report.main:app --reload
```

服务启动后可访问：

- `GET http://127.0.0.1:8000/api/health`
- `POST http://127.0.0.1:8000/api/overseas-plans/generate`
- `GET http://127.0.0.1:8000/api/overseas-plans/{project_id}`
- `GET http://127.0.0.1:8000/api/overseas-plans/{project_id}/versions`
- `POST http://127.0.0.1:8000/api/overseas-plans/{project_id}/regenerate`
- `POST http://127.0.0.1:8000/api/overseas-plans/{project_id}/finalize`

如果环境变量 `DEEPSEEK_API_KEY` 已配置，默认服务会使用现有 `DeepSeekLLMService`；如果未配置，则使用本地确定性 Demo LLM 适配器，便于 API 冒烟测试，但请求仍会进入 `OverseasPlanGenerationService` 的既有编排流程。

### 生成接口请求示例

```json
{
  "enterprise_id": "ent-1",
  "product_ids": ["prod-1"],
  "selected_industry": "医疗器械",
  "target_countries": ["德国"],
  "generated_by": "user-1",
  "extra_context": {
    "language": "zh-CN"
  }
}
```

### 设置最终版请求示例

`POST /api/overseas-plans/{project_id}/finalize`

```json
{
  "version_number": 1,
  "finalized_by": "user-1"
}
```
