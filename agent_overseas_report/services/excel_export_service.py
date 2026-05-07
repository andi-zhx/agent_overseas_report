"""Excel export utilities for enterprise overseas-plan action/resource sheets.

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


class ExcelExportKind(str, Enum):
    """Supported overseas-plan Excel workbook types."""

    ACTION_PLAN = "action_plan"
    RESOURCE_LIST = "resource_list"


@dataclass(slots=True)
class ExcelExportRequest:
    """Input DTO for exporting overseas-plan Excel workbooks."""

    project_id: str
    exported_by: str
    export_kind: ExcelExportKind | str
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


ACTION_PLAN_HEADERS = ["阶段", "时间范围", "核心目标", "关键动作", "责任方", "所需资源", "交付物", "优先级", "状态", "备注"]
RESOURCE_LIST_HEADERS = ["资源类型", "国家/地区", "资源名称", "建议对接对象", "对接目的", "优先级", "所属阶段", "需要准备的材料", "当前状态", "备注"]


_ACTION_ALIASES: dict[str, tuple[str, ...]] = {
    "阶段": ("阶段", "stage", "phase", "milestone"),
    "时间范围": ("时间范围", "time_range", "timeframe", "time", "period", "duration"),
    "核心目标": ("核心目标", "core_goal", "goal", "target", "objective"),
    "关键动作": ("关键动作", "key_actions", "actions", "action", "tasks", "initiatives"),
    "责任方": ("责任方", "responsible_party", "owner", "responsible", "department"),
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
    export_kind: ExcelExportKind | str,
    output_dir: str | Path | None = None,
    exported_by: str,
    system_name: str = SYSTEM_NAME,
    exported_at: datetime | None = None,
) -> ExcelExportResult:
    """Generate and save one overseas-plan Excel workbook.

    ``export_kind`` selects either the 12-24 month action plan or the overseas
    resource matching list.  The workbook is a single-sheet ``.xlsx`` file with
    clear Chinese headers and column widths derived from cell contents.
    """

    kind = ExcelExportKind(export_kind)
    exported_at = exported_at or datetime.now(UTC)
    exported_at_iso = exported_at.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat() + "Z"
    enterprise_name = enterprise.get("name") or enterprise.get("enterprise_name") or project.get("enterprise_id") or "未命名企业"
    suffix = "12-24个月行动计划表" if kind is ExcelExportKind.ACTION_PLAN else "海外资源对接清单"
    plan_name = f"{enterprise_name}{suffix}"
    sheet_name = suffix[:31]
    root = Path(output_dir) if output_dir is not None else DEFAULT_EXPORT_ROOT
    target_dir = root / str(project["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{_safe_filename(plan_name)}_v{project.get('version', 1)}_{exported_at.strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = target_dir / file_name

    headers = ACTION_PLAN_HEADERS if kind is ExcelExportKind.ACTION_PLAN else RESOURCE_LIST_HEADERS
    rows = extract_action_plan_rows(project) if kind is ExcelExportKind.ACTION_PLAN else extract_resource_list_rows(project)
    _write_xlsx(file_path, sheet_name=sheet_name, headers=headers, row_dicts=rows, system_name=system_name)

    return ExcelExportResult(
        project_id=str(project["id"]),
        plan_name=plan_name,
        export_type="Excel",
        export_kind=kind.value,
        sheet_name=sheet_name,
        file_path=str(file_path),
        exported_by=exported_by,
        exported_at=exported_at_iso,
        headers=headers,
        rows=rows,
    )


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


def _write_xlsx(path: Path, *, sheet_name: str, headers: list[str], row_dicts: list[dict[str, str]], system_name: str) -> None:
    rows = [headers] + [[row.get(header, "") for header in headers] for row in row_dicts]
    widths = [_column_width([row[idx] for row in rows]) for idx in range(len(headers))]
    sheet_xml = _worksheet_xml(sheet_name=sheet_name, rows=rows, widths=widths)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", _content_types_xml())
        xlsx.writestr("_rels/.rels", _root_rels_xml())
        xlsx.writestr("xl/workbook.xml", _workbook_xml(sheet_name))
        xlsx.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml())
        xlsx.writestr("xl/styles.xml", _styles_xml())
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        xlsx.writestr("docProps/core.xml", _core_xml(system_name))
        xlsx.writestr("docProps/app.xml", _app_xml())


def _worksheet_xml(*, sheet_name: str, rows: list[list[str]], widths: list[float]) -> str:
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


def _content_types_xml() -> str:
    return _xml_header() + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'


def _root_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'


def _workbook_xml(sheet_name: str) -> str:
    return _xml_header() + f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{_escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'


def _workbook_rels_xml() -> str:
    return _xml_header() + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'


def _styles_xml() -> str:
    return _xml_header() + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/><family val="2"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/><family val="2"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left style="thin"><color rgb="FFD9D9D9"/></left><right style="thin"><color rgb="FFD9D9D9"/></right><top style="thin"><color rgb="FFD9D9D9"/></top><bottom style="thin"><color rgb="FFD9D9D9"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'


def _core_xml(system_name: str) -> str:
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return _xml_header() + f'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:creator>{_escape(system_name)}</dc:creator><cp:lastModifiedBy>{_escape(system_name)}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'


def _app_xml() -> str:
    return _xml_header() + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Excel</Application></Properties>'


def _normalize_row(item: Any, headers: list[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    if not isinstance(item, dict):
        if headers == RESOURCE_LIST_HEADERS:
            return {**_empty_row(headers), "资源类型": _stringify(item)}
        return {**_empty_row(headers), headers[0]: _stringify(item)}
    return {header: _stringify(_extract(item, *aliases[header]), empty="") for header in headers}


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


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return cleaned[:80] or "企业出海Excel导出"
