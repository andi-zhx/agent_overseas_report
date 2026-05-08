"""Deterministic report quality scoring for generated overseas reports."""

from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from agent_overseas_report.models.overseas_generation import utc_now


class ReportQualityStatus(str, Enum):
    """Quality gate labels used after automatic report scoring."""

    PASSED = "passed"
    NEEDS_REVISION = "needs_revision"
    FAILED_QUALITY_CHECK = "failed_quality_check"


@dataclass(slots=True)
class ReportQualityDimensionScore:
    """One 0-10 scoring dimension with review findings."""

    key: str
    name: str
    score: float
    max_score: int = 10
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReportQualityScore:
    """Persistable 100-point quality review result for a generated report."""

    project_id: str
    version_number: int | None
    total_score: float
    status: ReportQualityStatus
    dimension_scores: list[ReportQualityDimensionScore]
    issues: list[str]
    suggestions: list[str]
    created_at: Any = field(default_factory=utc_now)
    id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["created_at"] = self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else self.created_at
        return payload


class ReportQualityScoringService:
    """Score generated reports against customer-delivery standards.

    The service intentionally uses transparent deterministic heuristics instead
    of another LLM call so it can run automatically after every generation and
    produce stable, auditable database records.
    """

    DIMENSIONS: tuple[tuple[str, str], ...] = (
        ("data_completeness", "数据完整度"),
        ("citation_completeness", "引用来源完整度"),
        ("market_analysis_depth", "市场分析深度"),
        ("company_diagnosis_depth", "公司诊断深度"),
        ("channel_execution_feasibility", "渠道方案可执行性"),
        ("financing_analysis_depth", "投融资分析深度"),
        ("risk_coverage", "风险覆盖度"),
        ("budget_kpi_quantification", "预算与 KPI 可量化程度"),
        ("roadmap_clarity_12_24_months", "12-24个月路线图清晰度"),
        ("client_delivery_readability", "客户交付可读性"),
    )

    def score_report(
        self,
        *,
        report: dict[str, Any],
        project_id: str,
        version_number: int | None = None,
        context_bundle: dict[str, Any] | None = None,
    ) -> ReportQualityScore:
        """Return a 100-point quality score plus issues and suggestions."""

        payload = copy.deepcopy(report) if isinstance(report, dict) else {}
        context = copy.deepcopy(context_bundle or {})
        dimensions = [self._score_dimension(key, name, payload, context) for key, name in self.DIMENSIONS]
        total = round(sum(item.score for item in dimensions), 2)
        status = self._status_for_score(total)
        issues: list[str] = []
        suggestions: list[str] = []
        for item in dimensions:
            issues.extend(f"{item.name}：{issue}" for issue in item.issues)
            suggestions.extend(f"{item.name}：{suggestion}" for suggestion in item.suggestions)
        return ReportQualityScore(
            id=f"rqs_{uuid4().hex}",
            project_id=project_id,
            version_number=version_number,
            total_score=total,
            status=status,
            dimension_scores=dimensions,
            issues=issues,
            suggestions=suggestions,
            metadata={
                "scoring_model": "deterministic_delivery_rubric_v1",
                "quality_gate": {"needs_revision_below": 75, "failed_quality_check_below": 60},
            },
        )

    def _score_dimension(
        self,
        key: str,
        name: str,
        report: dict[str, Any],
        context_bundle: dict[str, Any],
    ) -> ReportQualityDimensionScore:
        checks = _DIMENSION_CHECKS[key]
        evidence: list[str] = []
        score = 0.0
        for check in checks:
            passed, weight, label = check(report, context_bundle)
            if passed:
                score += weight
                evidence.append(label)
        score = round(min(10.0, score), 2)
        issues: list[str] = []
        suggestions: list[str] = []
        if score < 10:
            issues.append(_ISSUES[key])
            suggestions.append(_SUGGESTIONS[key])
        return ReportQualityDimensionScore(key=key, name=name, score=score, issues=issues, suggestions=suggestions, evidence=evidence)

    @staticmethod
    def _status_for_score(total_score: float) -> ReportQualityStatus:
        if total_score < 60:
            return ReportQualityStatus.FAILED_QUALITY_CHECK
        if total_score < 75:
            return ReportQualityStatus.NEEDS_REVISION
        return ReportQualityStatus.PASSED


Path = tuple[str, ...]
Check = Any


def _has_path(report: dict[str, Any], *paths: Path) -> bool:
    return any(_get_path(report, path) not in (None, "", [], {}) for path in paths)


def _get_path(payload: Any, path: Path) -> Any:
    current = payload
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _text(payload: Any) -> str:
    if isinstance(payload, dict):
        return " ".join(_text(value) for value in payload.values())
    if isinstance(payload, list):
        return " ".join(_text(item) for item in payload)
    return str(payload or "")


def _count_numbers(payload: Any) -> int:
    return len(re.findall(r"\d+(?:\.\d+)?%?|USD|RMB|CNY|万元|百万|KPI|ROI|CAC|GMV", _text(payload), flags=re.IGNORECASE))


def _count_citations(payload: Any) -> int:
    if isinstance(payload, dict):
        count = 0
        for key, value in payload.items():
            if str(key).lower() in {"citations", "citation_ids", "sources", "source_urls", "references"}:
                if isinstance(value, list):
                    count += len([item for item in value if item])
                elif value:
                    count += 1
            count += _count_citations(value)
        return count
    if isinstance(payload, list):
        return sum(_count_citations(item) for item in payload)
    return 0


def _list_len(report: dict[str, Any], *paths: Path) -> int:
    total = 0
    for path in paths:
        value = _get_path(report, path)
        if isinstance(value, list):
            total += len(value)
        elif value not in (None, "", {}, []):
            total += 1
    return total


def _contains_terms(report: dict[str, Any], terms: tuple[str, ...], *paths: Path) -> bool:
    haystack = _text([_get_path(report, path) for path in paths]) if paths else _text(report)
    return any(term.lower() in haystack.lower() for term in terms)


def _make_check(predicate: Any, weight: float, label: str) -> Any:
    def _check(report: dict[str, Any], context_bundle: dict[str, Any]) -> tuple[bool, float, str]:
        return bool(predicate(report, context_bundle)), weight, label

    return _check


_DIMENSION_CHECKS: dict[str, tuple[Any, ...]] = {
    "data_completeness": (
        _make_check(lambda r, c: _has_path(r, ("sections",), ("investment_analysis_report",)), 2, "包含报告主体模块"),
        _make_check(lambda r, c: _list_len(r, ("recommended_target_countries",), ("country_priority_matrix",)) > 0, 2, "包含目标国家/优先级数据"),
        _make_check(lambda r, c: _has_path(r, ("enterprise_diagnosis",), ("sections", "01_enterprise_diagnosis")), 2, "包含企业诊断数据"),
        _make_check(lambda r, c: _has_path(r, ("implementation_roadmap_12_24_months",), ("sections", "07_12_24_month_implementation_roadmap")), 2, "包含路线图数据"),
        _make_check(lambda r, c: _has_path(r, ("risk_warnings",), ("sections", "08_risk_warnings_and_next_steps")), 2, "包含风险或下一步数据"),
    ),
    "citation_completeness": (
        _make_check(lambda r, c: _count_citations(r) >= 1, 3, "报告含引用字段"),
        _make_check(lambda r, c: _count_citations(r) >= 5, 3, "引用数量达到基础门槛"),
        _make_check(lambda r, c: _count_citations(c) >= 1 or _has_path(r, ("data_quality_review",)), 2, "可追溯到上下文或数据质量复核"),
        _make_check(lambda r, c: not _contains_terms(r, ("无来源", "待补充来源", "缺少来源")), 2, "未出现明显缺来源标记"),
    ),
    "market_analysis_depth": (
        _make_check(lambda r, c: _has_path(r, ("country_priority_matrix",), ("sections", "02_overseas_market_selection")), 3, "包含国家/市场选择分析"),
        _make_check(lambda r, c: _contains_terms(r, ("市场", "需求", "竞争", "准入", "客户"), ("sections", "02_overseas_market_selection"), ("investment_analysis_report", "market_analysis")), 3, "覆盖需求/竞争/准入等市场主题"),
        _make_check(lambda r, c: _count_numbers(_get_path(r, ("country_priority_matrix",))) >= 2, 2, "市场分析包含评分或量化信息"),
        _make_check(lambda r, c: _list_len(r, ("country_priority_matrix",)) >= 1, 2, "至少一个国家有优先级结论"),
    ),
    "company_diagnosis_depth": (
        _make_check(lambda r, c: _has_path(r, ("enterprise_diagnosis",), ("sections", "01_enterprise_diagnosis")), 3, "包含企业诊断章节"),
        _make_check(lambda r, c: _contains_terms(r, ("优势", "短板", "能力", "产能", "认证", "团队"), ("enterprise_diagnosis",), ("sections", "01_enterprise_diagnosis")), 3, "覆盖优势/短板/能力主题"),
        _make_check(lambda r, c: _has_path(r, ("maturity_assessment",), ("data_quality_review",)), 2, "包含成熟度或数据质量判断"),
        _make_check(lambda r, c: _has_path(r, ("product_competitiveness_analysis",)), 2, "包含产品竞争力分析"),
    ),
    "channel_execution_feasibility": (
        _make_check(lambda r, c: _has_path(r, ("channel_path_design",), ("recommended_entry_modes",), ("sections", "03_entry_mode_design")), 3, "包含渠道/进入模式设计"),
        _make_check(lambda r, c: _contains_terms(r, ("经销", "代理", "平台", "KA", "展会", "伙伴", "获客"), ("channel_path_design",), ("sections", "03_entry_mode_design"), ("sections", "05_exhibition_and_marketing_plan")), 3, "渠道动作具备场景和载体"),
        _make_check(lambda r, c: _list_len(r, ("overseas_resource_matches",), ("exhibition_and_marketing_plan",)) > 0, 2, "包含资源或展会营销计划"),
        _make_check(lambda r, c: _contains_terms(r, ("下一步", "负责人", "时间", "里程碑", "行动"), ("channel_path_design",), ("implementation_roadmap_12_24_months",)), 2, "渠道方案包含行动安排"),
    ),
    "financing_analysis_depth": (
        _make_check(lambda r, c: _has_path(r, ("financing_and_capacity_plan",), ("sections", "06_financing_and_capacity_expansion_plan")), 3, "包含投融资与扩产章节"),
        _make_check(lambda r, c: _contains_terms(r, ("融资", "预算", "现金流", "扩产", "产能", "资金"), ("financing_and_capacity_plan",), ("sections", "06_financing_and_capacity_expansion_plan")), 3, "覆盖融资/预算/产能主题"),
        _make_check(lambda r, c: _count_numbers(_get_path(r, ("financing_and_capacity_plan",))) >= 2 or _count_numbers(_get_path(r, ("sections", "06_financing_and_capacity_expansion_plan"))) >= 2, 2, "投融资分析包含量化假设"),
        _make_check(lambda r, c: _contains_terms(r, ("假设", "敏感", "回收期", "ROI", "情景"), ("financing_and_capacity_plan",), ("sections", "06_financing_and_capacity_expansion_plan")), 2, "包含假设或敏感性视角"),
    ),
    "risk_coverage": (
        _make_check(lambda r, c: _has_path(r, ("risk_warnings",), ("sections", "08_risk_warnings_and_next_steps")), 3, "包含风险章节/清单"),
        _make_check(lambda r, c: _list_len(r, ("risk_warnings",), ("sections", "08_risk_warnings_and_next_steps", "risk_warnings")) >= 3, 3, "风险条目不少于 3 项"),
        _make_check(lambda r, c: _contains_terms(r, ("合规", "认证", "关税", "汇率", "物流", "政治", "合同", "数据"), ("risk_warnings",), ("sections", "08_risk_warnings_and_next_steps")), 2, "覆盖多类风险主题"),
        _make_check(lambda r, c: _contains_terms(r, ("应对", "缓释", "预案", "mitigation", "负责人"), ("risk_warnings",), ("sections", "08_risk_warnings_and_next_steps")), 2, "风险附带应对措施"),
    ),
    "budget_kpi_quantification": (
        _make_check(lambda r, c: _count_numbers(r) >= 5, 3, "全文包含足够量化信息"),
        _make_check(lambda r, c: _contains_terms(r, ("KPI", "指标", "目标", "预算", "费用", "收入", "线索")), 3, "包含预算/KPI/目标主题"),
        _make_check(lambda r, c: _count_numbers(_get_path(r, ("implementation_roadmap_12_24_months",))) >= 2 or _count_numbers(_get_path(r, ("sections", "07_12_24_month_implementation_roadmap"))) >= 2, 2, "路线图含量化里程碑"),
        _make_check(lambda r, c: _contains_terms(r, ("月", "季度", "12", "24"), ("implementation_roadmap_12_24_months",), ("sections", "07_12_24_month_implementation_roadmap")), 2, "指标具备时间口径"),
    ),
    "roadmap_clarity_12_24_months": (
        _make_check(lambda r, c: _has_path(r, ("implementation_roadmap_12_24_months",), ("sections", "07_12_24_month_implementation_roadmap")), 3, "包含 12-24 个月路线图"),
        _make_check(lambda r, c: _list_len(r, ("implementation_roadmap_12_24_months",)) >= 3, 3, "路线图阶段不少于 3 段"),
        _make_check(lambda r, c: _contains_terms(r, ("0-6", "6-12", "12-24", "个月", "里程碑"), ("implementation_roadmap_12_24_months",), ("sections", "07_12_24_month_implementation_roadmap")), 2, "包含明确时间段"),
        _make_check(lambda r, c: _contains_terms(r, ("行动", "负责人", "交付", "资源", "产出", "KPI"), ("implementation_roadmap_12_24_months",), ("sections", "07_12_24_month_implementation_roadmap")), 2, "路线图包含动作/产出/KPI"),
    ),
    "client_delivery_readability": (
        _make_check(lambda r, c: _has_path(r, ("sections",), ("investment_analysis_report",)), 2, "结构化章节清晰"),
        _make_check(lambda r, c: len(_text(r)) >= 500, 2, "正文信息量满足交付阅读"),
        _make_check(lambda r, c: _contains_terms(r, ("摘要", "结论", "建议", "下一步", "路线图")), 2, "包含面向客户的结论/建议表达"),
        _make_check(lambda r, c: not _contains_terms(r, ("TODO", "占位", "lorem", "示例文本")), 2, "未出现占位内容"),
        _make_check(lambda r, c: _list_len(r, ("next_action_suggestions",), ("sections", "08_risk_warnings_and_next_steps", "next_action_checklist")) > 0, 2, "包含下一步行动清单"),
    ),
}

_ISSUES = {
    "data_completeness": "关键章节或结构化字段不完整，无法支撑完整客户交付。",
    "citation_completeness": "部分事实、政策、市场或资源建议缺少可追溯 citations。",
    "market_analysis_depth": "市场选择缺少需求、竞争、准入或量化优先级分析。",
    "company_diagnosis_depth": "企业/产品诊断不够具体，优势、短板和成熟度证据不足。",
    "channel_execution_feasibility": "渠道方案动作、资源、时间或执行责任不够明确。",
    "financing_analysis_depth": "投融资、预算、扩产或现金流假设不够充分。",
    "risk_coverage": "风险清单覆盖不足或缺少应对措施。",
    "budget_kpi_quantification": "预算、KPI、阶段目标和量化口径不足。",
    "roadmap_clarity_12_24_months": "12-24 个月路线图阶段、里程碑或产出不清晰。",
    "client_delivery_readability": "报告结构、摘要结论或下一步建议不足以直接面向客户交付。",
}

_SUGGESTIONS = {
    "data_completeness": "补齐企业诊断、市场选择、渠道、融资、风险和路线图等必备模块，并填充结构化字段。",
    "citation_completeness": "为市场数据、政策准入、渠道资源、风险和预算假设补充 citations/source_urls，并标注待人工复核项。",
    "market_analysis_depth": "按目标国家补充市场规模/需求、竞争格局、准入壁垒、客户画像和优先级评分理由。",
    "company_diagnosis_depth": "结合企业主数据和产品资料补充优势、短板、认证、产能、团队和产品竞争力诊断。",
    "channel_execution_feasibility": "把渠道路径拆成目标客户、伙伴类型、获客动作、资源清单、负责人和时间节点。",
    "financing_analysis_depth": "补充融资用途、预算分解、扩产假设、现金流/回收期和敏感性分析。",
    "risk_coverage": "至少覆盖合规认证、贸易税务、汇率、物流、合同、数据和运营风险，并给出缓释措施。",
    "budget_kpi_quantification": "为每个阶段补充预算、线索数、转化率、收入/订单、渠道数量等可量化 KPI。",
    "roadmap_clarity_12_24_months": "按 0-6、6-12、12-24 个月列出行动、交付物、资源需求、KPI 和关键依赖。",
    "client_delivery_readability": "增加管理层摘要、清晰标题、结论先行、下一步行动清单和可阅读的客户交付表述。",
}
