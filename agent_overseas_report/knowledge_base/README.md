# 出海方案知识库模板

当前项目尚未引入 ORM 或数据库迁移机制，因此“出海方案知识库模板”先采用可维护的 JSON 种子数据实现，后续可以按同名字段迁移到后台管理数据库表。

## 文件位置

- 行业模板库：`agent_overseas_report/knowledge_base/templates/industry_templates.json`
- 国家模板库：`agent_overseas_report/knowledge_base/templates/country_templates.json`
- 资源模板库：`agent_overseas_report/knowledge_base/templates/resource_templates.json`
- 读取与匹配入口：`agent_overseas_report/knowledge_base/repository.py`

## 行业模板字段

- `industry_name`：行业名称。
- `typical_products`：该行业常见出海产品。
- `suitable_regions`：适合优先进入的区域。
- `common_entry_modes`：常见市场进入模式。
- `key_certifications`：重点认证、检测或准入要求。
- `pricing_logic`：报价、成本和价格带设计逻辑。
- `common_channels`：常见销售或获客渠道。
- `common_trade_shows`：常见展会或采购对接活动。
- `major_risks`：主要风险。
- `recommended_strategy`：推荐出海策略。

## 国家模板字段

- `country_name`：国家或地区名称。
- `region`：所属区域。
- `market_opportunity`：市场机会概述。
- `policy_environment`：政策、营商和合规环境。
- `tariff_or_access_notes`：关税、准入、认证或标签说明。
- `common_channels`：当地常见渠道。
- `logistics_notes`：物流、仓储和交付注意事项。
- `local_partner_types`：建议对接的本地合作伙伴类型。
- `relevant_trade_shows`：相关展会。
- `business_associations`：可对接商协会。
- `entry_difficulty`：进入难度。
- `market_potential`：市场潜力。
- `recommended_industries`：推荐匹配行业。

## 资源模板字段

- `resource_type`：资源类型，例如渠道代理商、电商平台、海外仓等。
- `resource_category`：资源一级分类，对齐海外资源库模型。
- `resource_subtype`：资源二级分类，对齐海外资源库模型。
- `description`：资源用途说明。
- `applicable_industries`：适配行业。
- `applicable_regions`：适配区域。
- `matching_tags`：用于 AI 或规则匹配的能力标签。
- `selection_criteria`：筛选资源时的建议标准。
- `maintenance_fields`：后续后台维护该类资源时建议展示或收集的字段。
- `recommended_use`：在出海方案生成流程中的推荐用法。

## 新增行业模板

1. 打开 `agent_overseas_report/knowledge_base/templates/industry_templates.json`。
2. 在 JSON 数组末尾新增一个对象，并完整填写行业模板字段。
3. 确保 `industry_name` 与国家模板中的 `recommended_industries` 可匹配。
4. 运行 `pytest` 验证 JSON 可加载、字段完整且匹配方法可用。

## 新增国家模板

1. 打开 `agent_overseas_report/knowledge_base/templates/country_templates.json`。
2. 在 JSON 数组末尾新增一个对象，并完整填写国家模板字段。
3. 确保 `region` 与行业模板的 `suitable_regions`、资源模板的 `applicable_regions` 口径一致。
4. 在 `recommended_industries` 中使用行业模板已有的 `industry_name`，便于按国家匹配行业。
5. 运行 `pytest` 验证 JSON 可加载、字段完整且匹配方法可用。
