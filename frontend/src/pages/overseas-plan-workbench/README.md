# 企业出海方案生成工作台

## 新增页面路径

- `frontend/src/pages/OverseasPlanWorkbench.tsx`

## 新增组件与样式路径

- 页面组件：`frontend/src/pages/OverseasPlanWorkbench.tsx`
- 页面样式：`frontend/src/pages/overseas-plan-workbench/OverseasPlanWorkbench.css`

## 使用方式

在现有前端路由中挂载页面组件即可，例如：

```tsx
import OverseasPlanWorkbench from "./pages/OverseasPlanWorkbench";

export function AppRoutes() {
  return <OverseasPlanWorkbench />;
}
```

如需接入真实后端，可注入 `onGenerate`、`onSaveDraft`、`onExport` 回调，并将企业库、产品库、行业、国家选项作为 props 传入。组件只读取传入数据，不会修改现有企业库和产品库页面。

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
      generated_by: currentUser.id,
    });

    return mapGenerationResponseToWorkbenchPlan(response.data);
  }}
  onSaveDraft={saveDraft}
  onExport={exportPlan}
/>
```

## 需要后端接口清单

| 场景 | 方法与路径 | 说明 |
| --- | --- | --- |
| 企业选择器 | `GET /api/enterprises` | 返回企业基础信息、主营产品、当前市场、出口占比、认证、产能、MOQ、成熟度评分、缺失字段。 |
| 产品多选器 | `GET /api/enterprises/{enterprise_id}/products` | 返回企业下产品选项、认证、产能、MOQ 等字段。 |
| 行业选择器 | `GET /api/industries` | 返回可选行业列表。 |
| 目标国家选择器 | `GET /api/countries` | 返回可选目标国家/地区列表。 |
| 生成方案 | `POST /api/overseas-plans/generations` | 创建并生成方案，返回项目状态、可编辑预览内容、国家优先级矩阵和路线图。 |
| 保存草稿 | `POST /api/overseas-plans/drafts` 或 `PUT /api/overseas-plans/{project_id}/draft` | 保存用户选择条件和已编辑内容。 |
| 更新编辑内容 | `PATCH /api/overseas-plans/{project_id}/sections` | 保存用户编辑后的分区正文，供后续导出使用。 |
| 导出 Word | `POST /api/overseas-plans/{project_id}/exports/word` | 生成 Word 方案并返回下载地址或导出任务 ID。 |
| 导出 PPT | `POST /api/overseas-plans/{project_id}/exports/ppt` | 生成 PPT 方案并返回下载地址或导出任务 ID。 |
| 导出 Excel 行动计划 | `POST /api/overseas-plans/{project_id}/exports/excel-action-plan` | 生成 Excel 行动计划表。 |
| 导出资源清单 | `POST /api/overseas-plans/{project_id}/exports/resource-list` | 生成海外资源对接清单。 |
| 查询导出任务 | `GET /api/export-tasks/{task_id}` | 当导出为异步任务时查询状态和下载地址。 |
