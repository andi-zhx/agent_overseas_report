"""Loader and typed accessors for overseas-plan knowledge-base templates.

The initial template library is intentionally stored as JSON seed data under
``agent_overseas_report/knowledge_base/templates`` instead of being embedded in
LLM prompts. This keeps the knowledge base maintainable and makes it ready to
be migrated to database tables or a background admin service later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

TEMPLATE_DATA_PACKAGE = "agent_overseas_report.knowledge_base.templates"


@dataclass(slots=True)
class IndustryTemplate:
    """Industry-level guidance used to draft overseas expansion plans."""

    industry_name: str
    typical_products: list[str]
    suitable_regions: list[str]
    common_entry_modes: list[str]
    key_certifications: list[str]
    pricing_logic: str
    common_channels: list[str]
    common_trade_shows: list[str]
    major_risks: list[str]
    recommended_strategy: str


@dataclass(slots=True)
class CountryTemplate:
    """Country/region-level market and entry guidance."""

    country_name: str
    region: str
    market_opportunity: str
    policy_environment: str
    tariff_or_access_notes: str
    common_channels: list[str]
    logistics_notes: str
    local_partner_types: list[str]
    relevant_trade_shows: list[str]
    business_associations: list[str]
    entry_difficulty: str
    market_potential: str
    recommended_industries: list[str]


@dataclass(slots=True)
class ResourceTemplate:
    """Resource-type guidance for matching external overseas service resources."""

    resource_type: str
    resource_category: str
    resource_subtype: str
    description: str
    applicable_industries: list[str]
    applicable_regions: list[str]
    matching_tags: list[str]
    selection_criteria: list[str]
    maintenance_fields: list[str]
    recommended_use: str


@dataclass
class KnowledgeBaseTemplateRepository:
    """Read-only repository over JSON template seed files.

    Args:
        template_dir: Optional filesystem directory containing
            ``industry_templates.json``, ``country_templates.json`` and
            ``resource_templates.json``. When omitted, bundled package seed data
            is used.
    """

    template_dir: Path | None = None
    _industry_file: str = field(default="industry_templates.json", init=False, repr=False)
    _country_file: str = field(default="country_templates.json", init=False, repr=False)
    _resource_file: str = field(default="resource_templates.json", init=False, repr=False)

    @cached_property
    def industry_templates(self) -> list[IndustryTemplate]:
        """Return all industry templates from the maintainable knowledge base."""

        return [IndustryTemplate(**item) for item in self._load_json_list(self._industry_file)]

    @cached_property
    def country_templates(self) -> list[CountryTemplate]:
        """Return all country/region templates from the maintainable knowledge base."""

        return [CountryTemplate(**item) for item in self._load_json_list(self._country_file)]

    @cached_property
    def resource_templates(self) -> list[ResourceTemplate]:
        """Return all resource-type templates from the maintainable knowledge base."""

        return [ResourceTemplate(**item) for item in self._load_json_list(self._resource_file)]

    def get_industry(self, industry_name: str) -> IndustryTemplate | None:
        """Find one industry template by exact industry name."""

        normalized = _normalize_key(industry_name)
        return _first_match(self.industry_templates, normalized, "industry_name")

    def get_country(self, country_name: str) -> CountryTemplate | None:
        """Find one country/region template by exact country name."""

        normalized = _normalize_key(country_name)
        return _first_match(self.country_templates, normalized, "country_name")

    def get_resource_type(self, resource_type: str) -> ResourceTemplate | None:
        """Find one resource template by exact resource type."""

        normalized = _normalize_key(resource_type)
        return _first_match(self.resource_templates, normalized, "resource_type")

    def match_industries(self, *, region: str | None = None, country_name: str | None = None) -> list[IndustryTemplate]:
        """Match industry templates by target region or recommended country industries."""

        candidates = self.industry_templates
        matched_names: set[str] | None = None
        if country_name:
            country = self.get_country(country_name)
            if country:
                matched_names = {_normalize_key(name) for name in country.recommended_industries}

        return [
            item
            for item in candidates
            if (region is None or _contains_normalized(item.suitable_regions, region))
            and (matched_names is None or _normalize_key(item.industry_name) in matched_names)
        ]

    def match_countries(self, *, industry_name: str | None = None, region: str | None = None) -> list[CountryTemplate]:
        """Match country templates by recommended industry and/or region."""

        return [
            item
            for item in self.country_templates
            if (industry_name is None or _contains_normalized(item.recommended_industries, industry_name))
            and (region is None or _normalize_key(item.region) == _normalize_key(region))
        ]

    def match_resources(
        self,
        *,
        resource_type: str | None = None,
        industry_name: str | None = None,
        region: str | None = None,
    ) -> list[ResourceTemplate]:
        """Match resource templates by resource type, industry and/or region."""

        return [
            item
            for item in self.resource_templates
            if (resource_type is None or _normalize_key(item.resource_type) == _normalize_key(resource_type))
            and (industry_name is None or _contains_normalized(item.applicable_industries, industry_name))
            and (region is None or _contains_normalized(item.applicable_regions, region))
        ]

    def _load_json_list(self, filename: str) -> list[dict[str, Any]]:
        if self.template_dir is not None:
            content = (self.template_dir / filename).read_text(encoding="utf-8")
        else:
            content = resources.files(TEMPLATE_DATA_PACKAGE).joinpath(filename).read_text(encoding="utf-8")

        payload = json.loads(content)
        if not isinstance(payload, list):
            raise ValueError(f"Template file {filename} must contain a JSON array")
        return payload


def get_default_template_repository() -> KnowledgeBaseTemplateRepository:
    """Create a repository backed by the bundled JSON template seed files."""

    return KnowledgeBaseTemplateRepository()


def _first_match(items: Iterable[Any], normalized: str, attribute_name: str) -> Any | None:
    for item in items:
        if _normalize_key(getattr(item, attribute_name)) == normalized:
            return item
    return None


def _contains_normalized(values: Iterable[str], expected: str) -> bool:
    expected_key = _normalize_key(expected)
    return any(_normalize_key(value) == expected_key for value in values)


def _normalize_key(value: str) -> str:
    return value.strip().casefold()
