"""Context assembly for overseas-plan report generation.

The builder centralizes every source of information that should be visible to
an LLM before report generation.  It intentionally keeps source provenance next
to the facts so downstream prompts can require citation-aware writing instead
of relying only on free-form user input.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CitationContext:
    """A source reference that can be cited by generated report claims."""

    citation_id: str
    source_type: str
    title: str
    source_ref: str
    reliability_score: float | None = None
    retrieved_at: str | None = None
    related_fields: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable citation payload."""

        return asdict(self)


@dataclass(slots=True)
class LocalKnowledgeContext:
    """Source-preserving local RAG chunks used to enrich the report context."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    citations: list[CitationContext] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable local-knowledge context."""

        return {
            "chunks": copy.deepcopy(self.chunks),
            "citations": [citation.to_dict() for citation in self.citations],
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class WebResearchContext:
    """Source-preserving public web research context."""

    sources: list[dict[str, Any]] = field(default_factory=list)
    citations: list[CitationContext] = field(default_factory=list)
    manual_review_items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable web-research context."""

        return {
            "sources": copy.deepcopy(self.sources),
            "citations": [citation.to_dict() for citation in self.citations],
            "manual_review_items": list(self.manual_review_items),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class RuleEngineContext:
    """Deterministic rule-engine output plus its provenance citation."""

    outputs: dict[str, Any] = field(default_factory=dict)
    citations: list[CitationContext] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable rule-engine context."""

        return {
            "outputs": copy.deepcopy(self.outputs),
            "citations": [citation.to_dict() for citation in self.citations],
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class MissingFieldContext:
    """Structured data-gap analysis that must be reflected in the report."""

    fields: list[dict[str, Any]] = field(default_factory=list)
    critical_missing_fields: list[str] = field(default_factory=list)
    status: str | None = None
    manual_review_required: bool = False
    prompt_instruction: str | None = None
    citations: list[CitationContext] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable missing-field context."""

        return {
            "fields": copy.deepcopy(self.fields),
            "critical_missing_fields": list(self.critical_missing_fields),
            "status": self.status,
            "manual_review_required": self.manual_review_required,
            "prompt_instruction": self.prompt_instruction,
            "citations": [citation.to_dict() for citation in self.citations],
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class ContextBundle:
    """Complete pre-LLM context bundle for overseas-plan generation."""

    enterprise_profile: dict[str, Any]
    product_profile: list[dict[str, Any]]
    user_parameters: dict[str, Any]
    retrieved_local_chunks: list[dict[str, Any]]
    web_research_sources: list[dict[str, Any]]
    rule_engine_outputs: dict[str, Any]
    missing_fields: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    data_quality_warnings: list[str]
    local_knowledge_context: dict[str, Any]
    web_research_context: dict[str, Any]
    rule_engine_context: dict[str, Any]
    missing_field_context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable context bundle."""

        return asdict(self)


@dataclass(slots=True)
class ReportContextBuilder:
    """Build a citation-aware context bundle before report prompt creation."""

    def build(
        self,
        *,
        enterprise_data: dict[str, Any],
        user_parameters: dict[str, Any],
        local_chunks: list[dict[str, Any]] | None = None,
        web_research_sources: list[dict[str, Any]] | None = None,
        rule_engine_outputs: dict[str, Any] | None = None,
        missing_field_analysis: dict[str, Any] | None = None,
    ) -> ContextBundle:
        """Create a complete ``ContextBundle`` from structured and retrieved inputs."""

        local_chunks = copy.deepcopy(local_chunks or [])
        web_research_sources = copy.deepcopy(web_research_sources or [])
        rule_engine_outputs = copy.deepcopy(rule_engine_outputs or {})
        missing_field_analysis = copy.deepcopy(missing_field_analysis or {})

        enterprise_profile = self._build_enterprise_profile(enterprise_data)
        product_profile = self._build_product_profile(enterprise_data)

        citations: list[CitationContext] = []
        citations.append(
            CitationContext(
                citation_id="enterprise_profile:master_data",
                source_type="enterprise_master_data",
                title="企业结构化主数据",
                source_ref=str(enterprise_profile.get("id") or user_parameters.get("enterprise_id") or "enterprise_profile"),
                reliability_score=1.0,
                related_fields=sorted([key for key, value in enterprise_profile.items() if _has_value(value)]),
            )
        )
        for index, product in enumerate(product_profile):
            product_id = self._product_citation_key(product, index)
            citations.append(
                CitationContext(
                    citation_id=f"product_profile:{product_id}",
                    source_type="product_master_data",
                    title=f"产品结构化主数据：{product.get('name') or product_id}",
                    source_ref=product_id,
                    reliability_score=1.0,
                    related_fields=sorted([key for key, value in product.items() if _has_value(value)]),
                )
            )

        local_context = self._build_local_knowledge_context(local_chunks)
        web_context = self._build_web_research_context(web_research_sources)
        rule_context = self._build_rule_engine_context(rule_engine_outputs)
        missing_context = self._build_missing_field_context(missing_field_analysis)
        citations.extend(local_context.citations)
        citations.extend(web_context.citations)
        citations.extend(rule_context.citations)
        citations.extend(missing_context.citations)

        warnings = self._build_data_quality_warnings(
            local_context=local_context,
            web_context=web_context,
            rule_context=rule_context,
            missing_context=missing_context,
        )

        return ContextBundle(
            enterprise_profile={**enterprise_profile, "citation_ids": ["enterprise_profile:master_data"]},
            product_profile=[
                {**product, "citation_ids": [f"product_profile:{self._product_citation_key(product, index)}"]}
                for index, product in enumerate(product_profile)
            ],
            user_parameters=copy.deepcopy(user_parameters),
            retrieved_local_chunks=local_chunks,
            web_research_sources=web_research_sources,
            rule_engine_outputs=rule_engine_outputs,
            missing_fields=missing_context.fields,
            citations=[citation.to_dict() for citation in citations],
            data_quality_warnings=warnings,
            local_knowledge_context=local_context.to_dict(),
            web_research_context=web_context.to_dict(),
            rule_engine_context=rule_context.to_dict(),
            missing_field_context=missing_context.to_dict(),
        )

    def _product_citation_key(self, product: dict[str, Any], index: int) -> str:
        return str(product.get("id") or product.get("name") or index)

    def _build_enterprise_profile(self, enterprise_data: dict[str, Any]) -> dict[str, Any]:
        enterprise = enterprise_data.get("enterprise", {}) if isinstance(enterprise_data.get("enterprise"), dict) else {}
        return copy.deepcopy(enterprise)

    def _build_product_profile(self, enterprise_data: dict[str, Any]) -> list[dict[str, Any]]:
        products = enterprise_data.get("products", []) if isinstance(enterprise_data.get("products"), list) else []
        return [copy.deepcopy(product) for product in products if isinstance(product, dict)]

    def _build_local_knowledge_context(self, chunks: list[dict[str, Any]]) -> LocalKnowledgeContext:
        citations: list[CitationContext] = []
        warnings: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or f"local_chunk_{index}")
            citations.append(
                CitationContext(
                    citation_id=f"local_knowledge:{chunk_id}",
                    source_type="local_knowledge_base",
                    title=str(chunk.get("title") or chunk.get("source_title") or chunk.get("file_name") or chunk_id),
                    source_ref=str(chunk.get("source_uri") or chunk.get("source") or chunk.get("file_path") or chunk_id),
                    reliability_score=_coerce_float(chunk.get("relevance_score")),
                    related_fields=["retrieved_local_chunks"],
                    metadata={"chunk_id": chunk_id, "source_kind": chunk.get("source_kind")},
                )
            )
        if not chunks:
            warnings.append("未检索到本地知识库 RAG 片段；相关结论需依赖结构化数据或标注人工复核。")
        return LocalKnowledgeContext(chunks=chunks, citations=citations, warnings=warnings)

    def _build_web_research_context(self, sources: list[dict[str, Any]]) -> WebResearchContext:
        citations: list[CitationContext] = []
        manual_review_items: list[str] = []
        warnings: list[str] = []
        for index, source in enumerate(sources, start=1):
            if source.get("source_kind") == "manual_review_required":
                manual_review_items.extend(str(item) for item in source.get("manual_review_items", []) if item)
                continue
            source_id = str(source.get("id") or source.get("url") or f"web_source_{index}")
            citations.append(
                CitationContext(
                    citation_id=f"web_research:{index}",
                    source_type="public_web",
                    title=str(source.get("title") or source.get("source_domain") or source_id),
                    source_ref=str(source.get("url") or source_id),
                    reliability_score=_coerce_float(source.get("reliability_score")),
                    retrieved_at=str(source.get("retrieved_at")) if source.get("retrieved_at") else None,
                    related_fields=["web_research_sources"],
                    metadata={
                        "query": source.get("query"),
                        "source_domain": source.get("source_domain"),
                        "publish_date": source.get("publish_date"),
                    },
                )
            )
        if not citations:
            warnings.append("未获得可引用的网络研究来源；动态市场、政策、关税、展会等信息必须标注需人工复核。")
        return WebResearchContext(sources=sources, citations=citations, manual_review_items=manual_review_items, warnings=warnings)

    def _build_rule_engine_context(self, outputs: dict[str, Any]) -> RuleEngineContext:
        citations: list[CitationContext] = []
        warnings: list[str] = []
        if outputs:
            citations.append(
                CitationContext(
                    citation_id="rule_engine:overseas_rule_engine",
                    source_type="deterministic_rule_engine",
                    title="OverseasRuleEngine 规则引擎结果",
                    source_ref="agent_overseas_report.services.rule_engine.OverseasRuleEngine",
                    reliability_score=1.0,
                    related_fields=sorted(outputs.keys()),
                )
            )
        else:
            warnings.append("规则引擎未返回结果；国家优先级、成熟度和资源匹配建议需人工复核。")
        return RuleEngineContext(outputs=outputs, citations=citations, warnings=warnings)

    def _build_missing_field_context(self, analysis: dict[str, Any]) -> MissingFieldContext:
        fields: list[dict[str, Any]] = []
        for category in analysis.get("missing_categories", []) or []:
            if not isinstance(category, dict):
                continue
            category_name = str(category.get("category") or "未分类")
            for field_name in category.get("fields", []) or []:
                fields.append({"category": category_name, "field": str(field_name), "severity": category.get("severity") or analysis.get("status")})
        for field_name in analysis.get("critical_missing_fields", []) or []:
            if not any(item["field"] == field_name for item in fields):
                fields.append({"category": "关键缺失字段", "field": str(field_name), "severity": "critical"})
        citations = [
            CitationContext(
                citation_id="missing_fields:generation_readiness",
                source_type="missing_field_analysis",
                title="生成前缺失字段分析",
                source_ref="assess_generation_readiness",
                reliability_score=1.0,
                related_fields=[item["field"] for item in fields],
            )
        ]
        warnings = [str(analysis.get("message"))] if analysis.get("message") else []
        return MissingFieldContext(
            fields=fields,
            critical_missing_fields=[str(item) for item in analysis.get("critical_missing_fields", []) or []],
            status=analysis.get("status"),
            manual_review_required=bool(analysis.get("manual_review_required")),
            prompt_instruction=analysis.get("prompt_instruction"),
            citations=citations,
            warnings=warnings,
        )

    def _build_data_quality_warnings(
        self,
        *,
        local_context: LocalKnowledgeContext,
        web_context: WebResearchContext,
        rule_context: RuleEngineContext,
        missing_context: MissingFieldContext,
    ) -> list[str]:
        warnings: list[str] = []
        warnings.extend(local_context.warnings)
        warnings.extend(web_context.warnings)
        warnings.extend(web_context.manual_review_items)
        warnings.extend(rule_context.warnings)
        warnings.extend(missing_context.warnings)
        if missing_context.fields:
            warnings.append("存在缺失字段，报告必须写入 missing_fields 并避免编造。")
        if missing_context.manual_review_required:
            warnings.append("缺失字段分析要求人工补充/复核。")
        return _dedupe_strings(warnings)


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
