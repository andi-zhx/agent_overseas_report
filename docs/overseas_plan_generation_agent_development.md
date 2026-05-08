# 企业出海方案自动生成智能体开发文档

> 适用对象：后端开发、前端开发、产品经理、测试同学、后续维护知识库与规则引擎的运营同学。  
> 模块范围：`agent_overseas_report` Python 包、`docs/overseas_plan_generation_api.md` 推荐 API 契约、前端工作台接入说明。

## 1. 功能介绍

“企业出海方案自动生成智能体”用于把企业基础信息、产品信息、目标行业、目标国家、行业/国家/资源模板库和确定性规则引擎结果，组合为可预览、可编辑、可导出的企业出海解决方案。

当前实现具有以下能力：

1. **方案生成编排**：通过 `OverseasPlanGenerationService` 完成草稿创建、同步生成、重新生成、版本追加、结果保存和失败状态记录。
2. **DeepSeek 调用适配**：通过 OpenAI-compatible Chat Completions SDK 调用 DeepSeek，配置集中在环境变量中。
3. **生成前完整性检查**：对企业、产品、出海目标三类字段做缺失检查，并向提示词注入“不得编造、需人工复核”的约束。
4. **规则引擎预判断**：在调用 LLM 前计算成熟度评分、国家优先级、渠道推荐、资源匹配和缺失字段。
5. **行业/国家/资源模板库**：以 JSON 种子文件维护，后续可迁移为数据库后台管理。
6. **结构化 JSON 结果**：提示词要求 DeepSeek 输出结构化方案，后端会解析、校验、尝试修复，并在失败时回退到规则引擎兜底内容。
7. **安全后处理**：对政策、关税、准入、认证、市场规模等动态信息追加人工复核标记；对未核验资源名称和联系方式做保守替换。
8. **版本管理**：AI 生成、重新生成、用户编辑、历史恢复、最终版标记均以版本形式追加保存，不覆盖历史内容。
9. **Word/PPT/Excel 导出**：使用标准库写入 `.docx`、`.pptx`、`.xlsx`，导出时优先使用最终版，其次使用最新完成版。
10. **审计日志**：对创建、生成、查看、编辑、导出、恢复、设为最终版、归档、删除等动作写入追加式审计日志。

## 2. 核心流程图文字版

```text
[前端/调用方]
  |
  | 1. 选择企业、产品、行业、目标国家，提交 GenerationRequest
  v
[OverseasPlanGenerationService.generate]
  |
  | 2. create_generation：创建 draft 项目版本，写 create_plan 审计日志
  v
[InMemoryGenerationStore]
  |
  | 3. run_generation：状态改为 generating
  v
[企业/产品数据仓储 EnterpriseDataRepository]
  |
  | 4. 读取企业基础信息 + 选中产品信息，组装 enterprise_data
  v
[生成前完整性检查 generation_readiness]
  |
  | 5. 输出 READY / LOW_QUALITY / NOT_RECOMMENDED、缺失字段、提示词约束
  |    - 若缺失关键字段且未允许继续：终止生成并写 failed 审计日志
  v
[模板库 KnowledgeBaseTemplateRepository]
  |
  | 6. 按行业/国家/区域匹配行业模板、国家模板、资源模板
  v
[规则引擎 OverseasRuleEngine]
  |
  | 7. 输出成熟度评分、国家优先级矩阵、渠道推荐、资源匹配、缺失字段
  v
[Prompt Builder]
  |
  | 8. 组合企业数据、模板库、规则输出、JSON 示例，生成 system/user prompt
  v
[DeepSeekLLMService / DeepSeek API]
  |
  | 9. 生成结构化 JSON 文本
  v
[解析/校验/修复]
  |
  | 10. JSON 解析成功 -> 校验 schema
  | 11. JSON 失败 -> 发起一次修复提示词
  | 12. 修复仍失败 -> 规则引擎兜底 payload
  v
[安全后处理]
  |
  | 13. 动态信息标记需人工复核；未核验资源占位
  v
[保存结果 + 版本 + 审计]
  |
  | 14. 状态 completed/failed，追加 PlanContentVersion，写 ai_generate_plan 审计日志
  v
[前端预览/编辑/导出]
  |
  | 15. 用户编辑 -> 追加 user_edit 版本
  | 16. 导出 Word/PPT/Excel -> 选择最终版或最新完成版，写导出审计日志
```

## 3. DeepSeek API 配置方式

### 3.1 环境变量

复制 `.env.example`，在运行环境中配置以下变量：

```bash
cp .env.example .env
```

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | 无 | DeepSeek 控制台创建的 API Key，禁止提交真实密钥。 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 默认文本生成模型。 |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek OpenAI-compatible API 地址。 |
| `DEEPSEEK_TIMEOUT_SECONDS` | 否 | `60` | 请求超时时间，必须是数字。 |

### 3.2 服务初始化

生产/集成环境建议显式注入 `DeepSeekLLMService`：

```python
from agent_overseas_report.services.llm_service import DeepSeekLLMService
from agent_overseas_report.services.generation_service import OverseasPlanGenerationService

service = OverseasPlanGenerationService(
    data_repository=enterprise_repository,
    llm_client=DeepSeekLLMService(),
)
```

`DeepSeekLLMService()` 默认从环境变量读取配置。测试时可以注入 fake client 或 fake `PlanLLMClient`，避免真实网络调用。

### 3.3 连通性验证

项目提供脚本用于验证 DeepSeek 调用：

```bash
python scripts/verify_deepseek_call.py
```

运行前必须设置 `DEEPSEEK_API_KEY`。如果本地只跑单元测试，不需要真实 Key。

### 3.4 日志与安全

- 服务日志只记录模型、prompt 长度、响应长度等元信息，不记录完整 prompt 和企业敏感正文。
- 审计日志不保存 AI 生成正文，只保存操作人、动作、企业/方案/产品 ID、目标国家、结果状态、导出路径等元数据。
- 真实密钥只能存在本地 `.env`、CI Secret 或部署平台 Secret 中，不能写入代码、文档示例输出或测试快照。

## 4. 企业出海方案生成流程

### 4.1 输入 DTO

核心请求对象为 `GenerationRequest`，主要字段包括：

| 字段 | 说明 |
| --- | --- |
| `enterprise_id` | 企业 ID，用于读取企业基础数据。 |
| `product_ids` | 本次参与生成的产品 ID 列表。 |
| `selected_industry` | 目标行业，用于覆盖/补充企业行业并匹配行业模板。 |
| `target_countries` | 目标国家或地区，用于匹配国家模板和区域资源。 |
| `generated_by` | 发起人用户 ID，用于审计日志和版本创建人。 |
| `extra_context` | 额外上下文，如方案语言、前端场景、重生成原因等。 |
| `continue_on_validation_warning` | 关键字段缺失时是否继续生成；默认保守阻断。 |

### 4.2 主服务调用

推荐同步调用：

```python
response = service.generate(
    GenerationRequest(
        enterprise_id="ent-1",
        product_ids=["prod-1", "prod-2"],
        selected_industry="医疗器械",
        target_countries=["德国", "美国"],
        generated_by="user-1001",
    )
)
```

后续如果接入异步队列，可拆分为：

1. `create_generation(request)`：立即返回 `draft` 项目；
2. 将项目 ID 投递到 Celery/RQ/Arq；
3. Worker 调用 `run_generation(project_id)`；
4. 前端轮询项目状态或通过 WebSocket/SSE 接收完成事件。

### 4.3 生成阶段细节

1. **创建项目**：项目 ID 前缀为 `ogp_`，状态为 `draft`，写入 `create_plan` 审计日志。
2. **加载数据**：调用 `EnterpriseDataRepository.get_enterprise()` 与 `get_products()`，并派生认证、MOQ、产能、英文资料等字段。
3. **生成前完整性检查**：检查企业层面、产品层面、目标层面字段；关键字段缺失时默认不建议继续。
4. **加载模板**：按目标国家拿国家模板，按行业和目标国家拿行业模板，按行业和区域拿资源模板。
5. **运行规则引擎**：产出可解释的确定性建议，作为 DeepSeek prompt 上下文。
6. **构建提示词**：包含系统角色、输出 JSON 约束、企业数据、模板、规则结果、数据质量说明。
7. **DeepSeek 生成**：调用 `generate_text()`，要求返回可解析 JSON。
8. **JSON 校验与修复**：首次解析失败会发起一次修复；修复失败则使用规则引擎兜底 payload。
9. **安全后处理**：动态政策/关税/认证等信息标记“需人工复核”；未核验资源名称/联系方式替换为“待人工确认”。
10. **保存结果**：状态置为 `completed`，保存最终分数、成熟度等级、模型名、是否 JSON 修复/兜底。
11. **追加版本**：保存 `PlanContentVersion`，来源可为 AI 生成、重新生成或用户编辑。
12. **写审计日志**：写入 `ai_generate_plan` 成功/失败记录，并返回预览 payload。

## 5. 规则引擎说明

规则引擎位于 `agent_overseas_report/services/rule_engine.py`，设计原则是“本地、确定性、可单测、可解释”，在任何 DeepSeek 调用前执行。

### 5.1 输入

规则引擎接收 `enterprise_data`，典型结构：

```json
{
  "enterprise": {"name": "示例企业", "industry": "医疗器械"},
  "products": [{"name": "一次性耗材", "hs_code": "9018", "certifications": ["CE"]}],
  "target_markets": ["德国", "美国"],
  "certifications": ["CE"],
  "capacity": {"monthly_units": 10000},
  "moq": 500
}
```

### 5.2 输出

`evaluate()` 统一输出：

| 输出字段 | 说明 |
| --- | --- |
| `maturity_assessment` | 100 分制成熟度评分、等级、七个维度分、缺失字段、改进建议。 |
| `country_recommendation` | 主攻市场、次级市场、长期市场、国家优先级矩阵、推荐国家名称。 |
| `channel_matches` | 经销代理、跨境电商、本地 KA、工程渠道、海外合资/办事处、本地仓、海外工厂等路径评分。 |
| `resource_matches` | 展会、推介会、采购对接会、商协会、渠道代理商、物流/海外仓、认证机构等资源匹配。 |
| `missing_fields` | 面向用户展示的缺失字段列表。 |
| `explanation` | 规则引擎判断说明。 |

### 5.3 成熟度评分维度

成熟度总分为 100 分，覆盖：

1. 产品国际化程度；
2. 海外渠道基础；
3. 英文资料完整性；
4. 认证状态；
5. 供应链稳定性；
6. 团队国际化能力；
7. 资金能力。

每个维度都输出分值、满分、解释和证据，便于前端展示和测试断言。

### 5.4 国家推荐逻辑

国家优先级综合考虑：

- 行业模板与国家模板的推荐行业是否匹配；
- 国家模板中的市场潜力与进入难度；
- 政策环境、物流说明、渠道适配；
- 企业是否已经指定目标国家或目标区域；
- 企业当前成熟度是否适合高难度市场。

输出结果会按 `priority_score` 降序排序，并切分为主攻、次级、长期三类市场。

### 5.5 渠道和资源推荐逻辑

- 渠道推荐基于行业、产品关键词、已有海外客户、产能、成熟度等因素加减分。
- 资源匹配通过资源类型别名映射，把展会、商协会、渠道代理商、物流/海外仓、认证机构等模板映射到可执行资源清单。
- 当前资源模板是“资源类型模板”，不代表已经核验的具体机构名单；具体机构名称、联系人、联系方式需接入真实资源库后再展示。

## 6. 行业模板库说明

行业模板库文件：`agent_overseas_report/knowledge_base/templates/industry_templates.json`。

### 6.1 用途

行业模板用于回答“该行业适合怎么出海”：

- 行业常见出海产品；
- 适合优先进入的区域；
- 常见市场进入模式；
- 关键认证和准入要求；
- 报价与价格带逻辑；
- 常见渠道、展会；
- 主要风险；
- 推荐策略。

### 6.2 维护要求

新增行业模板时需保证：

1. `industry_name` 唯一且与前端行业枚举一致；
2. `suitable_regions` 与国家模板 `region`、资源模板 `applicable_regions` 口径一致；
3. `common_entry_modes` 使用规则引擎可识别的业务口径，例如经销代理、跨境电商、海外仓、本地办事处等；
4. `key_certifications` 避免写入过期或无法验证的具体监管结论；涉及动态政策需标注需人工复核；
5. 修改后运行测试，确保 JSON 可加载且字段完整。

## 7. 国家模板库说明

国家模板库文件：`agent_overseas_report/knowledge_base/templates/country_templates.json`。

### 7.1 用途

国家模板用于回答“某国家/地区是否适合进入、如何进入”：

- 所属区域；
- 市场机会；
- 政策与营商环境；
- 关税、准入、认证或标签注意事项；
- 当地渠道、物流与仓储注意事项；
- 本地合作伙伴类型；
- 展会、商协会；
- 进入难度、市场潜力；
- 推荐匹配行业。

### 7.2 维护要求

1. `country_name` 与前端国家选择器一致；
2. `region` 与行业模板、资源模板使用同一套区域口径；
3. `recommended_industries` 需要使用行业模板中已有的 `industry_name`；
4. `market_potential`、`entry_difficulty` 建议使用稳定枚举或稳定描述，避免过细实时数据；
5. 政策、关税、准入、法规等动态信息仅作为方向性提示，具体项目落地前必须人工复核最新政策。

## 8. 资源模板库说明

资源模板库文件：`agent_overseas_report/knowledge_base/templates/resource_templates.json`。

### 8.1 用途

资源模板用于回答“方案中应该对接哪些类型的外部资源”：

- 渠道代理商；
- 电商平台；
- 展会与采购对接活动；
- 商协会；
- 物流服务商与海外仓；
- 认证检测机构；
- 金融、保险、法务、税务等服务资源。

### 8.2 字段口径

| 字段 | 说明 |
| --- | --- |
| `resource_type` | 资源类型名称，供规则引擎匹配。 |
| `resource_category` | 一级分类，对齐未来海外资源库模型。 |
| `resource_subtype` | 二级分类，对齐未来海外资源库模型。 |
| `description` | 资源用途说明。 |
| `applicable_industries` | 适配行业列表。 |
| `applicable_regions` | 适配区域列表。 |
| `matching_tags` | 规则/AI 匹配标签。 |
| `selection_criteria` | 筛选此类资源的建议标准。 |
| `maintenance_fields` | 后台维护真实资源时建议采集字段。 |
| `recommended_use` | 在方案中的推荐使用方式。 |

### 8.3 注意事项

- 当前模板库只描述“资源类型”，不是已核验的具体资源名录。
- 如果 DeepSeek 输出了未核验的具体机构名称、联系方式，安全后处理会替换为“待补充/需人工确认”。
- 后续接入真实海外资源库后，可通过 `verified_resource_library` 或人工确认标记保留已核验资源。

## 9. Word/PPT/Excel 导出说明

导出服务均在 `agent_overseas_report/services` 下，当前不依赖 Web 框架，也不依赖第三方 Office 库，使用 Python 标准库写入 OOXML 文件。

### 9.1 Word 导出

- 入口：`OverseasPlanGenerationService.export_word()`。
- DTO：`WordExportRequest` / `WordExportResult`。
- 文件格式：`.docx`。
- 默认目录：`/tmp/agent_overseas_report/exports/word/{project_id}/`。
- 内容：封面、企业诊断、市场选择、进入模式、资源匹配、展会营销、融资产能、12/24 月路线图、风险与人工复核提示等。

### 9.2 PPT 导出

- 入口：`OverseasPlanGenerationService.export_ppt()`。
- DTO：`PPTExportRequest` / `PPTExportResult`。
- 文件格式：`.pptx`。
- 默认目录：`/tmp/agent_overseas_report/exports/ppt/{project_id}/`。
- 内容：面向汇报场景的出海方案页，包括诊断、市场优先级、渠道打法、资源匹配、路线图、风险等。

### 9.3 Excel 导出

- 入口：`OverseasPlanGenerationService.export_excel()`。
- DTO：`ExcelExportRequest` / `ExcelExportResult`。
- 文件格式：`.xlsx`。
- 默认目录：`/tmp/agent_overseas_report/exports/excel/{project_id}/`。
- 支持类型：
  - `ExcelExportKind.ACTION_PLAN`：行动计划表；
  - `ExcelExportKind.RESOURCE_LIST`：海外资源对接清单。

### 9.4 导出版本选择规则

导出前会调用 `_project_for_export()`：

1. 优先使用同一历史组内被标记为 `is_final = true` 且状态为 completed 的最终版；
2. 如果没有最终版，使用版本号最大的 completed 版本；
3. 如果没有历史版本，则回退到当前 `GenerationProject.result`。

### 9.5 导出审计

每次导出都会写审计日志：

- Word：`export_word`；
- PPT：`export_ppt`；
- Excel 行动计划：`export_excel_action_plan`；
- Excel 资源清单：`export_resource_list`。

审计日志会记录导出人、企业、方案、版本、文件路径、导出类型、成功/失败状态等。

## 10. 审计日志说明

### 10.1 设计目标

审计日志用于追踪谁在什么时间对哪个企业/方案做了什么操作，以及操作是否成功。日志采用追加式写入，不保存 AI 正文，降低敏感信息泄露风险。

### 10.2 动作类型

当前预留动作包括：

| 动作 | 场景 |
| --- | --- |
| `create_plan` | 创建方案草稿。 |
| `ai_generate_plan` | AI 生成方案成功或失败。 |
| `regenerate_plan` | 从历史方案重新生成。 |
| `view_plan_detail` | 查看方案详情。 |
| `edit_ai_content` | 用户编辑 AI 生成内容。 |
| `export_word` | 导出 Word。 |
| `export_ppt` | 导出 PPT。 |
| `export_excel_action_plan` | 导出 Excel 行动计划。 |
| `export_resource_list` | 导出资源清单。 |
| `restore_version` | 恢复历史版本为当前可编辑版本。 |
| `mark_final_version` | 标记最终版。 |
| `archive_plan` | 归档方案。 |
| `delete_plan` | 删除方案。 |

### 10.3 日志字段

主要字段包括：

- `id`：审计日志 ID，前缀 `opa_`；
- `user_id` / `username`：操作人；
- `action_type`：动作类型；
- `enterprise_id` / `plan_id` / `product_ids` / `target_countries`：业务对象；
- `export_type` / `file_path`：导出相关信息；
- `created_at`：操作时间；
- `ip_address` / `user_agent`：请求上下文；
- `result_status`：`success` 或 `failed`；
- `error_message`：失败原因；
- `metadata`：版本号、变更字段、导出类型等扩展信息。

### 10.4 查询建议

服务层提供 `list_plan_audit_logs(query)`，可按企业、用户、动作、时间范围、方案 ID 查询。未来接入数据库时建议对 `enterprise_id`、`user_id`、`action_type`、`created_at`、`plan_id` 建索引。

## 11. 本地开发与测试方式

### 11.1 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 11.2 配置环境变量

如果只运行单元测试，可不配置 DeepSeek Key。若需要真实调用：

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
```

### 11.3 运行测试

```bash
pytest
```

建议重点关注：

- `tests/test_generation_service.py`：主编排、版本、导出、审计等；
- `tests/test_rule_engine.py`：成熟度、国家、渠道、资源匹配；
- `tests/test_knowledge_base_templates.py`：模板库字段和匹配；
- `tests/test_llm_service.py`：DeepSeek 服务配置、JSON 解析、异常处理；
- `tests/test_generation_readiness.py`：生成前完整性检查；
- `tests/test_overseas_plan_prompt.py`：提示词和输出结构约束。

### 11.4 运行规则引擎 Demo

```bash
python scripts/run_rule_engine_demo.py
```

该脚本不需要 DeepSeek Key，可用于快速查看规则引擎输出结构。

### 11.5 验证 DeepSeek 真实调用

```bash
DEEPSEEK_API_KEY=sk-xxx python scripts/verify_deepseek_call.py
```

注意：不要把真实 Key 写入 shell history、CI 日志、文档或截图。

## 12. 常见问题

### Q1：为什么有时缺字段会直接生成失败？

当缺失企业名称、所属行业、产品名称、目标国家等关键字段时，完整性检查会返回 `NOT_RECOMMENDED`，默认阻断生成，避免模型基于空数据编造方案。若业务上必须继续，可设置 `continue_on_validation_warning=True`，但输出会被标记为需人工复核。

### Q2：DeepSeek 返回的不是合法 JSON 怎么办？

服务会先尝试解析 JSON；失败后向 DeepSeek 发起一次“修复为合法 JSON”的提示词；如果修复仍失败或 provider 报错，会使用规则引擎结果构造兜底 payload，并在项目 metadata 中记录 `json_fallback_used` 和原因。

### Q3：规则引擎和 DeepSeek 是什么关系？

规则引擎是确定性前置判断，用于提供可解释、可测试的结构化建议；DeepSeek 负责把企业信息、规则结果、模板库内容组织成咨询方案表达。即使 DeepSeek 不可用，规则引擎也能提供兜底方案框架。

### Q4：模板库里能不能直接写某机构联系人或手机号？

不建议。当前资源模板库定位为“资源类型模板”，不是已核验资源名录。真实机构、联系人、联系方式应接入独立资源库，并通过人工确认或 `verified_resource_library` 标记后再进入方案。

### Q5：导出内容为什么提示“需人工复核”？

政策、关税、准入、认证、市场规模、增长率等信息会随时间变化。系统会对这类动态信息保守标记，提醒顾问在交付客户前核验最新政策和市场数据。

### Q6：如何新增一个行业或国家？

修改对应 JSON 模板文件，保持字段完整、命名一致，然后运行 `pytest`。新增国家时尤其要确认 `region` 与行业/资源模板一致，`recommended_industries` 使用已存在行业名。

### Q7：现在为什么使用内存 Store？

当前模块是框架无关的业务服务，`InMemoryGenerationStore` 便于测试和 Demo。接入真实后端时应替换为数据库 Repository，并保持方法语义：项目保存、版本追加、最终版选择、审计日志追加与查询。

### Q8：前端如何接入？

前端工作台可调用推荐 REST 契约：创建生成、查询版本、保存编辑、恢复历史版本、标记最终版、导出 Word/PPT/Excel。接口示例见 `docs/overseas_plan_generation_api.md` 和前端工作台 README。

### Q9：是否可以流式生成？

`DeepSeekLLMService.stream_generate()` 当前仅预留接口，尚未实现。若后续需要流式预览，应在服务层增加状态事件和前端 SSE/WebSocket 通道，同时保留最终 JSON 校验和版本保存机制。

## 13. 后续可扩展方向

1. **数据库持久化**：将 `InMemoryGenerationStore` 替换为真实数据库表，支持跨进程任务、分页查询、权限控制和审计留存。
2. **异步生成任务**：接入 Celery/RQ/Arq，把 `create_generation()` 与 `run_generation()` 拆分为“提交任务 + 后台执行”。
3. **模板后台管理**：把行业、国家、资源模板迁移到后台可维护表，支持版本、启停、审批、导入导出。
4. **真实海外资源库**：接入机构、展会、商协会、代理商、海外仓、认证机构等已核验资源，区分模板建议和真实资源。
5. **多模型与降级策略**：抽象 LLM Provider，支持 DeepSeek、OpenAI-compatible 私有模型、本地模型，并配置重试、限流、熔断。
6. **RAG 与资料引用**：引入政策库、案例库、企业附件、产品手册检索，要求方案引用来源并标注更新时间。
7. **更强 schema 校验**：使用 JSON Schema 或 Pydantic 模型校验 DeepSeek 输出，提供更细粒度错误提示。
8. **权限与租户隔离**：按企业、园区、服务商、用户角色控制方案查看、编辑、导出和审计查询权限。
9. **导出模板定制**：支持不同园区/服务商的 Word/PPT 版式、Logo、封面、页脚和目录模板。
10. **人工协同流程**：增加顾问审核、客户确认、最终版签发、评论批注、任务分派等流程节点。
11. **指标与质量评估**：记录生成耗时、修复率、兜底率、用户编辑差异、导出转化率，用于持续优化提示词和规则。
12. **国际化输出**：支持中文、英文及目标国家本地语言方案，按语言切换提示词和导出模板。
13. **前端流式体验**：增加“正在诊断企业”“正在匹配国家”“正在生成路线图”等阶段化进度与局部预览。
