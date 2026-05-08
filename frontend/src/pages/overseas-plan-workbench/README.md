# 企业出海报告生成工作台

## 页面路径

- `frontend/src/pages/OverseasPlanWorkbench.tsx`
- `frontend/src/pages/overseas-plan-workbench/OverseasPlanWorkbench.css`

## 页面能力

该页面用于企业出海报告生成，覆盖：企业选择、产品选择、目标国家选择、行业选择、报告深度（基础版 / 标准版 / 投资分析师版）、本地知识库开关、联网研究开关、允许缺失字段继续生成、生成进度、报告预览、缺失信息提示、数据来源展示、质量评分展示、人工编辑、版本切换、Word/PPT/Excel 导出和审计日志入口。

## 前端边界

- 前端只负责收集参数、展示状态、展示后端返回结果、触发导出和审计日志入口。
- 报告生成、知识库检索、联网研究、质量评分、数据来源整理、导出文件生成均应由后端 API 完成。
- 如果未传入 `onGenerate` / `onExport` 回调，组件会调用默认后端接口；不会在前端编造业务报告。

## 使用方式

在现有前端路由中挂载页面组件即可，例如：

```tsx
import OverseasPlanWorkbench from "./pages/OverseasPlanWorkbench";

export function AppRoutes() {
  return <OverseasPlanWorkbench apiBaseUrl="" />;
}
```

如需接入现有请求封装，可注入回调，并将企业库、产品库、行业、国家选项作为 props 传入。

```tsx
<OverseasPlanWorkbench
  enterprises={enterpriseOptions}
  products={productOptions}
  industries={industryOptions}
  countries={countryOptions}
  currentUserId={currentUser.id}
  onGenerate={async (payload) => {
    const response = await api.post("/api/overseas-plans/generations", {
      enterprise_id: payload.enterpriseId,
      product_ids: payload.productIds,
      selected_industry: payload.selectedIndustry,
      target_countries: payload.targetCountries,
      report_depth: payload.reportDepth,
      use_local_knowledge_base: payload.useLocalKnowledgeBase,
      use_web_research: payload.useWebResearch,
      continue_on_validation_warning: payload.continueOnValidationWarning,
    });

    return mapGenerationResponseToWorkbenchPlan(response.data);
  }}
  onSaveDraft={saveDraft}
  onExport={exportPlan}
  onOpenAuditLog={(projectId) => navigate(`/audit-logs?project_id=${projectId}`)}
/>
```

## 需要后端接口清单

| 场景 | 方法与路径 | 说明 |
| --- | --- | --- |
| 企业选择器 | `GET /api/enterprises` | 返回企业基础信息、主营产品、当前市场、出口占比、认证、产能、MOQ、成熟度评分、缺失字段。 |
| 产品多选器 | `GET /api/enterprises/{enterprise_id}/products` | 返回企业下产品选项、认证、产能、MOQ 等字段。 |
| 行业选择器 | `GET /api/industries` | 返回可选行业列表。 |
| 目标国家选择器 | `GET /api/countries` | 返回可选目标国家/地区列表。 |
| 生成报告 | `POST /api/overseas-plans/generations` | 创建并生成报告，入参包含报告深度、知识库/联网研究开关和缺失字段策略；返回项目状态、可编辑预览内容、数据来源、质量评分、国家优先级矩阵和路线图。 |
| 保存草稿 | `POST /api/overseas-plans/drafts` 或 `PUT /api/overseas-plans/{project_id}/draft` | 保存用户选择条件和已编辑内容。 |
| 更新编辑内容 | `PATCH /api/overseas-plans/{project_id}/sections` | 保存用户编辑后的分区正文，供后续导出使用。 |
| 版本记录 | `GET /api/overseas-plans/{project_id}/versions` | 返回历史版本列表，支持前端切换预览。 |
| 恢复版本 | `POST /api/overseas-plans/{project_id}/versions/{version_number}/restore` | 将历史版本恢复为当前版本。 |
| 设置最终版 | `POST /api/overseas-plans/{project_id}/versions/{version_number}/mark-final` | 标记最终导出版。 |
| 导出 Word | `POST /api/overseas-plans/{project_id}/exports/word` | 生成 Word 报告并返回下载地址或导出任务 ID。 |
| 导出 PPT | `POST /api/overseas-plans/{project_id}/exports/ppt` | 生成 PPT 报告并返回下载地址或导出任务 ID。 |
| 导出 Excel | `POST /api/overseas-plans/{project_id}/exports/excel` | 生成 Excel 行动计划表。 |
| 审计日志 | `GET /api/overseas-plans/{project_id}/audit-logs` | 展示生成、编辑、导出、版本操作等审计记录。 |

## 手动测试步骤

1. 打开挂载了 `OverseasPlanWorkbench` 的路由，确认页面整体为商务风格卡片布局。
2. 切换企业后，产品多选器应刷新为该企业产品。
3. 选择产品、目标国家、行业和报告深度；切换“启用本地知识库”“启用网络研究”“允许缺失字段继续生成”。
4. 点击“生成方案”：应出现 loading 遮罩和生成进度；请求成功后展示报告预览、数据来源、质量评分、国家矩阵和路线图。
5. 未允许缺失字段且关键字段缺失时，点击“生成方案”应弹出缺失信息提示；点击“继续生成”后才提交生成。
6. 编辑任一报告章节，点击“保存草稿”，版本记录中应新增用户编辑版本。
7. 打开版本记录，切换历史版本时编辑区应为只读；恢复历史版本后应可继续编辑。
8. 点击 Word/PPT/Excel 导出按钮，确认前端调用对应导出接口并展示成功或错误提示。
9. 点击“审计日志入口”，确认跳转或回调到项目审计日志页面。
