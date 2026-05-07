"""Maintainable knowledge-base templates for overseas plan generation."""

from agent_overseas_report.knowledge_base.repository import (
    CountryTemplate,
    IndustryTemplate,
    KnowledgeBaseTemplateRepository,
    ResourceTemplate,
    get_default_template_repository,
)

__all__ = [
    "CountryTemplate",
    "IndustryTemplate",
    "KnowledgeBaseTemplateRepository",
    "ResourceTemplate",
    "get_default_template_repository",
]
