"""JSON Schema contract and lightweight validation for generated overseas plans."""

from __future__ import annotations

from typing import Any

from agent_overseas_report.prompts import INVESTMENT_GRADE_REPORT_MODULES, LEGACY_SEVEN_SECTION_KEYS, STANDARD_MODULE_FIELDS

CONFIDENCE_LEVELS = ("高", "中", "低")

OVERSEAS_PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://agent-overseas-report.local/schemas/overseas-plan-output.schema.json",
    "title": "一级市场投资分析师级企业出海方案输出",
    "type": "object",
    "required": ["report_title", "version", "language", "investment_analysis_report", "sections"],
    "properties": {
        "report_title": {"type": "string"},
        "version": {"type": "string"},
        "language": {"type": "string"},
        "investment_analysis_report": {"$ref": "#/$defs/investment_analysis_report"},
        "sections": {"$ref": "#/$defs/legacy_sections"},
        "global_manual_review_items": {"type": "array", "items": {"type": "string"}},
        "data_quality_notes": {"type": "array", "items": {"type": "string"}},
        "data_quality_review": {"type": "object"},
    },
    "$defs": {
        "investment_analysis_report": {
            "type": "object",
            "required": list(INVESTMENT_GRADE_REPORT_MODULES),
            "properties": {module: {"$ref": "#/$defs/report_module"} for module in INVESTMENT_GRADE_REPORT_MODULES},
            "additionalProperties": True,
        },
        "report_module": {
            "type": "object",
            "required": [*STANDARD_MODULE_FIELDS],
            "properties": {
                "title": {"type": "string"},
                "conclusion": {"type": "string"},
                "key_findings": {"type": "array", "items": {"type": ["object", "string"]}},
                "evidence": {"type": "array", "items": {"type": ["object", "string"]}},
                "recommendation": {"type": "array", "items": {"type": ["object", "string"]}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "missing_information": {"type": "array", "items": {"type": "string"}},
                "citations": {"type": "array", "items": {"$ref": "#/$defs/citation"}},
                "confidence_level": {"type": "string", "enum": [*CONFIDENCE_LEVELS]},
            },
            "additionalProperties": True,
        },
        "citation": {
            "type": "object",
            "required": ["citation_id", "source_title", "source_type", "excerpt_or_fact", "review_status"],
            "properties": {
                "citation_id": {"type": "string"},
                "source_title": {"type": "string"},
                "source_url": {"type": ["string", "null"]},
                "source_type": {"type": "string"},
                "excerpt_or_fact": {"type": "string"},
                "review_status": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "legacy_sections": {
            "type": "object",
            "required": list(LEGACY_SEVEN_SECTION_KEYS),
            "additionalProperties": True,
        },
    },
}


class OverseasPlanOutputSchemaError(ValueError):
    """Raised when generated plan output does not satisfy the JSON schema contract."""


def validate_overseas_plan_output_schema(payload: dict[str, Any]) -> None:
    """Validate the upgraded generated-plan payload against the local JSON Schema contract.

    The project intentionally keeps this validator dependency-free so unit tests
    and offline deployments can enforce the same structural contract even when
    the optional ``jsonschema`` package is not installed.
    """

    if not isinstance(payload, dict):
        raise OverseasPlanOutputSchemaError("Generated plan output must be a JSON object")
    for field_name in OVERSEAS_PLAN_OUTPUT_SCHEMA["required"]:
        if field_name not in payload:
            raise OverseasPlanOutputSchemaError(f"Generated plan output missing required field: {field_name}")
    report = payload.get("investment_analysis_report")
    if not isinstance(report, dict):
        raise OverseasPlanOutputSchemaError("investment_analysis_report must be an object")
    missing_modules = [module for module in INVESTMENT_GRADE_REPORT_MODULES if module not in report]
    if missing_modules:
        raise OverseasPlanOutputSchemaError(f"investment_analysis_report missing modules: {', '.join(missing_modules)}")
    for module_name in INVESTMENT_GRADE_REPORT_MODULES:
        module_payload = report[module_name]
        if not isinstance(module_payload, dict):
            raise OverseasPlanOutputSchemaError(f"{module_name} must be an object")
        missing_fields = [field_name for field_name in STANDARD_MODULE_FIELDS if field_name not in module_payload]
        if missing_fields:
            raise OverseasPlanOutputSchemaError(f"{module_name} missing fields: {', '.join(missing_fields)}")
        _validate_module_field_types(module_name, module_payload)
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        raise OverseasPlanOutputSchemaError("sections must be an object")
    missing_legacy_sections = [section for section in LEGACY_SEVEN_SECTION_KEYS if section not in sections]
    if missing_legacy_sections:
        raise OverseasPlanOutputSchemaError(f"sections missing legacy compatibility modules: {', '.join(missing_legacy_sections)}")


def _validate_module_field_types(module_name: str, module_payload: dict[str, Any]) -> None:
    if not isinstance(module_payload["conclusion"], str):
        raise OverseasPlanOutputSchemaError(f"{module_name}.conclusion must be a string")
    for field_name in ("key_findings", "evidence", "recommendation", "assumptions", "missing_information", "citations"):
        if not isinstance(module_payload[field_name], list):
            raise OverseasPlanOutputSchemaError(f"{module_name}.{field_name} must be an array")
    confidence_level = module_payload["confidence_level"]
    if confidence_level not in CONFIDENCE_LEVELS:
        raise OverseasPlanOutputSchemaError(f"{module_name}.confidence_level must be 高/中/低")
    for index, citation in enumerate(module_payload["citations"]):
        if not isinstance(citation, dict):
            raise OverseasPlanOutputSchemaError(f"{module_name}.citations[{index}] must be an object")
        for field_name in ("citation_id", "source_title", "source_type", "excerpt_or_fact", "review_status"):
            if field_name not in citation:
                raise OverseasPlanOutputSchemaError(f"{module_name}.citations[{index}] missing {field_name}")
