# 企业出海报告生成系统端到端验收报告

## 1. 验收目标

本验收样例用于证明系统可以在不依赖真实 API Key 的情况下跑通完整企业出海报告生命周期：企业/产品主数据创建、本地资料上传解析、向量化检索、mock 联网研究、ContextBundle 构建、报告生成、质量评分、人工编辑、版本管理、最终版标记，以及 Word/PPT/Excel 导出。

## 2. 验收样例数据

| 类型 | 文件 | 用途 |
| --- | --- | --- |
| 示例企业数据 | `tests/fixtures/e2e/enterprise.json` | 创建“杭州智检医疗科技有限公司”企业主数据，覆盖行业、产能、认证、融资需求、出海目标、渠道偏好等字段。 |
| 示例产品数据 | `tests/fixtures/e2e/product.json` | 创建“Aquila 便携式检测仪”产品主数据，覆盖 HS 编码、卖点、认证、目标客户、合规要求等字段。 |
| 示例报告生成参数 | `tests/fixtures/e2e/generation_params.json` | 指定企业、产品、目标国家、生成用户，并通过 `force_web_research=true` 触发 mock WebResearch。 |
| 企业知识库样例 | `tests/fixtures/e2e/enterprise_profile.txt` | 上传、解析、切块、向量化企业资料。 |
| 产品知识库样例 | `tests/fixtures/e2e/product_profile.txt` | 上传、解析、切块、向量化产品资料。 |
| Mock LLM 报告正文 | `tests/fixtures/investment_grade_overseas_plan_sample.json` | 自动化测试中由 `MockLLM` 返回，避免真实 LLM 调用。 |

## 3. 自动化测试覆盖

新增测试文件：`tests/test_e2e_acceptance_flow.py`。

自动化测试按以下顺序执行并断言关键结果：

1. 创建企业：`POST /api/enterprises`。
2. 创建产品：`POST /api/products`。
3. 上传企业资料：`POST /api/knowledge/files/upload`。
4. 上传产品资料：`POST /api/knowledge/files/upload`。
5. 解析文件：断言 `parsed_status=parsed` 且存在 chunks。
6. 向量化：`POST /api/knowledge/files/{file_id}/embed`。
7. 检索本地知识库：`POST /api/knowledge/search`。
8. 联网研究：通过 `MockWebResearchService` 返回带来源的德国/荷兰研究结果。
9. 构建 ContextBundle：断言生成元数据包含本地知识、联网研究和 citations。
10. 生成报告：`POST /api/overseas-plans/generate`，由 `MockLLM` 返回确定性 JSON。
11. 质量评分：断言 `metadata.quality_review` 和 `metadata.quality_status` 已写入。
12. 人工编辑：`POST /api/overseas-plans/{project_id}/edit`。
13. 保存版本：断言版本列表包含 v1 AI 初版和 v2 人工编辑版。
14. 标记最终版：`POST /api/overseas-plans/{project_id}/finalize`，标记 v2 为最终版。
15. 导出 Word：`POST /api/overseas-plans/{project_id}/exports/word` 并断言 `.docx` 文件存在。
16. 导出 PPT：`POST /api/overseas-plans/{project_id}/exports/ppt` 并断言 `.pptx` 文件存在。
17. 导出 Excel：`POST /api/overseas-plans/{project_id}/exports/excel` 并断言 `.xlsx` 文件存在。
18. 输出最终验收状态：查询详情和审计日志，确认最终版号、导出文件引用、关键审计动作均存在。

## 4. Mock 策略

- LLM：`MockLLM` 只返回本地 JSON fixture，不读取环境变量，不访问网络。
- WebResearch：`MockWebResearchService` 返回固定的 source-preserving 研究结果，URL 使用 `example.test`，不访问真实搜索引擎。
- 本地知识库：使用 `HashingEmbeddingService` 和 `LocalFAISSVectorStore` 的本地/纯 Python 回退能力，资料文件为小型 `.txt` fixture。
- 数据库：测试内使用内存 SQLite 保存知识库元数据；企业/产品和报告版本使用内存仓储。

## 5. 手动验收清单

### 5.1 环境准备

- [ ] 安装依赖：`pip install -r requirements-dev.txt`。
- [ ] 确认不需要设置 `DEEPSEEK_API_KEY`。
- [ ] 确认测试环境可写 `/tmp/agent_overseas_report/exports`，或在服务层调用时传入临时导出目录。
- [ ] 确认 fixture 文件存在：`tests/fixtures/e2e/`。

### 5.2 主数据验收

- [ ] 企业创建接口返回 201。
- [ ] 企业 ID 为 `ent-e2e-001`。
- [ ] 产品创建接口返回 201。
- [ ] 产品 ID 为 `prod-e2e-001`，且 `enterprise_id=ent-e2e-001`。

### 5.3 本地知识库验收

- [ ] 企业资料上传返回 201。
- [ ] 产品资料上传返回 201。
- [ ] 两个文件均返回 `parsed_status=parsed`。
- [ ] 每个文件至少产生 1 个 chunk。
- [ ] 两个文件向量化均返回 `embedded_chunk_count=1`。
- [ ] 使用“德国 CE 经销商 售后 SLA”检索时至少返回 1 条结果。

### 5.4 生成与质量验收

- [ ] 生成接口返回 200。
- [ ] `generation_status=completed`。
- [ ] LLM mock 被调用 1 次。
- [ ] WebResearch mock 被调用 1 次。
- [ ] `metadata.context_bundle.local_knowledge_context.chunks` 非空。
- [ ] `metadata.context_bundle.web_research_context.sources` 非空。
- [ ] `metadata.context_bundle.citations` 非空。
- [ ] `metadata.quality_review.total_score` 大于 0。
- [ ] `metadata.quality_status` 为 `passed`、`needs_revision` 或 `failed_quality_check` 之一。

### 5.5 编辑、版本与最终版验收

- [ ] 人工编辑接口返回 200。
- [ ] 当前版本号变为 2。
- [ ] 版本列表包含 v1 和 v2。
- [ ] 标记最终版接口返回 200。
- [ ] v2 的 `is_final=true`。
- [ ] 计划详情的 `metadata.final_version_number=2`。

### 5.6 导出验收

- [ ] Word 导出返回 `.docx` 文件路径。
- [ ] PPT 导出返回 `.pptx` 文件路径。
- [ ] Excel 导出返回 `.xlsx` 文件路径。
- [ ] 三个文件路径均真实存在。
- [ ] 计划详情中的 `output_word`、`output_ppt`、`output_excel` 均指向对应导出文件。

### 5.7 审计验收

- [ ] 审计日志包含 `create_plan`。
- [ ] 审计日志包含 `ai_generate_plan`。
- [ ] 审计日志包含 `edit_ai_content`。
- [ ] 审计日志包含 `mark_final_version`。
- [ ] 审计日志包含 `export_word`。
- [ ] 审计日志包含 `export_ppt`。
- [ ] 审计日志包含 `export_excel_action_plan`。
- [ ] 审计日志不包含完整 AI 正文或人工编辑敏感正文。

## 6. 常见错误排查说明

| 现象 | 常见原因 | 排查/修复 |
| --- | --- | --- |
| `ModuleNotFoundError: fastapi/sqlalchemy` | 未安装开发依赖 | 运行 `pip install -r requirements-dev.txt`。 |
| 上传接口返回 415 | 文件扩展名或 MIME 类型不在白名单 | 使用 `.txt/.md/.pdf/.docx/.xlsx/.pptx`，测试文件 MIME 设置为 `text/plain`。 |
| 上传接口返回 413 | 文件超过 `MAX_UPLOAD_BYTES` | 使用小样例文件，或调整环境变量 `MAX_UPLOAD_BYTES`。 |
| `parsed_status=failed` | 文件格式不受支持或内容损坏 | 先用 `.txt` 小文件验证；再逐步替换为真实资料。 |
| 检索结果为空 | 尚未向量化、过滤条件不匹配、query 为空 | 确认已调用 embed；检查 `enterprise_id/product_id/industry/country`；换用更贴近资料内容的 query。 |
| WebResearch 未触发 | 本地知识库已有结果且未强制联网研究 | 在生成参数中设置 `extra_context.force_web_research=true`，或清空本地知识上下文。 |
| 生成结果失败 | Mock LLM 返回 JSON 非法或不满足输出 schema | 使用 `investment_grade_overseas_plan_sample.json`，或检查 mock 返回字段。 |
| 质量评分低 | 报告缺少引用、风险、路线图、预算/KPI 等结构 | 根据 `metadata.quality_review.issues` 和 `suggestions` 补齐内容。 |
| 导出文件不存在 | 导出目录无写权限或磁盘空间不足 | 确认 `/tmp/agent_overseas_report/exports` 可写；必要时在服务测试中传入 `tmp_path`。 |
| 版本无法标记最终版 | 指定版本号不存在 | 先调用版本列表接口确认版本号，再 finalize。 |

## 7. 最终验收结论

当 `pytest tests/test_e2e_acceptance_flow.py` 通过时，可判定本验收样例覆盖的端到端链路已跑通。该验收不证明外部 LLM、真实搜索引擎或真实生产数据库的可用性；它证明系统编排、接口契约、知识库 RAG、ContextBundle、质量评分、版本管理和三类导出在 mock 条件下可以完整闭环。
