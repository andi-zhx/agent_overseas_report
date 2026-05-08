"""Maintainable knowledge-base templates and local ingestion utilities."""

from agent_overseas_report.knowledge_base.parsers import ParsedTextBlock, identify_file_type, parse_document, split_text_blocks
from agent_overseas_report.knowledge_base.rag import EmbeddingService, HashingEmbeddingService, LocalFAISSVectorStore, VectorStore
from agent_overseas_report.knowledge_base.repository import (
    CountryTemplate,
    IndustryTemplate,
    KnowledgeBaseTemplateRepository,
    ResourceTemplate,
    get_default_template_repository,
)

__all__ = [
    "CountryTemplate",
    "EmbeddingService",
    "HashingEmbeddingService",
    "IndustryTemplate",
    "KnowledgeBaseTemplateRepository",
    "LocalFAISSVectorStore",
    "ParsedTextBlock",
    "ResourceTemplate",
    "VectorStore",
    "get_default_template_repository",
    "identify_file_type",
    "parse_document",
    "split_text_blocks",
]
