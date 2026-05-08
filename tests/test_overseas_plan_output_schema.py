from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from agent_overseas_report.prompts import INVESTMENT_GRADE_REPORT_MODULES, STANDARD_MODULE_FIELDS
from agent_overseas_report.schemas.overseas_plan_output_schema import (
    OVERSEAS_PLAN_OUTPUT_SCHEMA,
    OverseasPlanOutputSchemaError,
    validate_overseas_plan_output_schema,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "investment_grade_overseas_plan_sample.json"


def _load_sample() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_output_json_schema_declares_eighteen_modules_and_required_fields():
    report_def = OVERSEAS_PLAN_OUTPUT_SCHEMA["$defs"]["investment_analysis_report"]
    module_def = OVERSEAS_PLAN_OUTPUT_SCHEMA["$defs"]["report_module"]

    assert report_def["required"] == list(INVESTMENT_GRADE_REPORT_MODULES)
    assert module_def["required"] == list(STANDARD_MODULE_FIELDS)
    assert "sections" in OVERSEAS_PLAN_OUTPUT_SCHEMA["required"]


def test_investment_grade_sample_passes_schema_validation():
    sample = _load_sample()

    validate_overseas_plan_output_schema(sample)


def test_schema_validation_rejects_missing_module_fields():
    sample = _load_sample()
    broken = deepcopy(sample)
    del broken["investment_analysis_report"]["executive_summary"]["citations"]

    with pytest.raises(OverseasPlanOutputSchemaError, match="executive_summary missing fields: citations"):
        validate_overseas_plan_output_schema(broken)


def test_schema_validation_rejects_missing_legacy_sections():
    sample = _load_sample()
    broken = deepcopy(sample)
    del broken["sections"]["04_overseas_resource_matching_plan"]

    with pytest.raises(OverseasPlanOutputSchemaError, match="legacy compatibility modules"):
        validate_overseas_plan_output_schema(broken)
