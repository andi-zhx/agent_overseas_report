"""Centralized prompt templates for overseas report generation."""

from .overseas_plan_prompt import (
    INVESTMENT_GRADE_REPORT_MODULES,
    LEGACY_SEVEN_SECTION_KEYS,
    OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE,
    OVERSEAS_PLAN_SYSTEM_PROMPT,
    STANDARD_MODULE_FIELDS,
    build_overseas_plan_prompts,
    build_overseas_plan_user_prompt,
)

__all__ = [
    "INVESTMENT_GRADE_REPORT_MODULES",
    "LEGACY_SEVEN_SECTION_KEYS",
    "OVERSEAS_PLAN_JSON_STRUCTURE_EXAMPLE",
    "OVERSEAS_PLAN_SYSTEM_PROMPT",
    "STANDARD_MODULE_FIELDS",
    "build_overseas_plan_prompts",
    "build_overseas_plan_user_prompt",
]
