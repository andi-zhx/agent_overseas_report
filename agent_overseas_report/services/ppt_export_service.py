"""PowerPoint export utilities for enterprise overseas-plan presentations.

The project stays framework-agnostic and dependency-light, so this module writes
an OOXML ``.pptx`` package directly with the Python standard library.  The deck
uses a consistent business-consulting visual language, widescreen pages, tables
and a priority-matrix table, with Microsoft YaHei font declarations for Chinese
content.
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
DEFAULT_EXPORT_ROOT = Path("/tmp/agent_overseas_report/exports/ppt")
SLIDE_W = 12192000
SLIDE_H = 6858000
FONT = "Microsoft YaHei"


@dataclass(slots=True)
class PPTExportRequest:
    """Input DTO for exporting a completed overseas plan to PowerPoint."""

    project_id: str
    exported_by: str
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    output_dir: str | Path | None = None
    system_name: str = SYSTEM_NAME


@dataclass(slots=True)
class PPTExportResult:
    """Result returned after a PowerPoint export file is written."""

    project_id: str
    plan_name: str
    export_type: str
    file_path: str
    exported_by: str
    exported_at: str


class PPTDeckBuilder:
    """Small PresentationML deck builder with text boxes and compact tables."""

    def __init__(self) -> None:
        self._slides: list[str] = []

    @property
    def slide_count(self) -> int:
        return len(self._slides)

    def add_slide(self, title: str, elements: list[dict[str, Any]]) -> None:
        shape_id = 2
        body: list[str] = [_background(), _title_box(title, shape_id)]
        shape_id += 1
        for element in elements:
            kind = element.get("kind")
            if kind == "bullets":
                body.append(_text_box(element.get("items", []), shape_id, element.get("x", 720000), element.get("y", 1450000), element.get("cx", 5000000), element.get("cy", 4200000), font_size=element.get("font_size", 18)))
            elif kind == "key_values":
                rows = [[item.get("label", ""), item.get("value", "")] for item in element.get("items", [])]
                body.append(_table_box(["关键项", "内容"], rows, shape_id, element.get("x", 720000), element.get("y", 1450000), element.get("cx", 5000000), element.get("cy", 4200000)))
            elif kind == "table":
                body.append(_table_box(element.get("headers", []), element.get("rows", []), shape_id, element.get("x", 720000), element.get("y", 1450000), element.get("cx", 10500000), element.get("cy", 4200000)))
            shape_id += 1
        self._slides.append(_slide_xml("".join(body)))

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as pptx:
            pptx.writestr("[Content_Types].xml", _content_types_xml(len(self._slides)))
            pptx.writestr("_rels/.rels", _root_rels_xml())
            pptx.writestr("ppt/presentation.xml", _presentation_xml(len(self._slides)))
            pptx.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels_xml(len(self._slides)))
            pptx.writestr("ppt/theme/theme1.xml", _theme_xml())
            pptx.writestr("ppt/slideMasters/slideMaster1.xml", _slide_master_xml())
            pptx.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _slide_master_rels_xml())
            pptx.writestr("ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
            pptx.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _slide_layout_rels_xml())
            for index, slide in enumerate(self._slides, start=1):
                pptx.writestr(f"ppt/slides/slide{index}.xml", slide)
                pptx.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", _slide_rels_xml())


def export_overseas_plan_ppt(
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    output_dir: str | Path | None = None,
    exported_by: str,
    system_name: str = SYSTEM_NAME,
    exported_at: datetime | None = None,
) -> PPTExportResult:
    """Generate and save the enterprise overseas solution PowerPoint deck."""

    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    plan_name = f"{enterprise_name}出海解决方案"
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    file_name = f"{_safe_filename(plan_name)}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.pptx"
    file_path = target_dir / file_name

    builder = PPTDeckBuilder()
    _build_deck(builder, project=project, enterprise=enterprise, plan_name=plan_name, system_name=system_name, generated_at=exported_at)
    builder.write(file_path)

    return PPTExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="PPT",
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
    )


def _build_deck(builder: PPTDeckBuilder, *, project: dict[str, Any], enterprise: dict[str, Any], plan_name: str, system_name: str, generated_at: datetime) -> None:
    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    target_markets = project.get("target_countries") or []
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id")
    industry = project.get("selected_industry") or enterprise.get("industry")

    builder.add_slide(
        f"《{plan_name}》",
        [
            {"kind": "key_values", "x": 850000, "y": 1700000, "cx": 5200000, "cy": 3600000, "items": [
                {"label": "企业名称", "value": enterprise_name},
                {"label": "所属行业", "value": industry},
                {"label": "目标国家", "value": target_markets},
                {"label": "生成日期", "value": generated_at.strftime("%Y-%m-%d")},
                {"label": "生成系统", "value": system_name},
            ]},
            {"kind": "bullets", "x": 6800000, "y": 2000000, "cx": 4000000, "cy": 3000000, "font_size": 22, "items": ["以市场优先级为牵引", "以渠道资源对接为抓手", "以12-24个月落地目标为闭环"]},
        ],
    )

    overview = sections.get("00_solution_overview", {}) if isinstance(sections, dict) else {}
    maturity = _get_nested(project, ["metadata", "rule_engine_output", "maturity_assessment"]) or {}
    matrix = _as_list(_extract(sections.get("02_overseas_market_selection", {}), "country_priority_matrix") or result.get("country_priority_matrix") or [])
    best_country = (_country_name(matrix[0]) if matrix else None) or _stringify(target_markets[:1])
    entry_modes = _extract(result, "recommended_entry_modes", "channel_path_design") or _extract(sections.get("03_entry_mode_design", {}), "first_stage_channel")
    builder.add_slide("建议以优先市场突破带动12-24个月出海增长", [{"kind": "key_values", "items": [
        {"label": "企业当前阶段", "value": maturity.get("maturity_level") or project.get("maturity_level") or _extract(overview, "current_stage")},
        {"label": "推荐目标市场", "value": best_country},
        {"label": "推荐进入模式", "value": entry_modes or "经销代理 + 展会获客 + KA试点"},
        {"label": "核心资源对接方向", "value": "渠道资源、认证/技术资源、供应链服务、政府/商协会"},
        {"label": "12-24个月目标", "value": _extract(overview, "target_12_24_months") or "完成重点市场样板客户、渠道体系和本地化能力建设"},
    ]}])

    diag = sections.get("01_enterprise_diagnosis", {}) if isinstance(sections, dict) else {}
    builder.add_slide("企业出海基础具备，但需补齐本地化运营能力", [
        {"kind": "key_values", "x": 650000, "y": 1400000, "cx": 5100000, "cy": 4200000, "items": [
            {"label": "企业基础情况", "value": _extract(diag, "enterprise_basic_situation", "summary", "content") or f"{enterprise_name}｜{industry}"},
            {"label": "产品竞争力", "value": _extract(diag, "product_competitiveness_analysis", "product_analysis")},
            {"label": "出海成熟度评分", "value": _score_text(maturity)},
        ]},
        {"kind": "table", "x": 6200000, "y": 1400000, "cx": 5000000, "cy": 3900000, "headers": ["维度", "得分", "说明"], "rows": [_maturity_row(item) for item in _as_list(maturity.get("dimension_scores"))][:5]},
    ])

    product = _extract(result, "product_competitiveness_analysis") or _extract(diag, "product_competitiveness_analysis", "product_analysis") or {}
    builder.add_slide("产品竞争力应聚焦技术、成本与交付三类可验证优势", [{"kind": "table", "headers": ["分析维度", "核心判断", "建议动作"], "rows": [
        ["技术壁垒", _extract(product, "technical_barrier", "技术壁垒") or "梳理专利、认证、检测报告等硬证明", "形成英文技术包"],
        ["成本优势", _extract(product, "cost_advantage", "成本优势") or "对标目标市场主流价格带", "建立FOB/CIF报价模型"],
        ["交付能力", _extract(product, "delivery_capability", "交付能力") or "明确产能、交期、MOQ与售后SLA", "输出交付承诺清单"],
        ["产品差异化", _extract(product, "differentiation", "产品差异化") or "提炼本地客户可感知卖点", "制作场景化案例"],
        ["品牌能力", _extract(product, "brand_capability", "品牌能力") or "完善官网、物料、客户背书", "搭建海外品牌资产"],
    ]}])

    market = sections.get("02_overseas_market_selection", {}) if isinstance(sections, dict) else {}
    builder.add_slide("目标市场选择以需求、政策、竞争、渠道和供应链五维打分", [
        {"kind": "table", "x": 600000, "y": 1350000, "cx": 5200000, "cy": 3900000, "headers": ["五维模型", "评价重点"], "rows": [["市场潜力", "需求规模、增长速度、客户匹配度"], ["政策环境", "准入、关税、认证和合规稳定性"], ["竞争强度", "竞品密度、价格带和替代风险"], ["渠道成熟", "经销、KA、电商和服务商可得性"], ["供应链适配", "物流、仓储、售后和备件体系"]]},
        {"kind": "key_values", "x": 6400000, "y": 1350000, "cx": 5000000, "cy": 3900000, "items": [
            {"label": "一级市场", "value": _extract(market, "tier_1", "primary_markets") or best_country},
            {"label": "二级市场", "value": _extract(market, "tier_2", "secondary_markets") or target_markets[1:3]},
            {"label": "长期市场", "value": _extract(market, "long_term_markets") or "认证周期长但战略价值高的区域"},
        ]},
    ])

    builder.add_slide("国家优先级矩阵显示应先攻高潜力、低到中难度市场", [{"kind": "table", "headers": ["推荐国家", "市场潜力(X)", "进入难度(Y)", "优先级", "推荐进入模式", "关键提示"], "rows": [_matrix_row(item, idx) for idx, item in enumerate(matrix or target_markets, start=1)]}])

    entry = sections.get("03_entry_mode_design", {}) if isinstance(sections, dict) else {}
    builder.add_slide("出海模式采用先轻后重、先渠道后本地化的分阶段路径", [{"kind": "table", "headers": ["模式", "适用场景", "阶段定位"], "rows": [
        ["经销代理", "快速验证市场和客户需求", "1-6个月优先启动"],
        ["跨境电商", "标准化产品、线上获客可行", "作为线索补充渠道"],
        ["本地KA渠道", "大客户明确且交付稳定", "6-12个月打造样板"],
        ["海外合资/办事处", "需要售后、仓储或本地团队", "12-24个月评估落地"],
        ["分阶段进入路径", _extract(entry, "first_stage_channel", "phase_1") or "展会获客→渠道试销→KA样板→本地化运营", "滚动复盘"],
    ]}])

    resources = _as_list(_extract(sections.get("04_overseas_resource_matching_plan", {}), "resources", "resource_matches") or result.get("overseas_resource_matches"))
    builder.add_slide("海外资源对接围绕渠道、技术、供应链和公共资源形成闭环", [{"kind": "table", "headers": ["资源方向", "对接重点", "近期动作"], "rows": [
        ["渠道资源", _resource_summary(resources, "channel") or "经销商、代理商、本地KA采购负责人", "建立长名单并分级拜访"],
        ["技术资源", _resource_summary(resources, "technology") or "认证、检测、售后服务和本地适配伙伴", "确认准入差距"],
        ["供应链资源", _resource_summary(resources, "supply") or "物流、仓储、备件和代工协同", "核算交付成本"],
        ["政府/商协会资源", _resource_summary(resources, "government") or "商协会、园区、投促机构和使领馆商务资源", "争取推介和背书"],
    ]}])

    marketing = sections.get("05_exhibition_and_marketing_plan", {}) if isinstance(sections, dict) else {}
    builder.add_slide("市场推广以展会获客为入口，形成线索到订单的漏斗", [{"kind": "table", "headers": ["推广动作", "核心安排", "产出指标"], "rows": [
        ["推荐展会", _extract(marketing, "recommended_exhibitions", "exhibition_strategy") or "选择目标国行业头部展及区域专业展", "有效线索/渠道面谈"],
        ["推介会", _extract(marketing, "promotion_event_strategy") or "联合商协会、园区或使领馆商务渠道举办", "样板客户邀约"],
        ["采购对接会", _extract(marketing, "procurement_matchmaking_strategy") or "匹配KA采购、集成商和本地代理", "报价/样品需求"],
        ["海外获客漏斗", _extract(marketing, "overseas_customer_acquisition_funnel") or "曝光→线索→资质审核→样品/报价→订单", "转化率复盘"],
    ]}])

    finance = sections.get("06_financing_and_capacity_expansion_plan", {}) if isinstance(sections, dict) else {}
    builder.add_slide("投融资与扩产规划应与订单验证节奏匹配", [{"kind": "table", "headers": ["阶段", "产能/资金安排", "关键判断"], "rows": [
        ["初期", _extract(finance, "initial_stage") or "国内代工/现有产线 + 银行授信", "以轻资产验证市场"],
        ["中期", _extract(finance, "mid_stage") or "新增产线/柔性产能 + 产业基金", "以订单确定扩产节奏"],
        ["后期", _extract(finance, "late_stage") or "海外工厂/仓储中心 + 战略融资", "以本地交付能力提升份额"],
    ]}])

    roadmap = _as_list(_extract(sections.get("07_12_24_month_implementation_roadmap", {}), "roadmap", "implementation_roadmap") or result.get("implementation_roadmap_12_24_months"))
    builder.add_slide("12-24个月路线图以市场验证、渠道转化和本地化落地递进", [{"kind": "table", "headers": ["时间", "目标", "关键动作", "交付物"], "rows": _roadmap_rows(roadmap)}])

    risk = sections.get("08_risk_warnings_and_next_steps", {}) if isinstance(sections, dict) else {}
    risks = _as_list(_extract(risk, "risks", "risk_warnings") or result.get("risk_warnings"))
    builder.add_slide("近期应优先控制准入、渠道、汇率与交付风险", [
        {"kind": "table", "x": 600000, "y": 1350000, "cx": 5400000, "cy": 3900000, "headers": ["主要风险", "应对动作"], "rows": _risk_rows(risks)},
        {"kind": "bullets", "x": 6500000, "y": 1350000, "cx": 4700000, "cy": 3900000, "items": _as_list(_extract(risk, "next_action_checklist", "next_actions") or result.get("next_action_suggestions"))[:6] or ["确认重点国家准入差距", "建立渠道资源长名单", "准备英文产品与报价材料", "排期首轮客户/代理访谈"]},
    ])


def _background() -> str:
    return '<p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F9FC"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'


def _title_box(text: str, shape_id: int) -> str:
    return _shape(texts=[text], shape_id=shape_id, name="Slide Title", x=600000, y=320000, cx=10800000, cy=720000, font_size=30, bold=True, color="17365D", fill=None)


def _text_box(items: list[Any], shape_id: int, x: int, y: int, cx: int, cy: int, *, font_size: int = 18) -> str:
    texts = _as_list(items) or ["暂无数据，建议后续补充。"]
    return _shape(texts=[_stringify(item) for item in texts], shape_id=shape_id, name="Bullets", x=x, y=y, cx=cx, cy=cy, font_size=font_size, bullet=True, fill="FFFFFF")


def _shape(*, texts: list[str], shape_id: int, name: str, x: int, y: int, cx: int, cy: int, font_size: int, bold: bool = False, color: str = "263238", fill: str | None = "FFFFFF", bullet: bool = False) -> str:
    fill_xml = '<a:noFill/>' if fill is None else f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
    paragraphs = []
    for text in texts:
        p_pr = '<a:pPr marL="300000" indent="-180000"><a:buChar char="•"/></a:pPr>' if bullet else '<a:pPr/>'
        paragraphs.append(f'<a:p>{p_pr}<a:r><a:rPr lang="zh-CN" sz="{font_size * 100}" b="{1 if bold else 0}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr><a:t>{_escape(text)}</a:t></a:r></a:p>')
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{_escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>{fill_xml}<a:ln><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="160000" tIns="100000" rIns="160000" bIns="100000"/><a:lstStyle/>{''.join(paragraphs)}</p:txBody></p:sp>'''


def _table_box(headers: list[str], rows: list[list[Any]], shape_id: int, x: int, y: int, cx: int, cy: int) -> str:
    headers = headers or ["项目", "内容"]
    normalized_rows = rows or [["暂无数据"] + [""] * (len(headers) - 1)]
    col_w = max(800000, int(cx / len(headers)))
    grid = "".join(f'<a:gridCol w="{col_w}"/>' for _ in headers)
    row_xml = [_table_row(headers, header=True)]
    row_xml.extend(_table_row(list(row)[: len(headers)] + [""] * max(0, len(headers) - len(row))) for row in normalized_rows[:8])
    return f'''<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId></a:tblPr><a:tblGrid>{grid}</a:tblGrid>{''.join(row_xml)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'''


def _table_row(cells: list[Any], *, header: bool = False) -> str:
    fill = "17365D" if header else "FFFFFF"
    color = "FFFFFF" if header else "263238"
    bold = 1 if header else 0
    return '<a:tr h="520000">' + ''.join(f'<a:tc><a:txBody><a:bodyPr wrap="square" lIns="70000" tIns="50000" rIns="70000" bIns="50000"/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="1300" b="{bold}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr><a:t>{_escape(_stringify(cell))}</a:t></a:r></a:p></a:txBody><a:tcPr><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:lnL><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnL><a:lnR><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnR><a:lnT><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnT><a:lnB><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnB></a:tcPr></a:tc>' for cell in cells) + '</a:tr>'


def _slide_xml(body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{body}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''


def _content_types_xml(slide_count: int) -> str:
    overrides = ''.join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, slide_count + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>{overrides}</Types>'''


def _root_rels_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>'


def _presentation_xml(slide_count: int) -> str:
    slide_ids = ''.join(f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{slide_count + 1}"/></p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/><p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle/></p:presentation>'''


def _presentation_rels_xml(slide_count: int) -> str:
    rels = ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1, slide_count + 1))
    rels += f'<Relationship Id="rId{slide_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    rels += f'<Relationship Id="rId{slide_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'


def _slide_rels_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'


def _slide_master_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'''


def _slide_master_rels_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>'


def _slide_layout_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'


def _slide_layout_rels_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>'


def _theme_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Consulting"><a:themeElements><a:clrScheme name="Consulting"><a:dk1><a:srgbClr val="1F2933"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="17365D"/></a:dk2><a:lt2><a:srgbClr val="F7F9FC"/></a:lt2><a:accent1><a:srgbClr val="17365D"/></a:accent1><a:accent2><a:srgbClr val="2F75B5"/></a:accent2><a:accent3><a:srgbClr val="70AD47"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4><a:accent5><a:srgbClr val="A5A5A5"/></a:accent5><a:accent6><a:srgbClr val="ED7D31"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Chinese"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:majorFont><a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''


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
    if not isinstance(item, dict):
        return [item, "", ""]
    return [item.get("dimension"), f"{item.get('score', '')}/{item.get('max_score', '')}", item.get("comment")]


def _score_text(maturity: dict[str, Any]) -> str:
    if not maturity:
        return "暂无评分，建议结合规则引擎补充。"
    score = maturity.get("total_score", "暂无")
    level = maturity.get("maturity_level", "待判定")
    return f"{score}/100（{level}）"


def _country_name(item: Any) -> str:
    if isinstance(item, dict):
        return _stringify(item.get("country_name") or item.get("country") or item.get("country_code"))
    return _stringify(item)


def _matrix_row(item: Any, idx: int) -> list[Any]:
    if not isinstance(item, dict):
        return [item, "待评估", "待评估", idx, "经销代理/展会获客", "需补充市场评分"]
    potential = item.get("market_potential") or item.get("total_score") or _dimension_score(item, "market")
    difficulty = item.get("entry_difficulty") or item.get("difficulty") or _difficulty_from_score(item.get("total_score"))
    return [_country_name(item), potential, difficulty, item.get("priority_rank") or idx, item.get("recommended_entry_mode"), item.get("key_opportunities") or item.get("key_risks")]


def _dimension_score(item: dict[str, Any], keyword: str) -> Any:
    for score in _as_list(item.get("dimension_scores")):
        if isinstance(score, dict) and keyword in _stringify(score.get("dimension")).lower():
            return score.get("score")
    return "待评估"


def _difficulty_from_score(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "中"
    if value >= 80:
        return "低-中"
    if value >= 60:
        return "中"
    return "中-高"


def _resource_summary(resources: list[Any], keyword: str) -> str | None:
    matched = [item for item in resources if keyword in _stringify(item).lower()]
    return _stringify(matched[:3]) if matched else None


def _roadmap_rows(roadmap: list[Any]) -> list[list[Any]]:
    fallback = [
        ["1-3个月", "完成出海准备", "市场验证、认证差距、渠道长名单", "诊断报告/资源清单"],
        ["3-6个月", "启动渠道验证", "代理访谈、展会报名、样品测试", "合作意向/线索池"],
        ["6-9个月", "形成样板订单", "KA推进、报价谈判、交付复盘", "样板客户/订单"],
        ["9-12个月", "搭建区域渠道", "经销协议、售后伙伴、备件方案", "渠道体系"],
        ["12-24个月", "评估本地化布局", "办事处/仓储/合资可研", "本地化落地方案"],
    ]
    if not roadmap:
        return fallback
    rows = []
    for item in roadmap[:5]:
        if isinstance(item, dict):
            rows.append([item.get("time") or item.get("phase") or item.get("stage"), item.get("goal") or item.get("target"), item.get("actions") or item.get("action"), item.get("deliverables") or item.get("deliverable")])
        else:
            rows.append([item, "", "", ""])
    return rows


def _risk_rows(risks: list[Any]) -> list[list[Any]]:
    if not risks:
        return [["政策/准入风险", "提前核验认证、关税和本地监管要求"], ["渠道风险", "对代理商做资质、客户和回款能力筛选"], ["汇率风险", "采用报价有效期、结算币种和套保机制"], ["供应链风险", "建立交期、备件和售后服务预案"]]
    rows = []
    for item in risks[:5]:
        if isinstance(item, dict):
            rows.append([item.get("type") or item.get("risk") or item.get("name"), item.get("mitigation") or item.get("action") or item.get("description")])
        else:
            rows.append([item, "制定责任人和跟踪机制"])
    return rows


def _stringify(value: Any) -> str:
    if value is None:
        return "暂无数据"
    if isinstance(value, (list, tuple, set)):
        return "；".join(_stringify(item) for item in value) if value else "暂无数据"
    if isinstance(value, dict):
        return "；".join(f"{key}：{_stringify(item)}" for key, item in value.items()) if value else "暂无数据"
    return str(value)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return cleaned[:80] or "企业出海解决方案"


def _escape(value: str) -> str:
    return html.escape(value, quote=False)
