"""PowerPoint export utilities for consulting-style overseas-plan decks.

This module intentionally writes a dependency-light OOXML ``.pptx`` package
with the Python standard library.  The generated deck is not a Word clone: it
is a 20-page, presentation-ready client briefing with conclusion-style slide
titles, scorecards, matrices, tables and 12/24-month roadmaps.
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
DEFAULT_EXPORT_ROOT = Path("/tmp/agent_overseas_report/exports/ppt")
SLIDE_W = 12192000
SLIDE_H = 6858000
FONT = "Microsoft YaHei"
PPTReportVersion = Literal["client", "internal"]
DEFAULT_THEME_COLOR = "17365D"
DEFAULT_ACCENT_COLOR = "2F75B5"


@dataclass(slots=True)
class PPTExportRequest:
    """Input DTO for exporting a completed overseas plan to PowerPoint."""

    project_id: str
    exported_by: str
    report_version: PPTReportVersion | str = "client"
    logo_text: str | None = None
    theme_color: str = DEFAULT_THEME_COLOR
    footer_text: str | None = None
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
    report_version: str = "client"
    slide_count: int = 0
    audit_log_path: str | None = None


class PPTDeckBuilder:
    """Small PresentationML deck builder with consulting-style primitives."""

    def __init__(self, *, theme_color: str = DEFAULT_THEME_COLOR, footer_text: str | None = None, logo_text: str | None = None) -> None:
        self._slides: list[str] = []
        self.theme_color = _normalize_hex_color(theme_color, DEFAULT_THEME_COLOR)
        self.footer_text = footer_text or ""
        self.logo_text = logo_text or ""

    @property
    def slide_count(self) -> int:
        return len(self._slides)

    def add_slide(self, title: str, elements: list[dict[str, Any]]) -> None:
        shape_id = 2
        body: list[str] = [_background(), _title_box(title, shape_id, self.theme_color)]
        shape_id += 1
        if self.logo_text:
            body.append(_label_box(self.logo_text, shape_id, 10200000, 300000, 1300000, 360000, font_size=11, color=self.theme_color))
            shape_id += 1
        for element in elements:
            kind = element.get("kind")
            if kind == "bullets":
                body.append(
                    _text_box(
                        element.get("items", []),
                        shape_id,
                        element.get("x", 720000),
                        element.get("y", 1450000),
                        element.get("cx", 5000000),
                        element.get("cy", 4200000),
                        font_size=element.get("font_size", 18),
                    )
                )
            elif kind == "key_values":
                rows = [[item.get("label", ""), item.get("value", "")] for item in element.get("items", [])]
                body.append(_table_box(["关键项", "内容"], rows, shape_id, element.get("x", 720000), element.get("y", 1450000), element.get("cx", 5000000), element.get("cy", 4200000), theme_color=self.theme_color))
            elif kind == "table":
                body.append(_table_box(element.get("headers", []), element.get("rows", []), shape_id, element.get("x", 720000), element.get("y", 1450000), element.get("cx", 10500000), element.get("cy", 4200000), theme_color=self.theme_color))
            elif kind == "note":
                body.append(_label_box(_stringify(element.get("text")), shape_id, element.get("x", 720000), element.get("y", 5600000), element.get("cx", 10500000), element.get("cy", 420000), font_size=element.get("font_size", 12), color=element.get("color", "6B7280"), fill=element.get("fill", "EEF3F8")))
            shape_id += 1
        body.append(_footer_box(self.footer_text, self.slide_count + 1, shape_id, self.theme_color))
        self._slides.append(_slide_xml("".join(body)))

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as pptx:
            pptx.writestr("[Content_Types].xml", _content_types_xml(len(self._slides)))
            pptx.writestr("_rels/.rels", _root_rels_xml())
            pptx.writestr("ppt/presentation.xml", _presentation_xml(len(self._slides)))
            pptx.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels_xml(len(self._slides)))
            pptx.writestr("ppt/theme/theme1.xml", _theme_xml(self.theme_color))
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
    report_version: PPTReportVersion | str = "client",
    logo_text: str | None = None,
    theme_color: str = DEFAULT_THEME_COLOR,
    footer_text: str | None = None,
) -> PPTExportResult:
    """Generate and save the enterprise overseas solution PowerPoint deck."""

    normalized_version = _normalize_report_version(report_version)
    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    plan_name = f"{enterprise_name}出海客户汇报稿"
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    suffix = "内部版" if normalized_version == "internal" else "客户版"
    file_name = f"{_safe_filename(plan_name)}_{suffix}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.pptx"
    file_path = target_dir / file_name

    configured_footer = footer_text or f"{system_name}｜{suffix}｜{enterprise_name}"
    configured_logo = logo_text or enterprise.get("logo_text") or enterprise_name[:8]
    builder = PPTDeckBuilder(theme_color=theme_color, footer_text=configured_footer, logo_text=configured_logo)
    _build_deck(
        builder,
        project=project,
        enterprise=enterprise,
        plan_name=plan_name,
        system_name=system_name,
        generated_at=exported_at,
        report_version=normalized_version,
    )
    builder.write(file_path)
    audit_log_path = _append_export_audit_log(
        target_dir,
        {
            "project_id": str(project["id"]),
            "plan_name": plan_name,
            "export_type": "PPT",
            "report_version": normalized_version,
            "slide_count": builder.slide_count,
            "file_path": str(file_path),
            "exported_by": exported_by,
            "exported_at": exported_at_iso,
            "system_name": system_name,
            "theme_color": builder.theme_color,
            "footer_text": configured_footer,
            "logo_text": configured_logo,
        },
    )

    return PPTExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="PPT",
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
        report_version=normalized_version,
        slide_count=builder.slide_count,
        audit_log_path=str(audit_log_path),
    )


def _build_deck(builder: PPTDeckBuilder, *, project: dict[str, Any], enterprise: dict[str, Any], plan_name: str, system_name: str, generated_at: datetime, report_version: str) -> None:
    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    metadata = project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    target_markets = project.get("target_countries") or []
    products = _products(project, metadata)
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id")
    industry = project.get("selected_industry") or enterprise.get("industry")
    overview = sections.get("00_solution_overview", {}) if isinstance(sections, dict) else {}
    diag = sections.get("01_enterprise_diagnosis", {}) if isinstance(sections, dict) else {}
    market = sections.get("02_overseas_market_selection", {}) if isinstance(sections, dict) else {}
    entry = sections.get("03_entry_mode_design", {}) if isinstance(sections, dict) else {}
    resources_section = sections.get("04_overseas_resource_matching_plan", {}) if isinstance(sections, dict) else {}
    marketing = sections.get("05_exhibition_and_marketing_plan", {}) if isinstance(sections, dict) else {}
    finance = sections.get("06_financing_and_capacity_expansion_plan", {}) if isinstance(sections, dict) else {}
    roadmap_section = sections.get("07_12_24_month_implementation_roadmap", {}) if isinstance(sections, dict) else {}
    risk = sections.get("08_risk_warnings_and_next_steps", {}) if isinstance(sections, dict) else {}
    maturity = _get_nested(project, ["metadata", "rule_engine_output", "maturity_assessment"]) or {}
    matrix = _as_list(_extract(market, "country_priority_matrix") or result.get("country_priority_matrix") or [])
    resources = _as_list(_extract(resources_section, "resources", "resource_matches") or result.get("overseas_resource_matches"))
    roadmap = _as_list(_extract(roadmap_section, "roadmap", "implementation_roadmap") or result.get("implementation_roadmap_12_24_months"))
    best_country = (_country_name(matrix[0]) if matrix else None) or _stringify(target_markets[:1])
    entry_modes = _extract(result, "recommended_entry_modes", "channel_path_design") or _extract(entry, "first_stage_channel") or "经销代理 + 展会获客 + KA试点"
    version_label = "内部评审版" if report_version == "internal" else "客户沟通版"

    builder.add_slide(f"本次汇报建议以{best_country}为突破口推进{enterprise_name}出海增长", [
        {"kind": "key_values", "x": 780000, "y": 1550000, "cx": 5000000, "cy": 3500000, "items": [
            {"label": "汇报对象", "value": version_label}, {"label": "企业名称", "value": enterprise_name}, {"label": "所属行业", "value": industry}, {"label": "目标国家", "value": target_markets}, {"label": "生成日期", "value": generated_at.strftime("%Y-%m-%d")},
        ]},
        {"kind": "bullets", "x": 6400000, "y": 1700000, "cx": 4600000, "cy": 3000000, "font_size": 22, "items": ["用机会判断统一方向", "用评分与矩阵确定优先级", "用资源与路线图驱动落地"]},
    ])
    builder.add_slide(f"核心结论是先验证{best_country}样板市场，再复制到第二梯队国家", [{"kind": "table", "headers": ["结论", "依据", "管理动作"], "rows": [
        ["优先市场", best_country, "集中资源完成首轮渠道和客户验证"],
        ["进入模式", entry_modes, "先轻资产获客，订单稳定后再本地化"],
        ["能力短板", _score_text(maturity), "补齐认证、渠道、售后与英文资料"],
        ["增长目标", _extract(overview, "target_12_24_months") or "12个月形成样板订单，24个月形成区域渠道体系", "月度复盘KPI"],
    ]}])
    builder.add_slide("企业出海机会来自目标市场需求增长与中国产能交付优势叠加", [{"kind": "table", "headers": ["机会来源", "判断", "验证方式"], "rows": [
        ["需求端", _extract(market, "market_demand", "demand_trend") or "目标国家存在效率提升、替代升级或成本优化需求", "客户访谈/招标需求/进口数据复核"],
        ["供给端", _extract(diag, "product_competitiveness_analysis") or "产品具备成本、交付或技术参数优势", "竞品参数与报价对标"],
        ["渠道端", _extract(entry, "channel_opportunity") or "可通过代理、展会和KA采购快速建立触点", "渠道长名单拜访"],
        ["政策端", _extract(market, "policy_opportunity") or "需动态核验准入、关税与补贴政策", "政策/认证复核"],
    ]}])
    builder.add_slide("企业与产品画像显示应将可证明卖点转化为海外客户语言", [
        {"kind": "key_values", "x": 600000, "y": 1380000, "cx": 5200000, "cy": 4100000, "items": [{"label": "企业基础", "value": _extract(diag, "enterprise_basic_situation", "summary") or f"{enterprise_name}｜{industry}"}, {"label": "核心产品", "value": [p.get("name") for p in products] or enterprise.get("core_products")}, {"label": "认证/资质", "value": enterprise.get("certifications") or _product_values(products, "certifications")}]},
        {"kind": "table", "x": 6200000, "y": 1380000, "cx": 5200000, "cy": 4100000, "headers": ["产品", "卖点", "价格/MOQ"], "rows": _product_rows(products)},
    ])
    builder.add_slide("出海成熟度评分表明当前适合以可控试点推进而非一次性重资产投入", [{"kind": "table", "headers": ["维度", "得分", "说明"], "rows": [_maturity_row(item) for item in _as_list(maturity.get("dimension_scores"))] or _default_maturity_rows(maturity)}])
    builder.add_slide("目标国家优先级矩阵显示应先攻高潜力、低到中难度市场", [{"kind": "table", "headers": ["推荐国家", "市场潜力(X)", "进入难度(Y)", "优先级", "推荐进入模式", "关键提示"], "rows": [_matrix_row(item, idx) for idx, item in enumerate(matrix or target_markets, start=1)]}])
    builder.add_slide("目标市场规模与增长需要以外部数据复核后纳入滚动决策", [{"kind": "table", "headers": ["国家/区域", "规模判断", "增长判断", "数据复核动作"], "rows": _market_size_rows(matrix or target_markets, market)}])
    builder.add_slide("竞品与价格带分析应锁定可打赢的中高性价比细分区间", [{"kind": "table", "headers": ["竞品/价格带", "当前判断", "我方打法"], "rows": _competitor_rows(products, result, market)}])
    builder.add_slide("客户与渠道结构决定先做经销商筛选和KA样板客户并行推进", [{"kind": "table", "headers": ["客户/渠道", "优先级", "判断逻辑", "推进动作"], "rows": _channel_rows(enterprise, products, entry)}])
    builder.add_slide("推荐进入模式是经销代理打底、展会获客加速、KA试点建立标杆", [{"kind": "table", "headers": ["模式", "适用场景", "阶段定位", "退出/升级条件"], "rows": _entry_mode_rows(entry_modes, entry)}])
    builder.add_slide("渠道推进路径应以长名单筛选到试销协议再到区域独家逐级收敛", [{"kind": "table", "headers": ["阶段", "渠道动作", "筛选标准", "输出"], "rows": _channel_path_rows(entry)}])
    builder.add_slide("展会、推介会和采购对接要服务于可量化线索漏斗", [{"kind": "table", "headers": ["活动", "核心安排", "目标对象", "产出指标"], "rows": _marketing_rows(marketing)}])
    builder.add_slide("海外资源匹配要围绕渠道、认证、供应链和公共资源形成闭环", [{"kind": "table", "headers": ["资源方向", "对接重点", "近期动作"], "rows": _resource_rows(resources)}])
    builder.add_slide("合规与政策风险是进入节奏的前置约束而非事后补救事项", [{"kind": "table", "headers": ["风险类别", "影响", "前置应对"], "rows": _compliance_rows(risk, products)}])
    builder.add_slide("融资与扩产路径应跟随订单验证和渠道确定性分阶段释放", [{"kind": "table", "headers": ["阶段", "产能/资金安排", "触发条件", "关键判断"], "rows": _finance_rows(finance)}])
    builder.add_slide("预算与KPI应聚焦线索、渠道、样品、订单和回款五类指标", [{"kind": "table", "headers": ["模块", "预算口径", "核心KPI", "复盘频率"], "rows": _budget_kpi_rows(finance, marketing)}])
    builder.add_slide("12个月路线图应完成准备、验证、样板订单和渠道体系四个里程碑", [{"kind": "table", "headers": ["时间", "目标", "关键动作", "交付物"], "rows": _roadmap_rows(roadmap, horizon="12m")}])
    builder.add_slide("24个月路线图应从单点订单扩展为区域运营和本地化能力", [{"kind": "table", "headers": ["时间", "目标", "关键动作", "交付物"], "rows": _roadmap_rows(roadmap, horizon="24m")}])
    builder.add_slide("关键风险应通过红黄绿灯机制明确责任人和止损条件", [{"kind": "table", "x": 600000, "y": 1350000, "cx": 5600000, "cy": 3900000, "headers": ["主要风险", "等级", "应对动作"], "rows": _risk_rows(_as_list(_extract(risk, "risks", "risk_warnings") or result.get("risk_warnings")))}, {"kind": "bullets", "x": 6600000, "y": 1450000, "cx": 4500000, "cy": 3300000, "items": ["红灯：暂停投入并复核准入/回款", "黄灯：限定预算推进验证", "绿灯：进入渠道复制和产能评估"]}])
    next_actions = _as_list(_extract(risk, "next_action_checklist", "next_actions") or result.get("next_action_suggestions"))[:6]
    internal_note = ["内部版需同步跟踪毛利、授信、渠道返利和资源真实性复核"] if report_version == "internal" else ["客户版建议下一步召开资源对接启动会并确认首批试点国家"]
    builder.add_slide("下一步应在30天内完成市场复核、渠道长名单和首轮客户访谈", [{"kind": "table", "headers": ["优先动作", "责任建议", "完成时点"], "rows": _next_action_rows(next_actions)}, {"kind": "note", "text": internal_note[0]}])


def _products(project: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    payload = metadata.get("enterprise_payload") if isinstance(metadata.get("enterprise_payload"), dict) else {}
    products = payload.get("products") or project.get("products") or []
    return [item for item in products if isinstance(item, dict)]


def _product_values(products: list[dict[str, Any]], key: str) -> list[Any]:
    return [product.get(key) for product in products if product.get(key)]


def _product_rows(products: list[dict[str, Any]]) -> list[list[Any]]:
    if not products:
        return [["核心产品", "需补充核心卖点、认证、价格带", "待补充"]]
    return [[p.get("name"), p.get("core_selling_points") or p.get("application_scenarios"), p.get("price_range") or p.get("moq")] for p in products[:5]]


def _default_maturity_rows(maturity: dict[str, Any]) -> list[list[Any]]:
    return [["综合成熟度", _score_text(maturity), "建议通过规则引擎和人工访谈补充维度评分"], ["市场准备", "待评估", "补充目标市场数据"], ["渠道准备", "待评估", "建立渠道长名单"], ["合规准备", "待评估", "复核认证与准入"]]


def _market_size_rows(markets: list[Any], market_section: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for item in markets[:5]:
        if isinstance(item, dict):
            rows.append([_country_name(item), item.get("market_size") or item.get("market_potential") or "待复核", item.get("growth_rate") or item.get("growth") or "待复核", "使用行业报告/海关数据/客户访谈三角验证"])
        else:
            rows.append([item, _extract(market_section, "market_size") or "待复核", _extract(market_section, "growth_rate") or "待复核", "补充公开数据和一手访谈"])
    return rows or [["目标市场", "待复核", "待复核", "补充数据来源"]]


def _competitor_rows(products: list[dict[str, Any]], result: dict[str, Any], market: dict[str, Any]) -> list[list[Any]]:
    competitors = _as_list(_extract(market, "competitors", "competitive_landscape") or result.get("competitors") or _product_values(products, "competitors"))
    rows = []
    for item in competitors[:5]:
        rows.append([item, "价格/参数/渠道需逐项对标", "用性价比、交期和服务响应切入"])
    if not rows:
        rows = [["头部国际品牌", "高品牌溢价、渠道成熟", "避开正面价格战，切入细分场景"], ["本地中小品牌", "服务近但产品迭代慢", "用交付和技术参数建立替代"], ["中国同类出口商", "价格竞争明显", "用认证、案例和售后区分"]]
    return rows


def _channel_rows(enterprise: dict[str, Any], products: list[dict[str, Any]], entry: dict[str, Any]) -> list[list[Any]]:
    channel_requirements = enterprise.get("channel_requirements") if isinstance(enterprise.get("channel_requirements"), dict) else {}
    targets = _product_values(products, "target_customers") or channel_requirements.get("target_customers") or []
    return [["经销商/代理商", "高", _extract(entry, "dealer_fit") or "适合快速覆盖区域客户", "筛选10-30家并完成访谈"], ["KA/采购商", "高", _stringify(targets) if targets else "适合建立样板客户", "锁定3-5家试点"], ["服务商/集成商", "中", "提升售后和方案能力", "签署合作备忘录"], ["线上线索", "中", "作为低成本补充获客", "官网/询盘/内容投放联动"]]


def _entry_mode_rows(entry_modes: Any, entry: dict[str, Any]) -> list[list[Any]]:
    return [["经销代理", "快速验证市场和客户需求", "1-6个月优先启动", "连续订单与回款稳定后升级"], ["展会获客", "行业客户集中、产品需现场演示", "贯穿前12个月", "线索转化率低则调整展会"], ["KA试点", "目标客户明确且交付稳定", "6-12个月打造样板", "样板可复制后扩展区域"], ["办事处/仓储", "售后或交付半径要求高", "12-24个月评估", "订单密度覆盖固定成本"], ["综合建议", entry_modes, _extract(entry, "phase_1") or "先轻后重", _extract(entry, "phase_2") or "滚动复盘"]]


def _channel_path_rows(entry: dict[str, Any]) -> list[list[Any]]:
    return [["长名单", "商协会/展会/平台搜集", "品类匹配、区域覆盖、客户资源", "30家候选"], ["短名单", "资质访谈与背景核验", "历史订单、团队、回款能力", "10家优先对象"], ["试销", "样品、报价、联合拜访", "线索质量、响应速度", "3-5家试销协议"], ["区域合作", "年度目标和返利机制", "订单达成和服务能力", "区域渠道体系"]]


def _marketing_rows(marketing: dict[str, Any]) -> list[list[Any]]:
    return [["推荐展会", _extract(marketing, "recommended_exhibitions", "exhibition_strategy") or "选择目标国行业头部展及区域专业展", "代理商/KA/集成商", "有效线索与会面数"], ["推介会", _extract(marketing, "promotion_event_strategy") or "联合商协会、园区或使领馆商务渠道举办", "重点客户与公共资源", "样板客户邀约"], ["采购对接会", _extract(marketing, "procurement_matchmaking_strategy") or "匹配KA采购、集成商和本地代理", "采购负责人", "报价/样品需求"], ["线索漏斗", _extract(marketing, "overseas_customer_acquisition_funnel") or "曝光→线索→资质审核→样品/报价→订单", "全渠道", "转化率复盘"]]


def _resource_rows(resources: list[Any]) -> list[list[Any]]:
    return [["渠道资源", _resource_summary(resources, "channel") or "经销商、代理商、本地KA采购负责人", "建立长名单并分级拜访"], ["认证/技术资源", _resource_summary(resources, "cert") or _resource_summary(resources, "technology") or "认证、检测、售后服务和本地适配伙伴", "确认准入差距"], ["供应链资源", _resource_summary(resources, "supply") or "物流、仓储、备件和代工协同", "核算交付成本"], ["政府/商协会资源", _resource_summary(resources, "government") or "商协会、园区、投促机构和使领馆商务资源", "争取推介和背书"]]


def _compliance_rows(risk: dict[str, Any], products: list[dict[str, Any]]) -> list[list[Any]]:
    requirements = _product_values(products, "compliance_requirements")
    return [["认证/准入", _stringify(requirements) if requirements else "认证周期可能影响首单", "建立认证差距清单和责任人"], ["关税/贸易政策", _extract(risk, "tariff_risk") or "关税、原产地和贸易管制需动态复核", "报价前复核HS编码和税费"], ["数据/标签/售后", _extract(risk, "regulatory_risk") or "本地标签、质保和售后要求可能增加成本", "纳入报价和合同条款"], ["合同/回款", _extract(risk, "payment_risk") or "跨境收款和信用风险需前置控制", "信用证/预付款/保险组合"]]


def _finance_rows(finance: dict[str, Any]) -> list[list[Any]]:
    return [["初期", _extract(finance, "initial_stage") or "现有产线 + 银行授信", "线索转样品/小单", "以轻资产验证市场"], ["中期", _extract(finance, "mid_stage") or "柔性产能 + 周转资金", "样板订单和渠道协议", "以订单确定扩产节奏"], ["后期", _extract(finance, "late_stage") or "海外仓/办事处 + 战略融资", "区域订单密度稳定", "以本地交付提升份额"]]


def _budget_kpi_rows(finance: dict[str, Any], marketing: dict[str, Any]) -> list[list[Any]]:
    return [["市场验证", _extract(marketing, "budget") or "展会/差旅/物料/翻译", "有效线索、客户访谈、样品需求", "双周"], ["渠道开发", "代理尽调、样品、联合拜访", "短名单、试销协议、渠道订单", "月度"], ["合规认证", "检测、认证、标签/说明书", "认证差距关闭率", "月度"], ["产能交付", _extract(finance, "capex_budget") or "备货、物流、售后备件", "准交率、毛利、回款周期", "月度"]]


def _roadmap_rows(roadmap: list[Any], *, horizon: str) -> list[list[Any]]:
    fallback_12 = [["1-3个月", "完成出海准备", "市场验证、认证差距、渠道长名单", "诊断报告/资源清单"], ["3-6个月", "启动渠道验证", "代理访谈、展会报名、样品测试", "合作意向/线索池"], ["6-9个月", "形成样板订单", "KA推进、报价谈判、交付复盘", "样板客户/订单"], ["9-12个月", "搭建区域渠道", "经销协议、售后伙伴、备件方案", "渠道体系"]]
    fallback_24 = [["12-15个月", "复制样板客户", "扩展第二梯队国家和渠道", "复制打法包"], ["15-18个月", "完善服务网络", "售后伙伴、备件与培训", "服务SLA"], ["18-21个月", "评估本地化投入", "海外仓/办事处/合资可研", "本地化方案"], ["21-24个月", "形成区域经营闭环", "预算、团队和渠道年度规划", "24个月复盘报告"]]
    if not roadmap:
        return fallback_12 if horizon == "12m" else fallback_24
    rows = []
    for item in roadmap[:4] if horizon == "12m" else roadmap[4:8]:
        if isinstance(item, dict):
            rows.append([item.get("time") or item.get("time_range") or item.get("phase") or item.get("stage"), item.get("goal") or item.get("core_goal") or item.get("target"), item.get("actions") or item.get("key_actions") or item.get("action"), item.get("deliverables") or item.get("deliverable")])
        else:
            rows.append([item, "", "", ""])
    return rows or (fallback_12 if horizon == "12m" else fallback_24)


def _risk_rows(risks: list[Any]) -> list[list[Any]]:
    if not risks:
        return [["政策/准入风险", "黄", "提前核验认证、关税和本地监管要求"], ["渠道风险", "黄", "对代理商做资质、客户和回款能力筛选"], ["汇率风险", "绿", "采用报价有效期、结算币种和套保机制"], ["供应链风险", "黄", "建立交期、备件和售后服务预案"]]
    rows = []
    for item in risks[:5]:
        if isinstance(item, dict):
            rows.append([item.get("type") or item.get("risk") or item.get("name"), item.get("level") or "黄", item.get("mitigation") or item.get("action") or item.get("description")])
        else:
            rows.append([item, "黄", "制定责任人和跟踪机制"])
    return rows


def _next_action_rows(actions: list[Any]) -> list[list[Any]]:
    defaults = ["确认重点国家准入差距", "建立渠道资源长名单", "准备英文产品与报价材料", "排期首轮客户/代理访谈"]
    values = actions or defaults
    return [[action, "海外业务部/项目组", f"T+{(idx + 1) * 7}天"] for idx, action in enumerate(values[:6])]


def _append_export_audit_log(target_dir: Path, record: dict[str, Any]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    audit_path = target_dir / "ppt_export_audit_log.jsonl"
    with audit_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return audit_path


def _background() -> str:
    return '<p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F9FC"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'


def _title_box(text: str, shape_id: int, theme_color: str) -> str:
    return _shape(texts=[text], shape_id=shape_id, name="Slide Title", x=600000, y=300000, cx=9800000, cy=760000, font_size=28, bold=True, color=theme_color, fill=None)


def _footer_box(footer_text: str, slide_no: int, shape_id: int, theme_color: str) -> str:
    text = f"{footer_text}｜{slide_no:02d}" if footer_text else f"{slide_no:02d}"
    return _label_box(text, shape_id, 600000, 6320000, 10800000, 280000, font_size=9, color="6B7280", fill=None, line_color=theme_color)


def _label_box(text: str, shape_id: int, x: int, y: int, cx: int, cy: int, *, font_size: int = 12, color: str = "263238", fill: str | None = "FFFFFF", line_color: str = "D7DEE8") -> str:
    return _shape(texts=[text], shape_id=shape_id, name="Label", x=x, y=y, cx=cx, cy=cy, font_size=font_size, bold=False, color=color, fill=fill, bullet=False, line_color=line_color)


def _text_box(items: list[Any], shape_id: int, x: int, y: int, cx: int, cy: int, *, font_size: int = 18) -> str:
    texts = _as_list(items) or ["暂无数据，建议后续补充。"]
    return _shape(texts=[_stringify(item) for item in texts], shape_id=shape_id, name="Bullets", x=x, y=y, cx=cx, cy=cy, font_size=font_size, bullet=True, fill="FFFFFF")


def _shape(*, texts: list[str], shape_id: int, name: str, x: int, y: int, cx: int, cy: int, font_size: int, bold: bool = False, color: str = "263238", fill: str | None = "FFFFFF", bullet: bool = False, line_color: str = "D7DEE8") -> str:
    fill_xml = '<a:noFill/>' if fill is None else f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
    paragraphs = []
    for text in texts:
        p_pr = '<a:pPr marL="300000" indent="-180000"><a:buChar char="•"/></a:pPr>' if bullet else '<a:pPr/>'
        paragraphs.append(f'<a:p>{p_pr}<a:r><a:rPr lang="zh-CN" sz="{font_size * 100}" b="{1 if bold else 0}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr><a:t>{_escape(text)}</a:t></a:r></a:p>')
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{_escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>{fill_xml}<a:ln><a:solidFill><a:srgbClr val="{line_color}"/></a:solidFill></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="140000" tIns="80000" rIns="140000" bIns="80000"/><a:lstStyle/>{''.join(paragraphs)}</p:txBody></p:sp>'''


def _table_box(headers: list[str], rows: list[list[Any]], shape_id: int, x: int, y: int, cx: int, cy: int, *, theme_color: str) -> str:
    headers = headers or ["项目", "内容"]
    normalized_rows = rows or [["暂无数据"] + [""] * (len(headers) - 1)]
    col_w = max(800000, int(cx / len(headers)))
    grid = "".join(f'<a:gridCol w="{col_w}"/>' for _ in headers)
    row_xml = [_table_row(headers, header=True, theme_color=theme_color)]
    row_xml.extend(_table_row(list(row)[: len(headers)] + [""] * max(0, len(headers) - len(row)), theme_color=theme_color) for row in normalized_rows[:8])
    return f'''<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId></a:tblPr><a:tblGrid>{grid}</a:tblGrid>{''.join(row_xml)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'''


def _table_row(cells: list[Any], *, header: bool = False, theme_color: str = DEFAULT_THEME_COLOR) -> str:
    fill = theme_color if header else "FFFFFF"
    color = "FFFFFF" if header else "263238"
    bold = 1 if header else 0
    return '<a:tr h="500000">' + ''.join(f'<a:tc><a:txBody><a:bodyPr wrap="square" lIns="65000" tIns="45000" rIns="65000" bIns="45000"/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="1250" b="{bold}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr><a:t>{_escape(_stringify(cell))}</a:t></a:r></a:p></a:txBody><a:tcPr><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:lnL><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnL><a:lnR><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnR><a:lnT><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnT><a:lnB><a:solidFill><a:srgbClr val="D7DEE8"/></a:solidFill></a:lnB></a:tcPr></a:tc>' for cell in cells) + '</a:tr>'


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


def _theme_xml(theme_color: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Consulting"><a:themeElements><a:clrScheme name="Consulting"><a:dk1><a:srgbClr val="1F2933"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="{theme_color}"/></a:dk2><a:lt2><a:srgbClr val="F7F9FC"/></a:lt2><a:accent1><a:srgbClr val="{theme_color}"/></a:accent1><a:accent2><a:srgbClr val="{DEFAULT_ACCENT_COLOR}"/></a:accent2><a:accent3><a:srgbClr val="70AD47"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4><a:accent5><a:srgbClr val="A5A5A5"/></a:accent5><a:accent6><a:srgbClr val="ED7D31"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Chinese"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:majorFont><a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'''


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
    return [_country_name(item), potential, difficulty, item.get("priority_rank") or idx, item.get("recommended_entry_mode") or "经销代理/展会获客", item.get("key_opportunities") or item.get("key_risks")]


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
    return cleaned[:80] or "企业出海客户汇报稿"


def _normalize_report_version(value: PPTReportVersion | str) -> str:
    normalized = str(value or "client").lower()
    if normalized in {"internal", "内部版", "inner"}:
        return "internal"
    return "client"


def _normalize_hex_color(value: str | None, default: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", value or "")[:6].upper()
    return cleaned if len(cleaned) == 6 else default


def _escape(value: str) -> str:
    return html.escape(value, quote=False)
