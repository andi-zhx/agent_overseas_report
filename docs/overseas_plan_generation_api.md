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
