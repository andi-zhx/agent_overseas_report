"""Word export utilities for enterprise overseas-plan documents.

The project does not depend on a web framework yet, so this module builds a
minimal OOXML ``.docx`` package with the Python standard library.  The generated
file is compatible with Microsoft Word/WPS and uses Chinese-capable East Asian
font declarations.
"""

from __future__ import annotations

import html
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


SYSTEM_NAME = "企业出海方案智能生成系统"
DEFAULT_EXPORT_ROOT = Path("/tmp/agent_overseas_report/exports/word")
WordReportVersion = Literal["client", "internal"]


@dataclass(slots=True)
class WordExportRequest:
    """Input DTO for exporting a completed overseas plan to Word."""

    project_id: str
    exported_by: str
    report_version: WordReportVersion | str = "client"
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    output_dir: str | Path | None = None
    system_name: str = SYSTEM_NAME


@dataclass(slots=True)
class WordExportResult:
    """Result returned after a Word export file is written."""

    project_id: str
    plan_name: str
    export_type: str
    file_path: str
    exported_by: str
    exported_at: str
    report_version: str = "client"
    audit_log_path: str | None = None


class WordDocumentBuilder:
    """Small OOXML document builder with headings, paragraphs and tables."""

    def __init__(self) -> None:
        self._body: list[str] = []

    def add_title(self, text: str) -> None:
        self._body.append(_paragraph(text, style="Title", alignment="center"))

    def add_subtitle(self, text: str) -> None:
        self._body.append(_paragraph(text, style="Subtitle", alignment="center"))

    def add_heading(self, text: str, level: int = 1) -> None:
        style = "Heading1" if level == 1 else "Heading2" if level == 2 else "Heading3"
        self._body.append(_paragraph(text, style=style))

    def add_paragraph(self, text: Any, *, style: str | None = None) -> None:
        self._body.append(_paragraph(_stringify(text), style=style))

    def add_notice(self, text: Any) -> None:
        self._body.append(_paragraph(_stringify(text), style="Notice"))

    def add_bullets(self, items: list[Any]) -> None:
        if not items:
            self.add_notice("暂无数据，建议后续补充并需人工复核。")
            return
        for item in items:
            self._body.append(_paragraph(f"• {_stringify(item)}"))

    def add_table(self, headers: list[str], rows: list[list[Any]]) -> None:
        normalized_rows = rows or [["暂无数据/需人工复核"] + ["" for _ in headers[1:]]]
        self._body.append(_table(headers, normalized_rows))

    def add_page_break(self) -> None:
        self._body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def build_xml(self) -> str:
        sect_pr = (
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1200" w:right="1080" '
            'w:bottom="1200" w:left="1080" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
        )
        return (
            _xml_header()
            + '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            + f'<w:body>{"".join(self._body)}{sect_pr}</w:body></w:document>'
        )


def export_overseas_plan_word(
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    output_dir: str | Path | None = None,
    exported_by: str,
    system_name: str = SYSTEM_NAME,
    exported_at: datetime | None = None,
    report_version: WordReportVersion | str = "client",
) -> WordExportResult:
    """Generate and save the enterprise overseas solution Word document."""

    normalized_version = _normalize_report_version(report_version)
    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    plan_name = f"{enterprise_name}企业出海服务正式报告"
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = "内部版" if normalized_version == "internal" else "客户版"
    file_name = f"{_safe_filename(plan_name)}_{suffix}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.docx"
    file_path = target_dir / file_name

    builder = WordDocumentBuilder()
    _build_document(
        builder,
        project=project,
        enterprise=enterprise,
        plan_name=plan_name,
        system_name=system_name,
        generated_at=exported_at,
        report_version=normalized_version,
    )
    _write_docx(file_path, builder.build_xml())
    audit_log_path = _append_export_audit_log(
        target_dir,
        {
            "project_id": str(project["id"]),
            "plan_name": plan_name,
            "export_type": "Word",
            "report_version": normalized_version,
            "file_path": str(file_path),
            "exported_by": exported_by,
            "exported_at": exported_at_iso,
            "system_name": system_name,
        },
    )

    return WordExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="Word",
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
        report_version=normalized_version,
        audit_log_path=str(audit_log_path),
    )


def _build_document(
    builder: WordDocumentBuilder,
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    plan_name: str,
    system_name: str,
    generated_at: datetime,
    report_version: str,
) -> None:
    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    metadata = project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    target_markets = project.get("target_countries") or []
    products = metadata.get("enterprise_payload", {}).get("products") if isinstance(metadata.get("enterprise_payload"), dict) else None
    products = products or project.get("products") or []
    manual_review_items = _collect_manual_review_items(result, metadata, include_internal_context=report_version == "internal")
    sources = _collect_data_sources(result, metadata)

    _add_cover(builder, plan_name, enterprise, project, target_markets, system_name, generated_at, report_version)
    _add_contents(builder)

    _add_executive_summary(builder, result, sections, enterprise, project, manual_review_items)
    _add_enterprise_product_profile(builder, enterprise, products, project)
    _add_maturity_diagnosis(builder, sections, project, metadata, report_version)
    _add_target_market_analysis(builder, sections, result, target_markets)
    _add_country_priority_matrix(builder, sections, result, target_markets)
    _add_competitor_price_analysis(builder, sections, result)
    _add_market_entry_strategy(builder, sections, result)
    _add_channel_path(builder, sections, result)
    _add_exhibition_procurement_plan(builder, sections, result)
    _add_resource_matching(builder, sections, result)
    _add_financing_capacity_advice(builder, sections, result)
    _add_budget_kpi(builder, sections, result)
    _add_roadmap(builder, sections, result)
    _add_risks(builder, sections, result)
    _add_data_sources(builder, sources)
    _add_manual_review_checklist(builder, manual_review_items)
    if report_version == "internal":
        _add_internal_quality_appendix(builder, project, metadata)
    _add_appendix(builder, result, metadata, report_version)


def _add_cover(builder: WordDocumentBuilder, plan_name: str, enterprise: dict[str, Any], project: dict[str, Any], target_markets: list[Any], system_name: str, generated_at: datetime, report_version: str) -> None:
    builder.add_title(f"《{plan_name}》")
    builder.add_subtitle("企业出海服务报告 · 可交付版")
    builder.add_table(
        ["项目", "内容"],
        [
            ["报告版本", "内部版（含质量评分与缺失字段）" if report_version == "internal" else "客户版"],
            ["企业名称", enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id")],
            ["所属行业", project.get("selected_industry") or enterprise.get("industry")],
            ["目标市场", target_markets],
            ["报告日期", generated_at.strftime("%Y-%m-%d")],
            ["生成机构/系统", system_name],
            ["保密提示", "本报告仅供指定客户用于出海决策参考，涉及动态政策、价格、展会和资源名单的内容均需在执行前复核。"],
        ],
    )
    builder.add_notice("重要声明：所有标注“需人工复核”的信息已在正文或清单中保留，不得在交付前删除或隐藏。")
    builder.add_page_break()


def _add_contents(builder: WordDocumentBuilder) -> None:
    builder.add_heading("目录", 1)
    for item in _report_sections():
        builder.add_paragraph(f"{item[0]}. {item[1]}")
    builder.add_page_break()


def _add_executive_summary(builder: WordDocumentBuilder, result: dict[str, Any], sections: dict[str, Any], enterprise: dict[str, Any], project: dict[str, Any], manual_review_items: list[str]) -> None:
    builder.add_heading("03 执行摘要", 1)
    summary = _extract(result, "executive_summary", "summary") or _extract(sections.get("00_executive_summary", {}), "summary", "content")
    builder.add_paragraph(summary or f"围绕{enterprise.get('name') or project.get('enterprise_id')}的产品能力、目标市场、渠道路径和资源匹配，本报告形成12-24个月出海实施建议。")
    builder.add_table(
        ["核心判断", "建议"],
        [
            ["首批市场", project.get("target_countries") or "需人工复核"],
            ["优先策略", _extract(sections.get("03_entry_mode_design", {}), "recommended_strategy", "first_stage_channel") or _extract(result, "recommended_entry_modes")],
            ["关键风险", _stringify(_as_list(_extract(sections.get("08_risk_warnings_and_next_steps", {}), "risk_warnings", "risks") or result.get("risk_warnings"))[:3])],
            ["复核提示", f"存在 {len(manual_review_items)} 项需人工复核内容" if manual_review_items else "未发现显式复核标记，仍建议复核动态信息"],
        ],
    )


def _add_enterprise_product_profile(builder: WordDocumentBuilder, enterprise: dict[str, Any], products: Any, project: dict[str, Any]) -> None:
    builder.add_heading("04 企业与产品画像", 1)
    builder.add_heading("企业画像", 2)
    builder.add_table(
        ["维度", "内容"],
        [
            ["企业名称", enterprise.get("name") or enterprise.get("enterprise_name")],
            ["行业", enterprise.get("industry") or project.get("selected_industry")],
            ["当前海外客户/市场", enterprise.get("overseas_customers") or enterprise.get("current_export_countries") or "需人工复核"],
            ["国际化团队", enterprise.get("team") or enterprise.get("team_internationalization") or "需人工复核"],
            ["资金能力", enterprise.get("finance") or enterprise.get("capital_capacity") or "需人工复核"],
        ],
    )
    builder.add_heading("产品画像", 2)
    rows = [_product_row(item) for item in _as_list(products)]
    builder.add_table(["产品", "HS编码", "认证", "价格带", "MOQ/交期", "产能"], rows)


def _add_maturity_diagnosis(builder: WordDocumentBuilder, sections: dict[str, Any], project: dict[str, Any], metadata: dict[str, Any], report_version: str) -> None:
    data = sections.get("01_enterprise_diagnosis", {})
    builder.add_heading("05 出海成熟度诊断", 1)
    builder.add_paragraph(_extract(data, "enterprise_basic_situation", "summary", "content", "title"))
    maturity = _get_nested(project, ["metadata", "rule_engine_output", "maturity_assessment"]) or metadata.get("rule_engine_output", {}).get("maturity_assessment", {}) if isinstance(metadata.get("rule_engine_output"), dict) else {}
    rows = [_maturity_row(item) for item in _as_list(maturity.get("dimension_scores", []))]
    if maturity.get("total_score") is not None:
        label = "内部总分" if report_version == "internal" else "成熟度档位"
        rows.insert(0, [label, maturity.get("total_score") if report_version == "internal" else "详见诊断结论", 100 if report_version == "internal" else "-", maturity.get("maturity_level")])
    builder.add_table(["维度", "得分", "满分", "说明"], rows)
    builder.add_heading("短板与改善建议", 2)
    builder.add_bullets(_as_list(_extract(data, "current_shortcomings", "improvement_suggestions", "suggestions") or maturity.get("improvement_suggestions")))


def _add_target_market_analysis(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any], target_markets: list[Any]) -> None:
    data = sections.get("02_overseas_market_selection", {})
    builder.add_heading("06 目标市场分析", 1)
    builder.add_bullets(_as_list(_extract(data, "target_market_analysis", "recommended_country_tiers", "country_tiers") or target_markets))
    builder.add_table(["维度", "分析重点"], [["需求", "市场规模、增长、终端客户画像"], ["准入", "认证、关税、监管、贸易壁垒"], ["竞争", "品牌集中度、替代品、价格带"], ["渠道", "经销商、KA、电商、集成商成熟度"], ["交付", "物流、售后、备件、本地服务要求"]])
    builder.add_paragraph(_extract(data, "recommendation_reason", "recommended_reasons", "reason"))


def _add_country_priority_matrix(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any], target_markets: list[Any]) -> None:
    builder.add_heading("07 国家优先级矩阵", 1)
    data = sections.get("02_overseas_market_selection", {})
    matrix = _extract(data, "country_priority_matrix") or result.get("country_priority_matrix") or target_markets
    builder.add_table(["国家", "优先级", "综合评分", "推荐模式", "机会", "风险"], [_country_row(item) for item in _as_list(matrix)])


def _add_competitor_price_analysis(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    builder.add_heading("08 竞品与价格带分析", 1)
    data = _extract(result, "competitor_price_analysis", "competitor_analysis") or _extract(sections.get("02_overseas_market_selection", {}), "competitor_price_analysis", "competition_analysis")
    rows = [_competitor_row(item) for item in _as_list(data)] if isinstance(data, list) else []
    builder.add_table(["竞品/品牌", "国家/渠道", "价格带", "优势", "启示/需复核"], rows)
    if not rows:
        builder.add_notice(data or "暂无完整竞品价格带数据；建议交付前补充目标国家主流竞品、渠道报价和最终成交价，需人工复核。")


def _add_market_entry_strategy(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("03_entry_mode_design", {})
    builder.add_heading("09 市场进入策略", 1)
    builder.add_table(["进入模式", "适用场景", "建议"], [["经销代理", "快速进入、借助本地资源", _extract(data, "dealer_strategy") or "首年优先筛选2-3家区域经销商"], ["KA/项目直供", "标杆客户明确", _extract(data, "ka_strategy") or "建立英文案例与投标资料"], ["跨境电商/平台", "标准化产品", _extract(data, "ecommerce_strategy") or "适合标准件或低售后复杂度产品"], ["本地化运营", "强售后/准入要求", _extract(data, "localization_strategy") or "达到稳定订单后再布局"]])
    builder.add_paragraph(_extract(data, "recommended_strategy", "content") or _extract(result, "recommended_entry_modes"))


def _add_channel_path(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("03_entry_mode_design", {})
    builder.add_heading("10 渠道路径", 1)
    rows = []
    for title, keys in [("第一阶段", ["first_stage_channel", "phase_1"]), ("第二阶段", ["second_stage_channel", "phase_2"]), ("第三阶段", ["third_stage_layout", "phase_3"] )]:
        rows.append([title, _extract(data, *keys) or _extract(result, "channel_path_design", "recommended_entry_modes")])
    builder.add_table(["阶段", "渠道动作"], rows)


def _add_exhibition_procurement_plan(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("05_exhibition_and_marketing_plan", {})
    builder.add_heading("11 展会与采购对接计划", 1)
    builder.add_table(["事项", "计划"], [["展会策略", _extract(data, "exhibition_strategy")], ["推介会策略", _extract(data, "promotion_event_strategy")], ["采购对接会策略", _extract(data, "procurement_matchmaking_strategy")], ["获客漏斗", _extract(data, "overseas_customer_acquisition_funnel") or result.get("exhibition_and_marketing_plan")]])


def _add_resource_matching(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("04_overseas_resource_matching_plan", {})
    builder.add_heading("12 资源匹配", 1)
    resources = _as_list(_extract(data, "resources", "resource_matches") or result.get("overseas_resource_matches"))
    builder.add_table(["资源", "类型", "国家/地区", "匹配度", "备注"], [_resource_row(item) for item in resources])


def _add_financing_capacity_advice(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("06_financing_and_capacity_expansion_plan", {})
    builder.add_heading("13 融资与扩产建议", 1)
    builder.add_table(["模块", "建议"], [["产能规划", _extract(data, "capacity_plan")], ["融资规划", _extract(data, "financing_plan")], ["资本协同路径", _extract(data, "capital_synergy_path") or result.get("financing_and_capacity_plan")]])


def _add_budget_kpi(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    builder.add_heading("14 预算与 KPI", 1)
    data = _extract(result, "budget_and_kpi", "budget_kpi") or _extract(sections.get("07_12_24_month_implementation_roadmap", {}), "budget_and_kpi", "kpis")
    rows = [_budget_row(item) for item in _as_list(data)] if isinstance(data, list) else []
    builder.add_table(["阶段/项目", "预算", "KPI", "口径/备注"], rows or [["准入准备", "需人工复核", "认证/资料完成率", data or "请结合企业预算补充"], ["渠道拓展", "需人工复核", "有效渠道线索数、样品/报价转化", "建议按国家拆分"], ["订单验证", "需人工复核", "首单金额、复购率、回款周期", "需财务复核"]])


def _add_roadmap(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("07_12_24_month_implementation_roadmap", {})
    builder.add_heading("15 12-24个月路线图", 1)
    roadmap = _extract(data, "roadmap", "implementation_roadmap") or result.get("implementation_roadmap_12_24_months") or []
    builder.add_table(["阶段/时间", "目标", "动作", "责任方", "交付物"], [_roadmap_row(item) for item in _as_list(roadmap)])


def _add_risks(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("08_risk_warnings_and_next_steps", {}) if isinstance(sections, dict) else {}
    builder.add_heading("16 风险与应对", 1)
    risks = _as_list(_extract(data, "risks", "risk_warnings") or result.get("risk_warnings"))
    builder.add_table(["风险类型", "表现", "应对动作"], [_risk_row(item) for item in risks] or [["政策/准入", "目标市场政策、认证和关税变化", "执行前逐项复核最新法规，需人工复核"], ["渠道", "渠道能力与独家条款不确定", "设置试销期与退出机制"], ["汇率/回款", "价格和回款周期波动", "报价预留汇率缓冲并强化信用审核"]])


def _add_data_sources(builder: WordDocumentBuilder, sources: list[dict[str, Any]]) -> None:
    builder.add_heading("17 数据来源", 1)
    builder.add_paragraph("本报告以企业主数据、产品资料、规则引擎/知识库、AI生成内容及外部检索摘要为基础。动态信息应在执行前复核。")
    builder.add_table(["编号", "来源类型", "来源/引用", "可信度/备注"], [[idx + 1, item.get("source_type"), item.get("citation_id") or item.get("title") or item.get("url"), item.get("notes") or item.get("confidence") or ("需人工复核" if item.get("manual_review_required") else "")] for idx, item in enumerate(sources[:50])])


def _add_manual_review_checklist(builder: WordDocumentBuilder, items: list[str]) -> None:
    builder.add_heading("18 人工复核清单", 1)
    rows = [[idx + 1, item, "待复核", "交付/执行负责人"] for idx, item in enumerate(items)]
    builder.add_table(["序号", "需人工复核内容", "状态", "建议责任方"], rows or [[1, "未发现显式复核标记；仍需复核政策、价格、资源联系人、展会档期和预算口径。", "待复核", "项目负责人"]])


def _add_internal_quality_appendix(builder: WordDocumentBuilder, project: dict[str, Any], metadata: dict[str, Any]) -> None:
    builder.add_heading("内部版附录：质量评分与缺失字段", 1)
    quality = metadata.get("quality_review") if isinstance(metadata.get("quality_review"), dict) else {}
    builder.add_table(["项目", "值"], [["质量总分", quality.get("total_score") or metadata.get("quality_score") or "暂无"], ["质量状态", quality.get("status") or metadata.get("quality_status") or "暂无"], ["成熟度分", project.get("final_score") or "暂无"]])
    builder.add_heading("质量问题", 2)
    builder.add_bullets(_as_list(quality.get("issues")))
    readiness = metadata.get("generation_readiness") if isinstance(metadata.get("generation_readiness"), dict) else {}
    rows = []
    for category in readiness.get("missing_categories", []) if isinstance(readiness.get("missing_categories"), list) else []:
        if isinstance(category, dict):
            rows.append([category.get("category"), category.get("fields")])
    builder.add_heading("缺失字段", 2)
    builder.add_table(["类别", "缺失字段"], rows)


def _add_appendix(builder: WordDocumentBuilder, result: dict[str, Any], metadata: dict[str, Any], report_version: str) -> None:
    builder.add_heading("19 附录", 1)
    builder.add_table(["附录项", "内容"], [["生成版本", metadata.get("plan_group_id") or metadata.get("version") or "当前版本"], ["下一步行动", _extract(result.get("sections", {}).get("08_risk_warnings_and_next_steps", {}), "next_action_checklist", "next_actions") or result.get("next_action_suggestions")], ["附注", "客户版不展示内部质量评分；内部版保留评分、缺失字段与复核项用于交付质检。"]])


def _report_sections() -> list[tuple[str, str]]:
    return [
        ("01", "封面"),
        ("02", "目录"),
        ("03", "执行摘要"),
        ("04", "企业与产品画像"),
        ("05", "出海成熟度诊断"),
        ("06", "目标市场分析"),
        ("07", "国家优先级矩阵"),
        ("08", "竞品与价格带分析"),
        ("09", "市场进入策略"),
        ("10", "渠道路径"),
        ("11", "展会与采购对接计划"),
        ("12", "资源匹配"),
        ("13", "融资与扩产建议"),
        ("14", "预算与 KPI"),
        ("15", "12-24个月路线图"),
        ("16", "风险与应对"),
        ("17", "数据来源"),
        ("18", "人工复核清单"),
        ("19", "附录"),
    ]


def _write_docx(path: Path, document_xml: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", _content_types_xml())
        docx.writestr("_rels/.rels", _root_rels_xml())
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", _styles_xml())
        docx.writestr("word/_rels/document.xml.rels", _document_rels_xml())


def _append_export_audit_log(target_dir: Path, record: dict[str, Any]) -> Path:
    audit_path = target_dir / "word_export_audit_log.jsonl"
    with audit_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return audit_path


def _paragraph(text: str, *, style: str | None = None, alignment: str | None = None) -> str:
    p_pr = ""
    if style:
        p_pr += f'<w:pStyle w:val="{style}"/>'
    if alignment:
        p_pr += f'<w:jc w:val="{alignment}"/>'
    return f'<w:p>{f"<w:pPr>{p_pr}</w:pPr>" if p_pr else ""}<w:r>{_run_props() if style == "Title" else ""}<w:t xml:space="preserve">{_escape(text)}</w:t></w:r></w:p>'


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    header_xml = "".join(_cell(header, bold=True, shaded=True) for header in headers)
    row_xml = [f"<w:tr>{header_xml}</w:tr>"]
    for index, row in enumerate(rows):
        cells = list(row)[: len(headers)] + [""] * max(0, len(headers) - len(row))
        row_xml.append("<w:tr>" + "".join(_cell(_stringify(cell), shaded=index % 2 == 1, fill="F7FBFF") for cell in cells) + "</w:tr>")
    tbl_pr = '<w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar><w:tblLook w:val="04A0"/></w:tblPr>'
    return f"<w:tbl>{tbl_pr}{''.join(row_xml)}</w:tbl>"


def _cell(text: Any, *, bold: bool = False, shaded: bool = False, fill: str = "D9EAF7") -> str:
    tc_pr = '<w:tcPr><w:tcW w:w="2400" w:type="dxa"/>' + (f'<w:shd w:fill="{fill}"/>' if shaded else "") + "</w:tcPr>"
    r_pr = '<w:rPr><w:b/></w:rPr>' if bold else ""
    return f'<w:tc>{tc_pr}<w:p><w:r>{r_pr}<w:t xml:space="preserve">{_escape(_stringify(text))}</w:t></w:r></w:p></w:tc>'


def _run_props() -> str:
    return '<w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="38"/></w:rPr>'


def _xml_header() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _content_types_xml() -> str:
    return _xml_header() + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'


def _root_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'


def _document_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'


def _styles_xml() -> str:
    return _xml_header() + '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="38"/><w:color w:val="1F4E79"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="24"/><w:color w:val="5B9BD5"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Notice"><w:name w:val="Notice"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="C00000"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:spacing w:before="360" w:after="160"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="30"/><w:color w:val="1F4E79"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="24"/><w:color w:val="5B9BD5"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="22"/></w:rPr></w:style><w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:left w:val="single" w:sz="4" w:color="BFBFBF"/><w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:right w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/></w:tblBorders></w:tblPr></w:style></w:styles>'


def _extract(data: Any, *keys: str) -> Any:
    if not isinstance(data, dict):
        return data
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
    return None


def _get_nested(data: dict[str, Any], keys: list[str]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _maturity_row(item: Any) -> list[Any]:
    if isinstance(item, dict):
        return [item.get("dimension"), item.get("score"), item.get("max_score"), item.get("comment")]
    return [item, "", "", ""]


def _country_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "需人工复核", "", "", "", ""]
    return [item.get("country_name") or item.get("country"), item.get("priority_rank") or item.get("tier"), item.get("total_score"), item.get("recommended_entry_mode"), item.get("key_opportunities"), item.get("key_risks")]


def _resource_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", ""]
    return [item.get("name") or item.get("resource_name"), item.get("category") or item.get("type") or item.get("resource_type"), item.get("country_name") or item.get("region") or item.get("country"), item.get("match_score") or item.get("priority"), item.get("notes") or item.get("materials_required")]


def _roadmap_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", ""]
    return [item.get("time") or item.get("phase") or item.get("stage"), item.get("goal") or item.get("target"), item.get("actions") or item.get("action"), item.get("owner") or item.get("responsible_party"), item.get("deliverables") or item.get("deliverable")]


def _product_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", "", ""]
    return [item.get("name") or item.get("product_name"), item.get("hs_code"), item.get("certifications") or item.get("certification_status"), item.get("price_band"), item.get("moq") or item.get("lead_time") or item.get("delivery_time"), item.get("capacity") or item.get("monthly_capacity")]


def _competitor_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", "需人工复核"]
    return [item.get("name") or item.get("brand"), item.get("country") or item.get("channel"), item.get("price_band") or item.get("price"), item.get("strength") or item.get("advantages"), item.get("insight") or item.get("notes") or "需人工复核"]


def _budget_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "需人工复核", "", ""]
    return [item.get("phase") or item.get("item"), item.get("budget"), item.get("kpi") or item.get("metrics"), item.get("notes")]


def _risk_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "需人工复核"]
    return [item.get("type") or item.get("risk_type"), item.get("description") or item.get("risk"), item.get("mitigation") or item.get("response") or item.get("action")]


def _collect_data_sources(result: Any, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {"source_type": "enterprise_master_data", "citation_id": "企业主数据", "notes": "来自企业/产品基础信息"},
        {"source_type": "ai_generation", "citation_id": "AI生成报告", "notes": "需人工复核后交付"},
    ]
    if isinstance(result, dict):
        citations = result.get("citations") or result.get("source_references") or []
        sources.extend(item for item in _as_list(citations) if isinstance(item, dict))
        for item in _walk_dicts(result):
            if any(key in item for key in ("citation_id", "source_type", "url", "source")):
                sources.append({k: item.get(k) for k in ("citation_id", "source_type", "url", "title", "notes", "confidence", "manual_review_required") if k in item})
    context_bundle = metadata.get("context_bundle") if isinstance(metadata.get("context_bundle"), dict) else {}
    for item in _walk_dicts(context_bundle):
        if item.get("citation_id") or item.get("source_type"):
            sources.append({k: item.get(k) for k in ("citation_id", "source_type", "title", "url", "notes", "confidence", "manual_review_required") if k in item})
    return _dedupe_sources(sources)


def _collect_manual_review_items(result: Any, metadata: dict[str, Any], *, include_internal_context: bool = False) -> list[str]:
    items: list[str] = []
    if isinstance(result, dict):
        items.extend(_stringify(item) for item in _as_list(result.get("global_manual_review_items")))
        for item in _walk_dicts(result):
            if item.get("manual_review_required") or item.get("citation_id") == "需人工复核" or "需人工复核" in _stringify(item):
                items.append(_stringify(item.get("claim") or item.get("description") or item.get("notes") or item))
    if include_internal_context:
        readiness = metadata.get("generation_readiness") if isinstance(metadata.get("generation_readiness"), dict) else {}
        for category in readiness.get("missing_categories", []) if isinstance(readiness.get("missing_categories"), list) else []:
            if isinstance(category, dict) and category.get("fields"):
                items.append(f"缺失字段需补充：{category.get('category')} - {_stringify(category.get('fields'))}")
        quality = metadata.get("quality_review") if isinstance(metadata.get("quality_review"), dict) else {}
        for issue in _as_list(quality.get("issues")):
            items.append(f"质量问题需复核：{_stringify(issue)}")
    return _dedupe_strings([item for item in items if item and item != "暂无数据"])


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_dicts(child))
    return found


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped = []
    for source in sources:
        key = json.dumps(source, ensure_ascii=False, sort_keys=True)
        if key not in seen and any(source.values()):
            seen.add(key)
            deduped.append(source)
    return deduped


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _normalize_report_version(value: WordReportVersion | str) -> str:
    normalized = str(value or "client").lower()
    if normalized in {"internal", "内部版", "inner"}:
        return "internal"
    return "client"


def _stringify(value: Any) -> str:
    if value is None:
        return "暂无数据"
    if isinstance(value, (list, tuple, set)):
        return "；".join(_stringify(item) for item in value) if value else "暂无数据"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}：{_stringify(item)}")
        return "；".join(parts) if parts else "暂无数据"
    return str(value)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return cleaned[:80] or "企业出海服务正式报告"


def _escape(value: str) -> str:
    return html.escape(value, quote=False)
