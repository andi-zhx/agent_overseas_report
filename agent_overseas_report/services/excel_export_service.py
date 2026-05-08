"""Excel export utilities for enterprise overseas-plan management workbooks.

The project intentionally avoids coupling exports to a web framework.  This
module writes standards-compliant ``.xlsx`` files with the Python standard
library so the generated workbooks can be opened by Microsoft Excel/WPS, support
Chinese text, and do not interfere with upstream enterprise/product Excel
import/export modules.
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


SYSTEM_NAME = "企业出海方案智能生成系统"
DEFAULT_EXPORT_ROOT = Path("/tmp/agent_overseas_report/exports/excel")
MISSING_RESOURCE_NAME = "待补充/需人工确认"
MANAGEMENT_WORKBOOK_SHEET_NAME = "项目执行管理总表"


class ExcelExportKind(str, Enum):
    """Supported overseas-plan Excel workbook types."""

    MANAGEMENT_WORKBOOK = "management_workbook"
    ACTION_PLAN = "action_plan"
    RESOURCE_LIST = "resource_list"


@dataclass(slots=True)
class ExcelExportRequest:
    """Input DTO for exporting overseas-plan Excel workbooks."""

    project_id: str
    exported_by: str
    export_kind: ExcelExportKind | str = ExcelExportKind.MANAGEMENT_WORKBOOK
    report_version: str = "client"
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    output_dir: str | Path | None = None
    system_name: str = SYSTEM_NAME


@dataclass(slots=True)
class ExcelExportResult:
    """Result returned after an Excel export file is written."""

    project_id: str
    plan_name: str
    export_type: str
    export_kind: str
    sheet_name: str
    file_path: str
    exported_by: str
    exported_at: str
    headers: list[str]
    rows: list[dict[str, str]]
    sheet_names: list[str]
    sheets: dict[str, dict[str, Any]]


@dataclass(slots=True)
class WorksheetSpec:
    """Normalized worksheet payload used by the XLSX writer."""

    name: str
    headers: list[str]
    rows: list[dict[str, str]]


ACTION_PLAN_HEADERS = ["阶段", "时间范围", "核心目标", "关键动作", "负责人", "所需资源", "交付物", "优先级", "状态", "备注"]
RESOURCE_LIST_HEADERS = ["资源类型", "国家/地区", "资源名称", "建议对接对象", "对接目的", "优先级", "所属阶段", "需要准备的材料", "当前状态", "备注"]
ENTERPRISE_HEADERS = ["企业ID", "企业名称", "所属行业", "海外客户", "英文资料", "国际化团队", "出海预算", "授信额度", "备注"]
PRODUCT_HEADERS = ["产品ID", "产品名称", "HS编码", "认证资质", "产能", "MOQ", "价格带", "海外版本", "备注"]
COUNTRY_MATRIX_HEADERS = ["国家/地区", "优先级", "总分", "市场需求", "政策环境", "竞争环境", "渠道成熟度", "供应链适配", "推荐进入模式", "关键机会", "关键风险", "数据来源", "备注"]
EVENT_PLAN_HEADERS = ["活动类型", "国家/地区", "活动/展会名称", "时间", "目标", "负责人", "预算", "优先级", "状态", "备注"]
COMPLIANCE_HEADERS = ["事项类型", "国家/地区", "认证/合规事项", "适用产品", "责任人", "截止时间", "当前状态", "风险等级", "数据来源", "备注"]
BUDGET_HEADERS = ["预算项目", "国家/地区", "阶段", "假设", "金额", "币种", "负责人", "备注"]
KPI_HEADERS = ["KPI指标", "目标值", "当前值", "数据来源", "统计周期", "负责人", "状态", "备注"]
RISK_HEADERS = ["风险类别", "国家/地区", "风险描述", "影响", "概率", "等级", "应对措施", "负责人", "状态", "备注"]
DATA_SOURCE_HEADERS = ["来源类型", "来源名称", "引用ID/链接", "适用Sheet", "更新时间", "可信度", "备注"]
REVIEW_HEADERS = ["复核事项", "关联Sheet", "优先级", "负责人", "截止时间", "状态", "复核要点", "备注"]
EXPORT_RECORD_HEADERS = ["项目ID", "方案名称", "导出类型", "导出用途", "导出人", "导出时间", "系统名称", "文件路径"]


_ACTION_ALIASES: dict[str, tuple[str, ...]] = {
    "阶段": ("阶段", "stage", "phase", "milestone"),
    "时间范围": ("时间范围", "time_range", "timeframe", "time", "period", "duration"),
    "核心目标": ("核心目标", "core_goal", "goal", "target", "objective"),
    "关键动作": ("关键动作", "key_actions", "actions", "action", "tasks", "initiatives"),
    "负责人": ("负责人", "responsible_party", "owner", "responsible", "department"),
    "所需资源": ("所需资源", "required_resources", "resources", "resource_needs", "support"),
    "交付物": ("交付物", "deliverables", "deliverable", "outputs", "output"),
    "优先级": ("优先级", "priority", "priority_level"),
    "状态": ("状态", "status", "current_status"),
    "备注": ("备注", "notes", "remark", "remarks", "comment"),
}
_RESOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "资源类型": ("资源类型", "resource_type", "type", "category", "subtype"),
    "国家/地区": ("国家/地区", "country_region", "country_name", "country", "region", "market"),
    "资源名称": ("资源名称", "resource_name", "name", "organization", "institution", "company"),
    "建议对接对象": ("建议对接对象", "suggested_contact", "contact", "contact_name", "target_contact", "department"),
    "对接目的": ("对接目的", "purpose", "matching_purpose", "objective", "goal"),
    "优先级": ("优先级", "priority", "priority_level"),
    "所属阶段": ("所属阶段", "stage", "phase", "related_stage"),
    "需要准备的材料": ("需要准备的材料", "materials", "required_materials", "preparation_materials", "documents"),
    "当前状态": ("当前状态", "current_status", "status"),
    "备注": ("备注", "notes", "remark", "remarks", "comment"),
}


def export_overseas_plan_excel(
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    export_kind: ExcelExportKind | str = ExcelExportKind.MANAGEMENT_WORKBOOK,
    output_dir: str | Path | None = None,
    exported_by: str,
    system_name: str = SYSTEM_NAME,
    exported_at: datetime | None = None,
) -> ExcelExportResult:
    """Generate and save one project execution/internal-management workbook."""

    kind = ExcelExportKind(export_kind)
    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    plan_name = f"{enterprise_name}{MANAGEMENT_WORKBOOK_SHEET_NAME}"
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{_safe_filename(plan_name)}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = target_dir / file_name

    worksheets = build_management_workbook_sheets(
        project=project,
        enterprise=enterprise,
        exported_by=exported_by,
        exported_at_iso=exported_at_iso,
        system_name=system_name,
        file_path=str(file_path),
        plan_name=plan_name,
    )
    _write_xlsx(file_path, worksheets=worksheets, system_name=system_name)

    primary = _primary_sheet_for_kind(kind, worksheets)
    sheets = {sheet.name: {"headers": sheet.headers, "rows": sheet.rows} for sheet in worksheets}
    return ExcelExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="Excel",
        export_kind=kind.value,
        sheet_name=primary.name,
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
        headers=primary.headers,
        rows=primary.rows,
        sheet_names=[sheet.name for sheet in worksheets],
        sheets=sheets,
    )


def build_management_workbook_sheets(
    *,
    project: dict[str, Any],
    enterprise: dict[str, Any],
    exported_by: str,
    exported_at_iso: str,
    system_name: str,
    file_path: str,
    plan_name: str,
) -> list[WorksheetSpec]:
    """Build all execution-management worksheets with clear table headers."""

    export_record = [{
        "项目ID": str(project.get("id", "")),
        "方案名称": plan_name,
        "导出类型": "Excel",
        "导出用途": "项目执行和内部管理",
        "导出人": exported_by,
        "导出时间": exported_at_iso,
        "系统名称": system_name,
        "文件路径": file_path,
    }]
    return [
        WorksheetSpec("企业基础信息", ENTERPRISE_HEADERS, extract_enterprise_rows(project, enterprise)),
        WorksheetSpec("产品基础信息", PRODUCT_HEADERS, extract_product_rows(project)),
        WorksheetSpec("目标国家评分矩阵", COUNTRY_MATRIX_HEADERS, extract_country_matrix_rows(project)),
        WorksheetSpec("渠道资源清单", RESOURCE_LIST_HEADERS, extract_resource_list_rows(project)),
        WorksheetSpec("展会与活动计划", EVENT_PLAN_HEADERS, extract_event_plan_rows(project)),
        WorksheetSpec("认证与合规事项", COMPLIANCE_HEADERS, extract_compliance_rows(project)),
        WorksheetSpec("预算测算", BUDGET_HEADERS, extract_budget_rows(project)),
        WorksheetSpec("KPI跟踪表", KPI_HEADERS, extract_kpi_rows(project)),
        WorksheetSpec("12-24个月行动计划", ACTION_PLAN_HEADERS, extract_action_plan_rows(project)),
        WorksheetSpec("风险清单", RISK_HEADERS, extract_risk_rows(project)),
        WorksheetSpec("数据来源", DATA_SOURCE_HEADERS, extract_data_source_rows(project)),
        WorksheetSpec("人工复核清单", REVIEW_HEADERS, extract_manual_review_rows(project)),
        WorksheetSpec("导出记录", EXPORT_RECORD_HEADERS, export_record),
    ]


def extract_enterprise_rows(project: dict[str, Any], enterprise: dict[str, Any]) -> list[dict[str, str]]:
    finance = enterprise.get("finance") if isinstance(enterprise.get("finance"), dict) else {}
    team = enterprise.get("team") if isinstance(enterprise.get("team"), dict) else {}
    return [{
        "企业ID": _stringify(enterprise.get("id") or project.get("enterprise_id")),
        "企业名称": _stringify(enterprise.get("name") or enterprise.get("enterprise_name")),
        "所属行业": _stringify(enterprise.get("industry") or project.get("selected_industry")),
        "海外客户": _stringify(enterprise.get("overseas_customers")),
        "英文资料": _stringify(enterprise.get("english_materials")),
        "国际化团队": _stringify(team),
        "出海预算": _stringify(finance.get("export_budget")),
        "授信额度": _stringify(finance.get("credit_line")),
        "备注": _stringify(enterprise.get("notes")),
    }]


def extract_product_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    products = [item for item in _as_list(project.get("products")) if isinstance(item, dict)]
    rows = []
    for product in products:
        rows.append({
            "产品ID": _stringify(product.get("id")),
            "产品名称": _stringify(product.get("name") or product.get("product_name")),
            "HS编码": _stringify(product.get("hs_code")),
            "认证资质": _stringify(product.get("certifications")),
            "产能": _stringify(product.get("capacity")),
            "MOQ": _stringify(product.get("moq")),
            "价格带": _stringify(product.get("price_band")),
            "海外版本": _stringify(product.get("overseas_version")),
            "备注": _stringify(product.get("notes")),
        })
    return rows or [_empty_row(PRODUCT_HEADERS)]


def extract_action_plan_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    """Extract 12-24 month action-plan rows from generated plan JSON."""

    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    roadmap_section = sections.get("07_12_24_month_implementation_roadmap", {}) if isinstance(sections, dict) else {}
    candidates = _extract(roadmap_section, "roadmap", "implementation_roadmap", "action_plan", "implementation_plan") or result.get("implementation_roadmap_12_24_months")
    rows = [_normalize_row(item, ACTION_PLAN_HEADERS, _ACTION_ALIASES) for item in _as_list(candidates)]
    return rows or [_empty_row(ACTION_PLAN_HEADERS)]


def extract_resource_list_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    """Extract overseas resource rows without inventing unnamed resources."""

    result = project.get("result") or {}
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    resource_section = sections.get("04_overseas_resource_matching_plan", {}) if isinstance(sections, dict) else {}
    candidates = _extract(resource_section, "resources", "resource_matches", "resource_list", "matching_resources") or result.get("overseas_resource_matches")
    if candidates is None and isinstance(resource_section, dict):
        candidates = _flatten_resource_section(resource_section)
    rows = []
    for item in _as_list(candidates):
        row = _normalize_row(item, RESOURCE_LIST_HEADERS, _RESOURCE_ALIASES)
        if not row["资源名称"]:
            row["资源名称"] = MISSING_RESOURCE_NAME
        rows.append(row)
    return rows or [{**_empty_row(RESOURCE_LIST_HEADERS), "资源名称": MISSING_RESOURCE_NAME}]


def extract_country_matrix_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    section = _section(project, "02_overseas_market_selection")
    candidates = _extract(section, "country_priority_matrix", "recommended_country_tiers", "country_selection_five_dimension_model") or _result(project).get("country_priority_matrix")
    rows = []
    for item in _as_list(candidates):
        if not isinstance(item, dict):
            rows.append({**_empty_row(COUNTRY_MATRIX_HEADERS), "国家/地区": _stringify(item)})
            continue
        dimensions = _dimension_score_map(item.get("dimension_scores") or item.get("scores") or item.get("five_dimension_scores"))
        rows.append({
            "国家/地区": _stringify(_extract(item, "country_name", "country", "country_region", "market")),
            "优先级": _stringify(_extract(item, "priority_rank", "priority", "tier")),
            "总分": _stringify(_extract(item, "total_score", "score")),
            "市场需求": dimensions.get("market_demand", ""),
            "政策环境": dimensions.get("policy_environment", ""),
            "竞争环境": dimensions.get("competitive_environment", ""),
            "渠道成熟度": dimensions.get("channel_maturity", ""),
            "供应链适配": dimensions.get("supply_chain_fit", ""),
            "推荐进入模式": _stringify(_extract(item, "recommended_entry_mode", "entry_mode")),
            "关键机会": _stringify(_extract(item, "key_opportunities", "opportunities")),
            "关键风险": _stringify(_extract(item, "key_risks", "risks")),
            "数据来源": _stringify(_extract(item, "data_source", "source", "citation")),
            "备注": _stringify(_extract(item, "notes", "rationale", "comment")),
        })
    return rows or [_empty_row(COUNTRY_MATRIX_HEADERS)]


def extract_event_plan_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    section = _section(project, "05_exhibition_and_marketing_plan")
    candidates = _extract(section, "events", "event_plan", "exhibitions", "exhibition_plan", "marketing_events")
    if candidates is None and isinstance(section, dict):
        candidates = _flatten_named_section(section, default_type="活动")
    rows = []
    for item in _as_list(candidates):
        if not isinstance(item, dict):
            rows.append({**_empty_row(EVENT_PLAN_HEADERS), "活动/展会名称": _stringify(item)})
            continue
        rows.append({
            "活动类型": _stringify(_extract(item, "event_type", "type", "category")),
            "国家/地区": _stringify(_extract(item, "country_region", "country", "market")),
            "活动/展会名称": _stringify(_extract(item, "event_name", "exhibition_name", "name", "title")),
            "时间": _stringify(_extract(item, "time", "date", "period", "time_range")),
            "目标": _stringify(_extract(item, "goal", "objective", "purpose")),
            "负责人": _stringify(_extract(item, "owner", "responsible", "responsible_party")),
            "预算": _stringify(_extract(item, "budget", "amount")),
            "优先级": _stringify(_extract(item, "priority", "priority_level")),
            "状态": _stringify(_extract(item, "status", "current_status")),
            "备注": _stringify(_extract(item, "notes", "remark", "comment")),
        })
    return rows or [_empty_row(EVENT_PLAN_HEADERS)]


def extract_compliance_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    result = _result(project)
    candidates = result.get("certification_and_compliance") or result.get("compliance_items") or []
    rows = []
    for item in _as_list(candidates):
        if isinstance(item, dict):
            rows.append(_generic_row(item, COMPLIANCE_HEADERS, {
                "事项类型": ("type", "item_type", "category"), "国家/地区": ("country_region", "country", "market"),
                "认证/合规事项": ("name", "item", "certification", "compliance_item"), "适用产品": ("product", "products", "applicable_products"),
                "责任人": ("owner", "responsible", "responsible_party"), "截止时间": ("deadline", "due_date", "time"),
                "当前状态": ("status", "current_status"), "风险等级": ("risk_level", "level"),
                "数据来源": ("data_source", "source", "citation"), "备注": ("notes", "remark", "comment"),
            }))
    if not rows:
        product_certs = []
        for product in _as_list(project.get("products")):
            if isinstance(product, dict):
                for cert in _as_list(product.get("certifications")):
                    product_certs.append({**_empty_row(COMPLIANCE_HEADERS), "事项类型": "产品认证", "认证/合规事项": _stringify(cert), "适用产品": _stringify(product.get("name"))})
        rows = product_certs
    return rows or [_empty_row(COMPLIANCE_HEADERS)]


def extract_budget_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    result = _result(project)
    section = _section(project, "06_financing_and_capacity_expansion_plan")
    candidates = result.get("budget_estimates") or result.get("budget") or _extract(section, "budget_estimates", "budget", "cost_plan")
    rows = []
    for item in _as_list(candidates):
        if not isinstance(item, dict):
            rows.append({**_empty_row(BUDGET_HEADERS), "预算项目": _stringify(item)})
            continue
        rows.append(_generic_row(item, BUDGET_HEADERS, {
            "预算项目": ("budget_item", "item", "name", "category"), "国家/地区": ("country_region", "country", "market"),
            "阶段": ("stage", "phase"), "假设": ("assumption", "assumptions", "basis"), "金额": ("amount", "cost", "budget"),
            "币种": ("currency",), "负责人": ("owner", "responsible", "responsible_party"), "备注": ("notes", "remark", "comment"),
        }))
    return rows or [{**_empty_row(BUDGET_HEADERS), "预算项目": "待测算", "假设": "根据目标国家、渠道建设、认证和活动计划补充", "金额": "", "备注": "需财务/业务负责人复核"}]


def extract_kpi_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    result = _result(project)
    candidates = result.get("kpis") or result.get("kpi_tracking") or []
    rows = []
    for item in _as_list(candidates):
        if isinstance(item, dict):
            rows.append(_generic_row(item, KPI_HEADERS, {
                "KPI指标": ("kpi", "metric", "name", "indicator"), "目标值": ("target_value", "target"),
                "当前值": ("current_value", "current"), "数据来源": ("data_source", "source"), "统计周期": ("period", "cycle", "frequency"),
                "负责人": ("owner", "responsible", "responsible_party"), "状态": ("status",), "备注": ("notes", "remark", "comment"),
            }))
    return rows or [
        {**_empty_row(KPI_HEADERS), "KPI指标": "目标国家有效渠道数", "目标值": "待设定", "当前值": "待填报", "数据来源": "渠道资源清单", "统计周期": "月度"},
        {**_empty_row(KPI_HEADERS), "KPI指标": "认证/合规事项完成率", "目标值": "100%", "当前值": "待填报", "数据来源": "认证与合规事项", "统计周期": "月度"},
    ]


def extract_risk_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    result = _result(project)
    candidates = result.get("risks") or result.get("risk_register") or []
    if not candidates:
        candidates = _extract(_section(project, "02_overseas_market_selection"), "key_risks", "risks")
    rows = []
    for item in _as_list(candidates):
        if not isinstance(item, dict):
            rows.append({**_empty_row(RISK_HEADERS), "风险描述": _stringify(item)})
            continue
        rows.append(_generic_row(item, RISK_HEADERS, {
            "风险类别": ("risk_type", "category", "type"), "国家/地区": ("country_region", "country", "market"), "风险描述": ("risk", "description", "risk_description"),
            "影响": ("impact",), "概率": ("probability", "likelihood"), "等级": ("level", "risk_level"),
            "应对措施": ("mitigation", "response", "action"), "负责人": ("owner", "responsible", "responsible_party"),
            "状态": ("status",), "备注": ("notes", "remark", "comment"),
        }))
    return rows or [_empty_row(RISK_HEADERS)]


def extract_data_source_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    metadata = project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    citations = metadata.get("context_bundle", {}) if isinstance(metadata.get("context_bundle"), dict) else {}
    rows = []
    for key, value in citations.items():
        if isinstance(value, dict):
            rows.append({
                "来源类型": key,
                "来源名称": _stringify(value.get("name") or value.get("title") or key),
                "引用ID/链接": _stringify(value.get("citation_ids") or value.get("url") or value.get("id")),
                "适用Sheet": "数据来源",
                "更新时间": _stringify(value.get("updated_at") or value.get("date")),
                "可信度": _stringify(value.get("confidence") or value.get("source_quality")),
                "备注": _stringify(value.get("notes")),
            })
    return rows or [{**_empty_row(DATA_SOURCE_HEADERS), "来源类型": "系统生成", "来源名称": "方案生成上下文/人工录入资料", "适用Sheet": "全部", "备注": "导出后建议补充外部引用链接"}]


def extract_manual_review_rows(project: dict[str, Any]) -> list[dict[str, str]]:
    result = _result(project)
    candidates = result.get("global_manual_review_items") or result.get("data_quality_review") or result.get("manual_review_items")
    rows = []
    for item in _as_list(candidates):
        if not isinstance(item, dict):
            rows.append({**_empty_row(REVIEW_HEADERS), "复核事项": _stringify(item), "状态": "待复核"})
            continue
        rows.append(_generic_row(item, REVIEW_HEADERS, {
            "复核事项": ("item", "review_item", "name", "title"), "关联Sheet": ("sheet", "related_sheet"), "优先级": ("priority",),
            "负责人": ("owner", "responsible", "responsible_party"), "截止时间": ("deadline", "due_date"), "状态": ("status",),
            "复核要点": ("review_points", "points", "description"), "备注": ("notes", "remark", "comment"),
        }))
    return rows or [{**_empty_row(REVIEW_HEADERS), "复核事项": "补充/核验空白字段与AI生成假设", "关联Sheet": "全部", "优先级": "高", "状态": "待复核", "复核要点": "检查关键金额、KPI目标值、认证要求、渠道资源真实性"}]


def _write_xlsx(path: Path, *, worksheets: list[WorksheetSpec], system_name: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", _content_types_xml(len(worksheets)))
        xlsx.writestr("_rels/.rels", _root_rels_xml())
        xlsx.writestr("xl/workbook.xml", _workbook_xml([sheet.name for sheet in worksheets]))
        xlsx.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(worksheets)))
        xlsx.writestr("xl/styles.xml", _styles_xml())
        for idx, sheet in enumerate(worksheets, start=1):
            rows = [sheet.headers] + [[row.get(header, "") for header in sheet.headers] for row in sheet.rows]
            widths = [_column_width([row[col_idx] for row in rows]) for col_idx in range(len(sheet.headers))]
            xlsx.writestr(f"xl/worksheets/sheet{idx}.xml", _worksheet_xml(rows=rows, widths=widths))
        xlsx.writestr("docProps/core.xml", _core_xml(system_name))
        xlsx.writestr("docProps/app.xml", _app_xml())


def _worksheet_xml(*, rows: list[list[str]], widths: list[float]) -> str:
    cols = "".join(f'<col min="{idx}" max="{idx}" width="{width:.1f}" customWidth="1"/>' for idx, width in enumerate(widths, start=1))
    row_xml = []
    for row_idx, row in enumerate(rows, start=1):
        cells = []
        for col_idx, value in enumerate(row, start=1):
            style = "1" if row_idx == 1 else "0"
            cells.append(f'<c r="{_cell_ref(row_idx, col_idx)}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{_escape(value)}</t></is></c>')
        row_xml.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
    dimension = f"A1:{_column_name(len(rows[0]))}{len(rows)}"
    return _xml_header() + (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{"".join(row_xml)}</sheetData><autoFilter ref="{dimension}"/></worksheet>'
    )


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for idx in range(1, sheet_count + 1))
    return _xml_header() + f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>{sheet_overrides}<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'


def _root_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(f'<sheet name="{_escape(_safe_sheet_name(name))}" sheetId="{idx}" r:id="rId{idx}"/>' for idx, name in enumerate(sheet_names, start=1))
    return _xml_header() + f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'


def _workbook_rels_xml(sheet_count: int) -> str:
    rels = "".join(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>' for idx in range(1, sheet_count + 1))
    rels += f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    return _xml_header() + f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'


def _styles_xml() -> str:
    return _xml_header() + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/><family val="2"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/><family val="2"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left style="thin"><color rgb="FFD9D9D9"/></left><right style="thin"><color rgb="FFD9D9D9"/></right><top style="thin"><color rgb="FFD9D9D9"/></top><bottom style="thin"><color rgb="FFD9D9D9"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'


def _core_xml(system_name: str) -> str:
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return _xml_header() + f'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:creator>{_escape(system_name)}</dc:creator><cp:lastModifiedBy>{_escape(system_name)}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'


def _app_xml() -> str:
    return _xml_header() + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Excel</Application></Properties>'


def _primary_sheet_for_kind(kind: ExcelExportKind, worksheets: list[WorksheetSpec]) -> WorksheetSpec:
    if kind is ExcelExportKind.ACTION_PLAN:
        return next(sheet for sheet in worksheets if sheet.name == "12-24个月行动计划")
    if kind is ExcelExportKind.RESOURCE_LIST:
        return next(sheet for sheet in worksheets if sheet.name == "渠道资源清单")
    return worksheets[0]


def _section(project: dict[str, Any], key: str) -> dict[str, Any]:
    result = _result(project)
    sections = result.get("sections", {}) if isinstance(result, dict) else {}
    section = sections.get(key, {}) if isinstance(sections, dict) else {}
    return section if isinstance(section, dict) else {}


def _result(project: dict[str, Any]) -> dict[str, Any]:
    result = project.get("result") or {}
    return result if isinstance(result, dict) else {}


def _dimension_score_map(value: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if isinstance(value, dict):
        return {str(key): _stringify(score.get("score") if isinstance(score, dict) else score) for key, score in value.items()}
    for item in _as_list(value):
        if isinstance(item, dict):
            dimension = item.get("dimension") or item.get("name")
            if dimension:
                mapping[str(dimension)] = _stringify(item.get("score"))
    return mapping


def _generic_row(item: dict[str, Any], headers: list[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    return {header: _stringify(_extract(item, *aliases[header]), empty="") for header in headers}


def _normalize_row(item: Any, headers: list[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    if not isinstance(item, dict):
        if headers == RESOURCE_LIST_HEADERS:
            return {**_empty_row(headers), "资源类型": _stringify(item)}
        return {**_empty_row(headers), headers[0]: _stringify(item)}
    return _generic_row(item, headers, aliases)


def _flatten_resource_section(section: dict[str, Any]) -> list[Any]:
    rows = []
    for key, value in section.items():
        if key in {"title", "summary", "description"}:
            continue
        for item in _as_list(value):
            if isinstance(item, dict):
                rows.append({"resource_type": item.get("resource_type") or item.get("type") or item.get("category") or key, **item})
            elif item not in (None, "", [], {}):
                rows.append({"resource_type": key, "notes": item})
    return rows


def _flatten_named_section(section: dict[str, Any], *, default_type: str) -> list[Any]:
    rows = []
    for key, value in section.items():
        if key in {"title", "summary", "description"}:
            continue
        for item in _as_list(value):
            if isinstance(item, dict):
                rows.append({"type": item.get("type") or default_type, **item})
            elif item not in (None, "", [], {}):
                rows.append({"type": default_type, "name": key, "notes": item})
    return rows


def _empty_row(headers: list[str]) -> dict[str, str]:
    return {header: "" for header in headers}


def _extract(data: Any, *keys: str) -> Any:
    if not isinstance(data, dict):
        return data
    for key in keys:
        if key in data and data[key] not in (None, "", [], {}):
            return data[key]
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _stringify(value: Any, *, empty: str = "") -> str:
    if value is None:
        return empty
    if isinstance(value, (list, tuple, set)):
        return "；".join(_stringify(item, empty=empty) for item in value if _stringify(item, empty=""))
    if isinstance(value, dict):
        parts = [f"{key}：{_stringify(item, empty=empty)}" for key, item in value.items() if item not in (None, "", [], {})]
        return "；".join(parts)
    return str(value)


def _column_width(values: list[str]) -> float:
    max_units = max((_display_units(value) for value in values), default=10)
    return min(max(max_units + 2, 10), 45)


def _display_units(value: str) -> int:
    total = 0
    for char in str(value):
        total += 2 if ord(char) > 127 else 1
    return total


def _cell_ref(row: int, col: int) -> str:
    return f"{_column_name(col)}{row}"


def _column_name(col: int) -> str:
    name = ""
    while col:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return name


def _xml_header() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _safe_sheet_name(value: str) -> str:
    cleaned = re.sub(r'[\\/*?:\[\]]+', "_", value).strip("'")
    return (cleaned[:31] or "Sheet")


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return cleaned[:80] or "企业出海Excel导出"
