# 企业出海报告端到端验收样例

本目录提供无需真实 API Key 即可运行的验收样例：

- `enterprise.json`：示例企业主数据。
- `product.json`：示例产品主数据。
- `generation_params.json`：报告生成参数，强制启用 mock WebResearch。
- `enterprise_profile.txt`：企业本地知识库小样例文件。
- `product_profile.txt`：产品本地知识库小样例文件。

自动化测试会使用本目录数据完成企业创建、产品创建、资料上传解析、向量化、检索、mock 联网研究、ContextBundle 构建、报告生成、质量评分、人工编辑、版本保存、最终版标记以及 Word/PPT/Excel 导出。
