from __future__ import annotations

from datetime import datetime, timedelta, timezone

pytest_plugins = ()

from agent_overseas_report.services.web_research_service import (
    DefaultWebResearchService,
    InMemoryWebResearchSourceRepository,
    WebResearchRequest,
    WebResearchTopic,
    WebSearchResult,
    build_web_research_queries,
    score_source_reliability,
)


class FakeSearchClient:
    def __init__(self, results: list[WebSearchResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def search(self, query: str, *, top_k: int = 5) -> list[WebSearchResult]:
        self.calls.append(query)
        return self.results[:top_k]


def test_web_research_builds_all_required_topic_queries() -> None:
    request = WebResearchRequest(
        enterprise_id="ent-1",
        product_ids=["prod-1"],
        enterprise_name="示例医疗科技",
        product_names=["便携式检测仪"],
        industry="医疗器械",
        target_countries=["德国"],
    )

    topics = {item["topic"] for item in build_web_research_queries(request)}

    assert topics == {topic.value for topic in WebResearchTopic}


def test_web_research_persists_source_scores_reliability_and_uses_cache() -> None:
    repo = InMemoryWebResearchSourceRepository()
    search_client = FakeSearchClient(
        [
            WebSearchResult(
                title="Germany medical devices import rules",
                url="https://trade.gov/germany-medical-devices",
                snippet="Official market access and import rules.",
                publish_date="2026-01-15",
            )
        ]
    )
    service = DefaultWebResearchService(search_client=search_client, source_repository=repo)
    request = WebResearchRequest(
        enterprise_id="ent-1",
        product_ids=["prod-1"],
        enterprise_name="示例医疗科技",
        product_names=["便携式检测仪"],
        industry="医疗器械",
        target_countries=["德国"],
        topics=[WebResearchTopic.IMPORT_POLICY],
    )

    first = service.research(request)
    second = service.research(request)

    assert len(first.sources) == 1
    assert first.sources[0].source_domain == "trade.gov"
    assert first.sources[0].retrieved_at is not None
    assert first.sources[0].reliability_score >= 0.9
    assert repo.sources[0].query.endswith("government customs")
    assert len(search_client.calls) == 1
    assert second.sources[0].url == first.sources[0].url


def test_web_research_marks_manual_review_when_no_source() -> None:
    service = DefaultWebResearchService(search_client=FakeSearchClient([]))
    request = WebResearchRequest(
        enterprise_id="ent-1",
        product_ids=[],
        enterprise_name="示例医疗科技",
        product_names=[],
        industry="医疗器械",
        target_countries=["德国"],
        topics=[WebResearchTopic.TARIFF],
    )

    result = service.research(request)
    context = result.to_retrieved_context()

    assert result.sources == []
    assert "需人工复核" in result.manual_review_items[0]
    assert context[-1]["source_kind"] == "manual_review_required"


def test_reliability_scorer_prioritizes_official_sources() -> None:
    official = score_source_reliability(domain="customs.gov", source_type="official_government_or_multilateral", url="https://customs.gov/tariff", title="Tariff")
    blog = score_source_reliability(domain="example.com", source_type="public_web", url="https://example.com/blog/tariff", title="Blog")

    assert official > blog
