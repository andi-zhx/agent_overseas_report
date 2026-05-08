"""Source-preserving public web research ports and default implementation.

The module is intentionally framework-agnostic and CrewAI-independent.  It can
be called by synchronous services, background jobs, API handlers, or future
agent workflows without depending on any one orchestration library.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from agent_overseas_report.models.overseas_generation import utc_now


class WebResearchTopic(str, Enum):
    """Supported public-research topics for overseas expansion reports."""

    MARKET_SIZE = "target_country_market_size"
    INDUSTRY_GROWTH_RATE = "industry_growth_rate"
    IMPORT_POLICY = "import_policy"
    TARIFF = "tariff"
    CERTIFICATION_ACCESS = "certification_access"
    EXHIBITION = "exhibition"
    COMPETITOR_COMPANY = "competitor_company"
    CHANNEL_DISTRIBUTOR = "channel_distributor"
    BUYER = "buyer"
    INDUSTRIAL_PARK_OR_OVERSEAS_WAREHOUSE = "industrial_park_or_overseas_warehouse"


DEFAULT_WEB_RESEARCH_TOPICS: tuple[WebResearchTopic, ...] = tuple(WebResearchTopic)


@dataclass(slots=True)
class WebSearchResult:
    """Single result returned by a replaceable web-search adapter."""

    title: str
    url: str
    snippet: str
    publish_date: date | str | None = None
    source_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSearchClient(Protocol):
    """Abstract search-client port so the concrete API can be replaced later."""

    def search(self, query: str, *, top_k: int = 5) -> list[WebSearchResult]:
        """Return source-bearing public web search results for ``query``."""


@dataclass(slots=True)
class WebResearchSource:
    """Persistable public source captured during web research."""

    id: str
    query: str
    title: str
    url: str
    snippet: str
    source_domain: str
    publish_date: date | str | None
    retrieved_at: datetime | str
    reliability_score: float
    source_type: str
    related_enterprise_id: str | None = None
    related_product_id: str | None = None
    related_country: str | None = None
    related_industry: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        payload = asdict(self)
        if isinstance(self.publish_date, date):
            payload["publish_date"] = self.publish_date.isoformat()
        if isinstance(self.retrieved_at, datetime):
            payload["retrieved_at"] = self.retrieved_at.isoformat()
        return payload


class WebResearchSourceRepository(Protocol):
    """Persistence port for source-preserving web research records."""

    def save_sources(self, sources: list[WebResearchSource]) -> list[WebResearchSource]: ...

    def find_cached_sources(
        self,
        *,
        query: str,
        related_enterprise_id: str | None = None,
        related_product_id: str | None = None,
        related_country: str | None = None,
        related_industry: str | None = None,
        min_retrieved_at: datetime | None = None,
    ) -> list[WebResearchSource]: ...


class InMemoryWebResearchSourceRepository:
    """In-memory source repository for tests, demos and local jobs."""

    def __init__(self) -> None:
        self.sources: list[WebResearchSource] = []

    def save_sources(self, sources: list[WebResearchSource]) -> list[WebResearchSource]:
        for source in sources:
            if not any(existing.url == source.url and existing.query == source.query for existing in self.sources):
                self.sources.append(copy.deepcopy(source))
        return copy.deepcopy(sources)

    def find_cached_sources(
        self,
        *,
        query: str,
        related_enterprise_id: str | None = None,
        related_product_id: str | None = None,
        related_country: str | None = None,
        related_industry: str | None = None,
        min_retrieved_at: datetime | None = None,
    ) -> list[WebResearchSource]:
        matched: list[WebResearchSource] = []
        for source in self.sources:
            retrieved_at = _coerce_datetime(source.retrieved_at)
            if source.query != query:
                continue
            if min_retrieved_at and retrieved_at and retrieved_at < min_retrieved_at:
                continue
            if related_enterprise_id is not None and source.related_enterprise_id != related_enterprise_id:
                continue
            if related_product_id is not None and source.related_product_id != related_product_id:
                continue
            if related_country is not None and source.related_country != related_country:
                continue
            if related_industry is not None and source.related_industry != related_industry:
                continue
            matched.append(copy.deepcopy(source))
        return sorted(matched, key=lambda item: item.reliability_score, reverse=True)


@dataclass(slots=True)
class WebResearchRequest:
    """Inputs for one source-preserving external research run."""

    enterprise_id: str | None
    product_ids: list[str]
    enterprise_name: str | None
    product_names: list[str]
    industry: str
    target_countries: list[str]
    topics: list[WebResearchTopic] = field(default_factory=lambda: list(DEFAULT_WEB_RESEARCH_TOPICS))
    top_k_per_query: int = 5
    force_refresh: bool = False


@dataclass(slots=True)
class WebResearchResult:
    """External research output plus explicit manual-review gaps."""

    sources: list[WebResearchSource]
    manual_review_items: list[str]
    retrieved_at: datetime

    def to_retrieved_context(self) -> list[dict[str, Any]]:
        """Convert web sources to the prompt's source-preserving context shape."""

        context = [
            {
                "source_kind": "public_web",
                "query": source.query,
                "title": source.title,
                "url": source.url,
                "snippet": source.snippet,
                "source_domain": source.source_domain,
                "publish_date": source.publish_date.isoformat() if isinstance(source.publish_date, date) else source.publish_date,
                "retrieved_at": source.retrieved_at.isoformat() if isinstance(source.retrieved_at, datetime) else source.retrieved_at,
                "reliability_score": source.reliability_score,
                "source_type": source.source_type,
                "related_country": source.related_country,
                "related_industry": source.related_industry,
                "metadata": copy.deepcopy(source.metadata),
                "usage_note": "仅可作为有来源的外部公开资料；动态结论仍需标注“需人工复核”。",
            }
            for source in self.sources
        ]
        if self.manual_review_items:
            context.append(
                {
                    "source_kind": "manual_review_required",
                    "retrieved_at": self.retrieved_at.isoformat(),
                    "manual_review_items": list(self.manual_review_items),
                    "usage_note": "未检索到可记录来源的外部资料，不得编造；报告中必须标注“需人工复核”。",
                }
            )
        return context


class WebResearchService(Protocol):
    """Abstract web-research service used by report generation on demand."""

    def research(self, request: WebResearchRequest) -> WebResearchResult:
        """Retrieve and persist source-preserving public information."""


@dataclass(slots=True)
class DefaultWebResearchService:
    """Default source-preserving implementation with cache and scoring."""

    search_client: WebSearchClient
    source_repository: WebResearchSourceRepository = field(default_factory=InMemoryWebResearchSourceRepository)
    cache_ttl_hours: int = 24

    def research(self, request: WebResearchRequest) -> WebResearchResult:
        retrieved_at = utc_now()
        sources: list[WebResearchSource] = []
        manual_review_items: list[str] = []
        seen: set[tuple[str, str]] = set()

        for query_spec in build_web_research_queries(request):
            cached = [] if request.force_refresh else self._get_cached_sources(query_spec["query"], request, query_spec)
            query_sources = cached or self._search_and_persist(query_spec["query"], request, query_spec, retrieved_at)
            if not query_sources:
                manual_review_items.append(f"{query_spec['label']} 未检索到可记录来源的公开资料，需人工复核。")
            for source in query_sources:
                key = (source.query, source.url)
                if key not in seen:
                    seen.add(key)
                    sources.append(source)

        sources.sort(key=lambda item: item.reliability_score, reverse=True)
        return WebResearchResult(sources=sources, manual_review_items=manual_review_items, retrieved_at=retrieved_at)

    def _get_cached_sources(
        self, query: str, request: WebResearchRequest, query_spec: dict[str, str | None]
    ) -> list[WebResearchSource]:
        min_retrieved_at = utc_now() - timedelta(hours=self.cache_ttl_hours)
        return self.source_repository.find_cached_sources(
            query=query,
            related_enterprise_id=request.enterprise_id,
            related_product_id=query_spec.get("product_id"),
            related_country=query_spec.get("country"),
            related_industry=request.industry,
            min_retrieved_at=min_retrieved_at,
        )

    def _search_and_persist(
        self,
        query: str,
        request: WebResearchRequest,
        query_spec: dict[str, str | None],
        retrieved_at: datetime,
    ) -> list[WebResearchSource]:
        search_results = self.search_client.search(query, top_k=request.top_k_per_query)
        sources = [
            source_from_search_result(
                result,
                query=query,
                retrieved_at=retrieved_at,
                related_enterprise_id=request.enterprise_id,
                related_product_id=query_spec.get("product_id"),
                related_country=query_spec.get("country"),
                related_industry=request.industry,
                topic=query_spec.get("topic"),
            )
            for result in search_results
            if result.url and result.title
        ]
        return self.source_repository.save_sources(sources) if sources else []


@dataclass(slots=True)
class WebResearchTask:
    """Framework-neutral external research task object."""

    service: WebResearchService
    request: WebResearchRequest

    def execute(self) -> WebResearchResult:
        """Run the task and return persisted sources plus manual-review gaps."""

        return self.service.research(self.request)


def build_web_research_queries(request: WebResearchRequest) -> list[dict[str, str | None]]:
    """Build topic-specific search queries without creating fake sources."""

    product_names = request.product_names or [None]
    countries = request.target_countries or [None]
    queries: list[dict[str, str | None]] = []
    for country in countries:
        for topic in request.topics:
            product_iter = product_names if topic in _PRODUCT_SCOPED_TOPICS else [None]
            for product_name in product_iter:
                queries.append(
                    {
                        "topic": topic.value,
                        "label": _TOPIC_LABELS[topic],
                        "country": country,
                        "product_id": _product_id_for_name(product_name, request),
                        "query": _query_for_topic(topic, industry=request.industry, country=country, product_name=product_name),
                    }
                )
    return queries


def source_from_search_result(
    result: WebSearchResult,
    *,
    query: str,
    retrieved_at: datetime,
    related_enterprise_id: str | None,
    related_product_id: str | None,
    related_country: str | None,
    related_industry: str | None,
    topic: str | None,
) -> WebResearchSource:
    """Normalize a search result into a persistable source record."""

    domain = normalize_domain(result.url)
    source_type = result.source_type or infer_source_type(domain, result.url, result.title)
    reliability_score = score_source_reliability(domain=domain, source_type=source_type, url=result.url, title=result.title)
    return WebResearchSource(
        id=f"wrs_{uuid4().hex}",
        query=query,
        title=result.title,
        url=result.url,
        snippet=result.snippet,
        source_domain=domain,
        publish_date=_coerce_date(result.publish_date),
        retrieved_at=retrieved_at,
        reliability_score=reliability_score,
        source_type=source_type,
        related_enterprise_id=related_enterprise_id,
        related_product_id=related_product_id,
        related_country=related_country,
        related_industry=related_industry,
        metadata={"topic": topic, **copy.deepcopy(result.metadata)},
    )


def normalize_domain(url: str) -> str:
    """Return a normalized source domain for scoring and display."""

    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def infer_source_type(domain: str, url: str, title: str) -> str:
    """Infer a source type used by the reliability scorer."""

    text = f"{domain} {url} {title}".lower()
    if any(token in text for token in [".gov", "government", "customs", "trade.gov", "wto.org", "worldbank.org", "imf.org", "oecd.org", "europa.eu"]):
        return "official_government_or_multilateral"
    if any(token in text for token in ["association", "chamber", "协会", "商会"]):
        return "industry_association"
    if any(token in text for token in ["expo", "fair", "exhibition", "展会"]):
        return "exhibition_official"
    if any(token in text for token in ["annual-report", "annual report", "investor", "sec.gov", "年报"]):
        return "listed_company_annual_report"
    if any(token in text for token in ["news", "reuters", "bloomberg", "财新"]):
        return "news_media"
    return "public_web"


def score_source_reliability(*, domain: str, source_type: str, url: str, title: str) -> float:
    """Score source reliability, prioritizing official and primary sources."""

    type_scores = {
        "official_government_or_multilateral": 0.95,
        "industry_association": 0.85,
        "exhibition_official": 0.82,
        "listed_company_annual_report": 0.8,
        "news_media": 0.6,
        "public_web": 0.45,
    }
    score = type_scores.get(source_type, 0.45)
    if domain.endswith(".gov") or ".gov." in domain or domain.endswith(".europa.eu"):
        score = max(score, 0.95)
    if any(primary in domain for primary in ["wto.org", "worldbank.org", "imf.org", "oecd.org", "customs"]):
        score = max(score, 0.92)
    if any(token in f"{url} {title}".lower() for token in ["blog", "forum", "wikipedia"]):
        score = min(score, 0.4)
    return round(score, 2)


_TOPIC_LABELS: dict[WebResearchTopic, str] = {
    WebResearchTopic.MARKET_SIZE: "目标国家市场规模",
    WebResearchTopic.INDUSTRY_GROWTH_RATE: "行业增长率",
    WebResearchTopic.IMPORT_POLICY: "进口政策",
    WebResearchTopic.TARIFF: "关税",
    WebResearchTopic.CERTIFICATION_ACCESS: "认证准入",
    WebResearchTopic.EXHIBITION: "展会",
    WebResearchTopic.COMPETITOR_COMPANY: "竞品公司",
    WebResearchTopic.CHANNEL_DISTRIBUTOR: "渠道代理商",
    WebResearchTopic.BUYER: "采购商",
    WebResearchTopic.INDUSTRIAL_PARK_OR_OVERSEAS_WAREHOUSE: "产业园区或海外仓",
}

_PRODUCT_SCOPED_TOPICS = {
    WebResearchTopic.TARIFF,
    WebResearchTopic.CERTIFICATION_ACCESS,
    WebResearchTopic.COMPETITOR_COMPANY,
    WebResearchTopic.CHANNEL_DISTRIBUTOR,
    WebResearchTopic.BUYER,
}


def _query_for_topic(topic: WebResearchTopic, *, industry: str, country: str | None, product_name: str | None) -> str:
    country_part = country or "目标国家"
    product_part = product_name or industry
    templates = {
        WebResearchTopic.MARKET_SIZE: f"{country_part} {industry} market size official report",
        WebResearchTopic.INDUSTRY_GROWTH_RATE: f"{country_part} {industry} industry growth rate association report",
        WebResearchTopic.IMPORT_POLICY: f"{country_part} import policy {industry} government customs",
        WebResearchTopic.TARIFF: f"{country_part} tariff import duty {product_part} customs HS code",
        WebResearchTopic.CERTIFICATION_ACCESS: f"{country_part} certification market access {product_part} official requirements",
        WebResearchTopic.EXHIBITION: f"{country_part} {industry} trade fair exhibition official",
        WebResearchTopic.COMPETITOR_COMPANY: f"{country_part} {product_part} competitor company annual report",
        WebResearchTopic.CHANNEL_DISTRIBUTOR: f"{country_part} {product_part} distributor channel association",
        WebResearchTopic.BUYER: f"{country_part} {product_part} buyer procurement importer directory",
        WebResearchTopic.INDUSTRIAL_PARK_OR_OVERSEAS_WAREHOUSE: f"{country_part} {industry} industrial park overseas warehouse official",
    }
    return templates[topic]


def _product_id_for_name(product_name: str | None, request: WebResearchRequest) -> str | None:
    if product_name is None:
        return None
    try:
        index = request.product_names.index(product_name)
    except ValueError:
        return None
    return request.product_ids[index] if index < len(request.product_ids) else None


def _coerce_date(value: date | str | None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
