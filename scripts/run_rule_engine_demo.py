"""Run a local rule-engine demo and print structured JSON.

Usage:
    python scripts/run_rule_engine_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_overseas_report.services import OverseasRuleEngine


DEMO_INPUT = {
    "enterprise": {"name": "示例医疗科技", "industry": "医疗器械"},
    "products": [
        {
            "name": "家用监测设备",
            "product_type": "诊断设备",
            "hs_code": "901819",
            "overseas_version": True,
            "localized_features": ["英文界面", "欧盟电压适配"],
            "price_band": "中高端",
        }
    ],
    "attachments": ["catalog.pdf", "test-report.pdf"],
    "certifications": ["ISO 13485", "CE MDR"],
    "capacity": {"monthly_units": 12000, "lead_time_days": 30},
    "moq": 100,
    "suppliers": ["核心传感器供应商A", "包装供应商B"],
    "quality_system": "ISO 9001",
    "after_sales": "远程售后 + 备件包",
    "overseas_customers": ["UAE distributor", "Malaysia clinic chain"],
    "overseas_channels": ["注册代理", "区域经销商"],
    "english_materials": ["英文官网", "英文画册", "英文说明书", "英文案例"],
    "team": {"international_members": 4, "languages": ["英语", "阿拉伯语"], "export_years": 3},
    "finance": {"export_budget": 800000, "credit_line": 2000000},
    "target_markets": ["中东", "东南亚"],
    "price_band": "中高端",
}


if __name__ == "__main__":
    result = OverseasRuleEngine().evaluate(DEMO_INPUT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
