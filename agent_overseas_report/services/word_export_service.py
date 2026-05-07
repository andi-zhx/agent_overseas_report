"""Word export utilities for enterprise overseas-plan documents.

The project does not depend on a web framework yet, so this module builds a
minimal OOXML ``.docx`` package with the Python standard library.  The generated
file is compatible with Microsoft Word/WPS and uses Chinese-capable East Asian
font declarations.
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SYSTEM_NAME = "企业出海方案智能生成系统"
DEFAULT_EXPORT_ROOT = Path("/tmp/agent_overseas_report/exports/word")


@dataclass(slots=True)
class WordExportRequest:
    """Input DTO for exporting a completed overseas plan to Word."""

    project_id: str
    exported_by: str
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


class WordDocumentBuilder:
    """Small OOXML document builder with headings, paragraphs and tables."""

    def __init__(self) -> None:
        self._body: list[str] = []

    def add_title(self, text: str) -> None:
        self._body.append(_paragraph(text, style="Title", alignment="center"))

    def add_heading(self, text: str, level: int = 1) -> None:
        style = "Heading1" if level == 1 else "Heading2"
        self._body.append(_paragraph(text, style=style))

    def add_paragraph(self, text: Any) -> None:
        self._body.append(_paragraph(_stringify(text)))

    def add_bullets(self, items: list[Any]) -> None:
        if not items:
            self.add_paragraph("暂无数据，建议后续补充。")
            return
        for item in items:
            self._body.append(_paragraph(f"• {_stringify(item)}"))

    def add_table(self, headers: list[str], rows: list[list[Any]]) -> None:
        normalized_rows = rows or [["暂无数据"] + ["" for _ in headers[1:]]]
        self._body.append(_table(headers, normalized_rows))

    def add_page_break(self) -> None:
        self._body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def build_xml(self) -> str:
        sect_pr = (
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" '
            'w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
        )
        return _xml_header() + f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' f'<w:body>{"".join(self._body)}{sect_pr}</w:body></w:document>'


def export_overseas_plan_word(
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    output_dir: str | Path | None = None,
    exported_by: str,
    system_name: str = SYSTEM_NAME,
    exported_at: datetime | None = None,
) -> WordExportResult:
    """Generate and save the enterprise overseas solution Word document."""

    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    plan_name = f"{enterprise_name}企业出海解决方案"
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{_safe_filename(plan_name)}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.docx"
    file_path = target_dir / file_name

    builder = WordDocumentBuilder()
    _build_document(builder, project=project, enterprise=enterprise, plan_name=plan_name, system_name=system_name, generated_at=exported_at)
    _write_docx(file_path, builder.build_xml())

    return WordExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="Word",
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
    )


def _build_document(
    builder: WordDocumentBuilder,
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    plan_name: str,
    system_name: str,
    generated_at: datetime,
) -> None:
    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    target_markets = project.get("target_countries") or []

    builder.add_title(f"《{plan_name}》")
    builder.add_paragraph("企业名称：" + _stringify(enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id")))
    builder.add_paragraph("所属行业：" + _stringify(project.get("selected_industry") or enterprise.get("industry")))
    builder.add_paragraph("目标市场：" + _stringify(target_markets))
    builder.add_paragraph("生成日期：" + generated_at.strftime("%Y-%m-%d"))
    builder.add_paragraph("生成机构/系统名称：" + system_name)
    builder.add_page_break()

    builder.add_heading("目录", 1)
    for item in [
        "1. 企业现状诊断",
        "2. 海外市场选择",
        "3. 出海模式设计",
        "4. 海外资源对接方案",
        "5. 展会与市场推广计划",
        "6. 投融资与扩产规划",
        "7. 12-24个月实施路线图",
        "8. 风险提示与下一步建议",
    ]:
        builder.add_paragraph(item)
    builder.add_page_break()

    _section_01(builder, sections, enterprise, project)
    _section_02(builder, sections, result, target_markets)
    _section_03(builder, sections, result)
    _section_04(builder, sections, result)
    _section_05(builder, sections, result)
    _section_06(builder, sections, result)
    _section_07(builder, sections, result)
    _section_08(builder, sections, result)


def _section_01(builder: WordDocumentBuilder, sections: dict[str, Any], enterprise: dict[str, Any], project: dict[str, Any]) -> None:
    data = sections.get("01_enterprise_diagnosis", {})
    builder.add_heading("01 企业现状诊断", 1)
    builder.add_heading("企业基础情况", 2)
    builder.add_table(["项目", "内容"], [["企业名称", enterprise.get("name")], ["所属行业", project.get("selected_industry") or enterprise.get("industry")], ["已选产品", project.get("product_ids")], ["目标市场", project.get("target_countries")]])
    builder.add_paragraph(_extract(data, "enterprise_basic_situation", "summary", "content", "title"))
    builder.add_heading("产品竞争力分析", 2)
    builder.add_paragraph(_extract(data, "product_competitiveness_analysis", "product_analysis", "analysis"))
    builder.add_heading("出海成熟度评估表", 2)
    maturity = _get_nested(project, ["metadata", "rule_engine_output", "maturity_assessment"]) or {}
    rows = [_maturity_row(item) for item in _as_list(maturity.get("dimension_scores", []))]
    if maturity.get("total_score") is not None:
        rows.insert(0, ["总分", maturity.get("total_score"), 100, maturity.get("maturity_level")])
    builder.add_table(["维度", "得分", "满分", "说明"], rows)
    builder.add_heading("当前短板与改善建议", 2)
    builder.add_bullets(_as_list(_extract(data, "current_shortcomings", "improvement_suggestions", "suggestions") or maturity.get("improvement_suggestions")))


def _section_02(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any], target_markets: list[Any]) -> None:
    data = sections.get("02_overseas_market_selection", {})
    builder.add_heading("02 海外市场选择", 1)
    builder.add_heading("推荐国家分层", 2)
    builder.add_bullets(_as_list(_extract(data, "recommended_country_tiers", "country_tiers") or target_markets))
    builder.add_heading("国家选择五维模型", 2)
    builder.add_table(["维度", "评价重点"], [["市场需求", "需求规模、增长潜力、客户匹配度"], ["政策环境", "贸易准入、产业政策、关税与合规"], ["竞争环境", "竞品强度、价格带与差异化空间"], ["渠道成熟度", "经销、KA、电商、服务商成熟度"], ["供应链适配", "物流、仓储、制造协同与售后适配性"]])
    builder.add_heading("国家优先级矩阵表", 2)
    matrix = _extract(data, "country_priority_matrix") or result.get("country_priority_matrix") or []
    builder.add_table(["国家", "优先级", "综合评分", "推荐模式", "机会", "风险"], [_country_row(item) for item in _as_list(matrix)])
    builder.add_heading("推荐理由", 2)
    builder.add_paragraph(_extract(data, "recommendation_reason", "recommended_reasons", "reason"))


def _section_03(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("03_entry_mode_design", {})
    builder.add_heading("03 出海模式设计", 1)
    builder.add_heading("渠道模式四分法", 2)
    builder.add_table(["模式", "适用场景"], [["经销代理", "快速进入市场、借助本地客户资源"], ["KA/大客户直供", "标杆客户明确、交付能力稳定"], ["跨境电商/平台", "标准品、低客单或适合线上获客"], ["本地化运营", "需要售后、认证、仓储或本地团队支撑"]])
    for title, keys in [("第一阶段渠道", ["first_stage_channel", "phase_1"]), ("第二阶段渠道", ["second_stage_channel", "phase_2"]), ("第三阶段布局", ["third_stage_layout", "phase_3"] )]:
        builder.add_heading(title, 2)
        builder.add_paragraph(_extract(data, *keys) or _extract(result, "channel_path_design", "recommended_entry_modes"))


def _section_04(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("04_overseas_resource_matching_plan", {})
    builder.add_heading("04 海外资源对接方案", 1)
    resources = _as_list(_extract(data, "resources", "resource_matches") or result.get("overseas_resource_matches"))
    for title, category in [("渠道资源", "channel"), ("技术资源", "technology"), ("供应链资源", "supply_chain"), ("政府/商协会资源", "government")]:
        builder.add_heading(title, 2)
        filtered = [item for item in resources if category in _stringify(item).lower()] or _as_list(_extract(data, title, title.replace("/", "_")))
        builder.add_bullets(filtered[:5])
    builder.add_heading("资源对接优先级", 2)
    builder.add_table(["资源", "类型", "国家/地区", "匹配度", "备注"], [_resource_row(item) for item in resources])


def _section_05(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("05_exhibition_and_marketing_plan", {})
    builder.add_heading("05 展会与市场推广计划", 1)
    for title, keys in [("展会策略", ["exhibition_strategy"]), ("推介会策略", ["promotion_event_strategy"]), ("采购对接会策略", ["procurement_matchmaking_strategy"]), ("海外获客漏斗", ["overseas_customer_acquisition_funnel"] )]:
        builder.add_heading(title, 2)
        builder.add_paragraph(_extract(data, *keys) or result.get("exhibition_and_marketing_plan"))


def _section_06(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("06_financing_and_capacity_expansion_plan", {})
    builder.add_heading("06 投融资与扩产规划", 1)
    for title, keys in [("产能规划", ["capacity_plan"]), ("融资规划", ["financing_plan"]), ("资本协同路径", ["capital_synergy_path"] )]:
        builder.add_heading(title, 2)
        builder.add_paragraph(_extract(data, *keys) or result.get("financing_and_capacity_plan"))


def _section_07(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("07_12_24_month_implementation_roadmap", {})
    builder.add_heading("07 12-24个月实施路线图", 1)
    roadmap = _extract(data, "roadmap", "implementation_roadmap") or result.get("implementation_roadmap_12_24_months") or []
    builder.add_table(["阶段/时间", "目标", "动作", "责任方", "交付物"], [_roadmap_row(item) for item in _as_list(roadmap)])


def _section_08(builder: WordDocumentBuilder, sections: dict[str, Any], result: dict[str, Any]) -> None:
    data = sections.get("08_risk_warnings_and_next_steps", {}) if isinstance(sections, dict) else {}
    builder.add_heading("08 风险提示与下一步建议", 1)
    risks = _as_list(_extract(data, "risks", "risk_warnings") or result.get("risk_warnings"))
    risk_labels = [("政策风险", "policy"), ("渠道风险", "channel"), ("汇率风险", "exchange"), ("认证风险", "certification"), ("供应链风险", "supply")]
    for title, key in risk_labels:
        builder.add_heading(title, 2)
        matched = [item for item in risks if key in _stringify(item).lower() or title[:2] in _stringify(item)]
        builder.add_bullets(matched[:3] or ["请结合目标市场最新政策、合同条款和本地服务能力持续跟踪。"])
    builder.add_heading("下一步行动清单", 2)
    builder.add_bullets(_as_list(_extract(data, "next_action_checklist", "next_actions") or result.get("next_action_suggestions")))


def _write_docx(path: Path, document_xml: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", _content_types_xml())
        docx.writestr("_rels/.rels", _root_rels_xml())
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", _styles_xml())
        docx.writestr("word/_rels/document.xml.rels", _document_rels_xml())


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
    for row in rows:
        cells = list(row)[: len(headers)] + [""] * max(0, len(headers) - len(row))
        row_xml.append("<w:tr>" + "".join(_cell(_stringify(cell)) for cell in cells) + "</w:tr>")
    tbl_pr = '<w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:tblLook w:val="04A0"/></w:tblPr>'
    return f"<w:tbl>{tbl_pr}{''.join(row_xml)}</w:tbl>"


def _cell(text: Any, *, bold: bool = False, shaded: bool = False) -> str:
    tc_pr = '<w:tcPr><w:tcW w:w="2400" w:type="dxa"/>' + ('<w:shd w:fill="D9EAF7"/>' if shaded else '') + '</w:tcPr>'
    r_pr = '<w:rPr><w:b/></w:rPr>' if bold else ''
    return f'<w:tc>{tc_pr}<w:p><w:r>{r_pr}<w:t xml:space="preserve">{_escape(_stringify(text))}</w:t></w:r></w:p></w:tc>'


def _run_props() -> str:
    return '<w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="36"/></w:rPr>'


def _xml_header() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _content_types_xml() -> str:
    return _xml_header() + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'


def _root_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'


def _document_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'


def _styles_xml() -> str:
    return _xml_header() + '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="36"/><w:color w:val="1F4E79"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:spacing w:before="360" w:after="160"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="30"/><w:color w:val="1F4E79"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:b/><w:sz w:val="24"/><w:color w:val="5B9BD5"/></w:rPr></w:style><w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:left w:val="single" w:sz="4" w:color="BFBFBF"/><w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:right w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/></w:tblBorders></w:tblPr></w:style></w:styles>'


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
        return [item, "", "", "", "", ""]
    return [item.get("country_name") or item.get("country"), item.get("priority_rank") or item.get("tier"), item.get("total_score"), item.get("recommended_entry_mode"), item.get("key_opportunities"), item.get("key_risks")]


def _resource_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", ""]
    return [item.get("name"), item.get("category") or item.get("type"), item.get("country_name") or item.get("region"), item.get("match_score"), item.get("notes")]


def _roadmap_row(item: Any) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "", "", "", ""]
    return [item.get("time") or item.get("phase") or item.get("stage"), item.get("goal") or item.get("target"), item.get("actions") or item.get("action"), item.get("owner") or item.get("responsible_party"), item.get("deliverables") or item.get("deliverable")]


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
    return cleaned[:80] or "企业出海解决方案"


def _escape(value: str) -> str:
    return html.escape(value, quote=False)
