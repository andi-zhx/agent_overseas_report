"""Deterministic overseas-expansion rule engine.

The engine runs before any DeepSeek call and converts enterprise/product facts
into structured JSON-ready recommendations. It deliberately uses only local
rules and the bundled template repository so it can be unit-tested without a
network connection or LLM credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from agent_overseas_report.knowledge_base.repository import (
    CountryTemplate,
    IndustryTemplate,
    KnowledgeBaseTemplateRepository,
    ResourceTemplate,
    get_default_template_repository,
)
from agent_overseas_report.models import MATURITY_SCORE_WEIGHTS, infer_maturity_level


CHANNEL_RULES: tuple[dict[str, Any], ...] = (
    {
        "channel_type": "经销代理",
        "industries": {"建材", "医疗器械", "工业设备", "食品及农产品", "电子产品", "家居用品", "纺织服装"},
        "product_keywords": {"设备", "器械", "建材", "耗材", "配件", "食品", "家居", "服装"},
        "base_score": 78,
    },
    {
        "channel_type": "跨境电商",
        "industries": {"消费品", "纺织服装", "电子产品", "家居用品", "食品及农产品"},
        "product_keywords": {"小家电", "个护", "服装", "家居", "礼品", "配件", "消费品"},
        "base_score": 74,
    },
    {
        "channel_type": "本地KA渠道",
        "industries": {"消费品", "食品及农产品", "家居用品", "电子产品", "纺织服装"},
        "product_keywords": {"食品", "饮料", "家居", "个护", "母婴", "服装", "小家电"},
        "base_score": 68,
    },
    {
        "channel_type": "工程渠道",
        "industries": {"建材", "工业设备", "电子产品"},
        "product_keywords": {"工程", "建材", "设备", "系统", "型材", "泵", "阀"},
        "base_score": 72,
    },
    {
        "channel_type": "海外合资/办事处",
        "industries": {"医疗器械", "工业设备", "电子产品", "建材"},
        "product_keywords": {"设备", "器械", "系统", "项目", "工程"},
        "base_score": 58,
    },
    {
        "channel_type": "本地仓",
        "industries": {"消费品", "食品及农产品", "电子产品", "家居用品", "纺织服装", "建材"},
        "product_keywords": {"高频", "易损", "大件", "备件", "快消", "服装", "食品"},
        "base_score": 60,
    },
    {
        "channel_type": "海外工厂",
        "industries": {"工业设备", "建材", "电子产品", "纺织服装", "食品及农产品"},
        "product_keywords": {"大批量", "关税", "本地化", "组装", "产能"},
        "base_score": 45,
    },
)

RESOURCE_TYPE_ALIASES: dict[str, list[str]] = {
    "展会": ["展会"],
    "推介会": ["展会", "商协会"],
    "采购对接会": ["展会", "商协会"],
    "商协会": ["商协会"],
    "渠道代理商": ["渠道代理商"],
    "物流/海外仓": ["物流服务商", "海外仓"],
    "认证机构": ["认证检测机构"],
}

_REQUIRED_FIELDS: dict[str, str] = {
    "enterprise.industry": "企业行业",
    "products": "产品信息",
    "certifications": "认证情况",
    "capacity.monthly_units": "产能",
    "moq": "MOQ",
    "overseas_customers": "海外客户",
    "english_materials": "英文资料",
    "team.international_members": "国际化团队",
    "finance.export_budget": "出海预算/资金能力",
}


@dataclass(slots=True)
class OverseasRuleEngine:
    """Local rule engine for overseas plans, independent from DeepSeek."""

    repository: KnowledgeBaseTemplateRepository = field(default_factory=get_default_template_repository)

    def evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run all rules and return a JSON-serializable result."""

        missing_fields = self.find_missing_fields(payload)
        maturity = self.assess_maturity(payload, missing_fields=missing_fields)
        country_recommendation = self.recommend_countries(payload, maturity["total_score"])
        channels = self.match_channels(payload, maturity["total_score"])
        resources = self.match_resources(payload, country_recommendation["recommended_country_names"])

        return {
            "maturity_assessment": maturity,
            "country_recommendation": country_recommendation,
            "channel_matches": channels,
            "resource_matches": resources,
            "missing_fields": missing_fields,
            "explanation": "规则引擎已基于本地企业字段与模板库完成结构化判断，结果可在调用 DeepSeek 前直接展示或作为提示词上下文。",
        }

    def assess_maturity(self, payload: dict[str, Any], missing_fields: list[str] | None = None) -> dict[str, Any]:
        """Score enterprise overseas maturity on a 100-point scale."""

        dimensions = {
            "product_internationalization": self._score_product_internationalization(payload),
            "overseas_channel_foundation": self._score_overseas_channel_foundation(payload),
            "english_material_completeness": self._score_english_materials(payload),
            "certification_status": self._score_certifications(payload),
            "supply_chain_stability": self._score_supply_chain(payload),
            "team_internationalization": self._score_team(payload),
            "capital_capacity": self._score_capital(payload),
        }
        total_score = round(sum(item["score"] for item in dimensions.values()), 2)
        level = infer_maturity_level(total_score).value
        missing = missing_fields if missing_fields is not None else self.find_missing_fields(payload)

        suggestions = self._build_improvement_suggestions(dimensions, missing)
        return {
            "total_score": total_score,
            "maturity_level": level,
            "dimension_scores": {
                key: {
                    "score": value["score"],
                    "max_score": MATURITY_SCORE_WEIGHTS[key],
                    "explanation": value["explanation"],
                    "evidence": value["evidence"],
                }
                for key, value in dimensions.items()
            },
            "score_explanation": f"总分 {total_score}/100，对应“{level}”。评分覆盖产品、渠道、英文资料、认证、供应链、团队和资金七个维度。",
            "missing_fields": missing,
            "improvement_suggestions": suggestions,
        }

    def recommend_countries(self, payload: dict[str, Any], maturity_score: float | None = None) -> dict[str, Any]:
        """Rank countries into primary, secondary and long-term markets."""

        industry_name = str(_get(payload, "enterprise.industry", "") or "")
        target_markets = _as_list(_get(payload, "target_markets", []))
        industry_template = self._match_industry(industry_name, payload)
        candidates = self.repository.country_templates
        if target_markets:
            targeted = [country for country in candidates if country.country_name in target_markets or country.region in target_markets]
            candidates = targeted or candidates

        matrix = []
        for country in candidates:
            scores, reasons = self._score_country(country, industry_template, payload, maturity_score or 0)
            market_potential_score = scores["market_potential_score"]
            entry_difficulty_score = scores["entry_difficulty_score"]
            total = round(scores["total_score"], 2)
            matrix.append(
                {
                    "country_name": country.country_name,
                    "region": country.region,
                    "priority_score": total,
                    "market_potential_score": market_potential_score,
                    "entry_difficulty_score": entry_difficulty_score,
                    "matched_industries": [name for name in country.recommended_industries if _same(name, industry_name)],
                    "recommended_entry_modes": self._entry_modes_for_country(country, industry_template),
                    "recommendation_reasons": reasons,
                    "explanation": "；".join(reasons),
                    "template_signals": {
                        "market_potential": country.market_potential,
                        "entry_difficulty": country.entry_difficulty,
                        "policy_environment": country.policy_environment,
                        "logistics_notes": country.logistics_notes,
                    },
                }
            )

        matrix.sort(key=lambda item: item["priority_score"], reverse=True)
        for index, item in enumerate(matrix, start=1):
            item["priority_rank"] = index

        primary = matrix[:2]
        secondary = matrix[2:5]
        long_term = matrix[5:8]
        return {
            "primary_markets": primary,
            "secondary_markets": secondary,
            "long_term_markets": long_term,
            "country_priority_matrix": matrix,
            "recommended_country_names": [item["country_name"] for item in matrix[:5]],
            "explanation": "按行业匹配度、市场潜力、进入难度、渠道/物流适配、认证和目标市场偏好综合排序。",
        }

    def match_channels(self, payload: dict[str, Any], maturity_score: float | None = None) -> list[dict[str, Any]]:
        """Recommend channel paths by industry, product and operating readiness."""

        industry = str(_get(payload, "enterprise.industry", "") or "")
        text = _payload_text(payload)
        has_customers = bool(_as_list(_get(payload, "overseas_customers", [])))
        capacity_score = min(float(_get(payload, "capacity.monthly_units", 0) or 0) / 10000 * 10, 10)
        matches = []
        for rule in CHANNEL_RULES:
            score = float(rule["base_score"])
            reasons: list[str] = []
            if industry in rule["industries"]:
                score += 12
                reasons.append(f"行业“{industry}”适配{rule['channel_type']}")
            matched_keywords = sorted(keyword for keyword in rule["product_keywords"] if keyword in text)
            if matched_keywords:
                score += min(len(matched_keywords) * 4, 12)
                reasons.append(f"产品关键词匹配：{', '.join(matched_keywords)}")
            if has_customers and rule["channel_type"] in {"经销代理", "本地KA渠道", "海外合资/办事处"}:
                score += 6
                reasons.append("已有海外客户，可复用客户案例和背书")
            if capacity_score >= 6 and rule["channel_type"] in {"本地仓", "海外工厂", "本地KA渠道"}:
                score += 5
                reasons.append("产能支撑批量备货或本地化布局")
            if (maturity_score or 0) < 41 and rule["channel_type"] in {"海外合资/办事处", "海外工厂"}:
                score -= 20
                reasons.append("当前成熟度偏低，重资产模式建议后置")
            matches.append(
                {
                    "channel_type": rule["channel_type"],
                    "match_score": round(max(0, min(score, 100)), 2),
                    "recommended_stage": _channel_stage(rule["channel_type"], maturity_score or 0),
                    "explanation": "；".join(reasons) or "基于通用行业路径给出备选渠道。",
                }
            )
        return sorted(matches, key=lambda item: item["match_score"], reverse=True)

    def match_resources(self, payload: dict[str, Any], country_names: Iterable[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        """Match exhibitions, events, associations, channels, logistics and certification resources."""

        industry = str(_get(payload, "enterprise.industry", "") or "")
        countries = list(country_names or _as_list(_get(payload, "target_markets", [])))
        regions = {country.region for name in countries if (country := self.repository.get_country(name))}
        if not regions:
            regions = {str(region) for region in _as_list(_get(payload, "target_regions", [])) if region}

        matched: dict[str, list[dict[str, Any]]] = {}
        for output_type, resource_types in RESOURCE_TYPE_ALIASES.items():
            rows: list[dict[str, Any]] = []
            for resource_type in resource_types:
                candidates = self._resource_candidates(resource_type, industry, regions)
                for resource in candidates:
                    rows.append(self._format_resource_match(output_type, resource, countries, regions, payload))
            matched[output_type] = _dedupe_resources(rows)[:5]
        return matched

    def find_missing_fields(self, payload: dict[str, Any]) -> list[str]:
        """Return user-facing missing-field names without raising errors."""

        missing = []
        for path, label in _REQUIRED_FIELDS.items():
            value = _get(payload, path)
            if value in (None, "", [], {}):
                missing.append(label)
        return missing

    def _score_product_internationalization(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence: list[str] = []
        score = 0.0
        products = _as_list(_get(payload, "products", []))
        if products:
            score += 5
            evidence.append("已提供产品信息")
        if any(_get(item, "hs_code") for item in products if isinstance(item, dict)) or _get(payload, "hs_code"):
            score += 4
            evidence.append("已提供 HS 编码")
        if any(_get(item, "overseas_version") or _get(item, "localized_features") for item in products if isinstance(item, dict)):
            score += 5
            evidence.append("产品已有海外版或本地化适配说明")
        if _as_list(_get(payload, "attachments", [])):
            score += 3
            evidence.append("已上传附件资料")
        if _get(payload, "price_band") or any(_get(item, "price_band") for item in products if isinstance(item, dict)):
            score += 3
            evidence.append("已提供价格带")
        return _dimension(score, "产品信息、HS 编码、本地化适配、附件和价格带越完整，国际化能力越强。", evidence, "product_internationalization")

    def _score_overseas_channel_foundation(self, payload: dict[str, Any]) -> dict[str, Any]:
        evidence = []
        customers = _as_list(_get(payload, "overseas_customers", []))
        channels = _as_list(_get(payload, "overseas_channels", []))
        target_markets = _as_list(_get(payload, "target_markets", []))
        score = 0.0
        if customers:
            score += min(8 + len(customers) * 2, 12)
            evidence.append("已有海外客户")
        if channels:
            score += min(4 + len(channels) * 2, 6)
            evidence.append("已有海外渠道")
        if target_markets:
            score += 2
            evidence.append("已明确目标市场")
        return _dimension(score, "海外客户、渠道和目标市场越明确，渠道基础得分越高。", evidence, "overseas_channel_foundation")

    def _score_english_materials(self, payload: dict[str, Any]) -> dict[str, Any]:
        materials = _as_list(_get(payload, "english_materials", []))
        score = min(len(materials) * 2.5, 10)
        return _dimension(score, "按英文官网、画册、说明书、案例、视频等资料完整度计分。", materials, "english_material_completeness")

    def _score_certifications(self, payload: dict[str, Any]) -> dict[str, Any]:
        certifications = _as_list(_get(payload, "certifications", []))
        industry = self._match_industry(str(_get(payload, "enterprise.industry", "") or ""), payload)
        required = industry.key_certifications if industry else []
        normalized_certs = {_norm(str(item)) for item in certifications}
        matched_required = [cert for cert in required if _norm(cert) in normalized_certs]
        score = min(len(certifications) * 3, 9) + min(len(matched_required) * 3, 6)
        evidence = [f"已有认证：{', '.join(map(str, certifications))}"] if certifications else []
        if matched_required:
            evidence.append(f"命中行业关键认证：{', '.join(matched_required)}")
        return _dimension(score, "同时考虑已取得认证数量及是否命中行业模板关键认证。", evidence, "certification_status")

    def _score_supply_chain(self, payload: dict[str, Any]) -> dict[str, Any]:
        score = 0.0
        evidence = []
        capacity = float(_get(payload, "capacity.monthly_units", 0) or 0)
        if capacity > 0:
            score += min(capacity / 5000 * 5, 5)
            evidence.append(f"月产能：{int(capacity)}")
        if _get(payload, "moq"):
            score += 3
            evidence.append("已提供 MOQ")
        if _get(payload, "capacity.lead_time_days"):
            score += 3
            evidence.append("已提供交期")
        if _as_list(_get(payload, "suppliers", [])) or _get(payload, "quality_system"):
            score += 2
            evidence.append("已提供供应商或质量体系信息")
        if _get(payload, "after_sales") or _get(payload, "warranty"):
            score += 2
            evidence.append("已提供售后/质保信息")
        return _dimension(score, "产能、MOQ、交期、供应商/质量体系和售后信息共同反映供应链稳定性。", evidence, "supply_chain_stability")

    def _score_team(self, payload: dict[str, Any]) -> dict[str, Any]:
        score = 0.0
        evidence = []
        members = int(_get(payload, "team.international_members", 0) or 0)
        languages = _as_list(_get(payload, "team.languages", []))
        export_years = float(_get(payload, "team.export_years", 0) or 0)
        if members:
            score += min(members * 2, 4)
            evidence.append(f"国际化/外贸团队人数：{members}")
        if languages:
            score += min(len(languages) * 1.5, 3)
            evidence.append(f"语言能力：{', '.join(map(str, languages))}")
        if export_years:
            score += min(export_years, 3)
            evidence.append(f"外贸经验：{export_years:g} 年")
        return _dimension(score, "国际化团队人数、语言能力和外贸经验决定团队能力得分。", evidence, "team_internationalization")

    def _score_capital(self, payload: dict[str, Any]) -> dict[str, Any]:
        budget = float(_get(payload, "finance.export_budget", 0) or 0)
        credit = float(_get(payload, "finance.credit_line", 0) or 0)
        score = min(budget / 500000 * 7, 7) + min(credit / 1000000 * 3, 3)
        evidence = []
        if budget:
            evidence.append(f"出海预算：{budget:g}")
        if credit:
            evidence.append(f"授信额度：{credit:g}")
        return _dimension(score, "按可投入出海预算和授信/融资能力计分。", evidence, "capital_capacity")

    def _score_country(self, country: CountryTemplate, industry: IndustryTemplate | None, payload: dict[str, Any], maturity_score: float) -> tuple[dict[str, float], list[str]]:
        industry_name = str(_get(payload, "enterprise.industry", "") or "")
        potential = _potential_score(country.market_potential)
        difficulty = _difficulty_score(country.entry_difficulty)
        industry_fit = 90 if any(_same(item, industry_name) for item in country.recommended_industries) else 58
        if industry and country.region in industry.suitable_regions:
            industry_fit += 6
        target_bonus = 8 if country.country_name in _as_list(_get(payload, "target_markets", [])) or country.region in _as_list(_get(payload, "target_markets", [])) else 0
        certification_fit = 70 + min(len(_as_list(_get(payload, "certifications", []))) * 5, 20)
        capacity_fit = 62 + min(float(_get(payload, "capacity.monthly_units", 0) or 0) / 10000 * 20, 18)
        maturity_fit = 55 + min(maturity_score * 0.35, 35)
        total = potential * 0.28 + difficulty * 0.18 + industry_fit * 0.24 + certification_fit * 0.12 + capacity_fit * 0.10 + maturity_fit * 0.08 + target_bonus
        reasons = [
            f"市场潜力为“{country.market_potential}”",
            f"进入难度为“{country.entry_difficulty}”",
        ]
        if industry_fit >= 90:
            reasons.append(f"国家模板推荐行业包含“{industry_name}”")
        if target_bonus:
            reasons.append("企业已将该国家/区域列为目标市场")
        reasons.append(country.market_opportunity)
        return {
            "market_potential_score": round(potential, 2),
            "entry_difficulty_score": round(difficulty, 2),
            "industry_fit_score": round(min(industry_fit, 100), 2),
            "certification_fit_score": round(certification_fit, 2),
            "capacity_fit_score": round(capacity_fit, 2),
            "maturity_fit_score": round(maturity_fit, 2),
            "total_score": min(total, 100),
        }, reasons

    def _entry_modes_for_country(self, country: CountryTemplate, industry: IndustryTemplate | None) -> list[str]:
        modes = list(industry.common_entry_modes[:3]) if industry else []
        modes.extend(country.local_partner_types[:2])
        return _dedupe_strings(modes)[:5]

    def _match_industry(self, industry_name: str, payload: dict[str, Any]) -> IndustryTemplate | None:
        exact = self.repository.get_industry(industry_name) if industry_name else None
        if exact:
            return exact
        text = _payload_text(payload)
        scored = []
        for industry in self.repository.industry_templates:
            score = sum(1 for product in industry.typical_products if product in text)
            if score:
                scored.append((score, industry))
        return max(scored, key=lambda item: item[0])[1] if scored else None

    def _resource_candidates(self, resource_type: str, industry: str, regions: set[str]) -> list[ResourceTemplate]:
        candidates: list[ResourceTemplate] = []
        search_regions = regions or {None}
        for region in search_regions:
            candidates.extend(self.repository.match_resources(resource_type=resource_type, industry_name=industry or None, region=region))
        if not candidates:
            candidates = self.repository.match_resources(resource_type=resource_type, industry_name=industry or None)
        if not candidates:
            candidates = self.repository.match_resources(resource_type=resource_type)
        return candidates

    def _format_resource_match(self, output_type: str, resource: ResourceTemplate, countries: list[str], regions: set[str], payload: dict[str, Any]) -> dict[str, Any]:
        industry = str(_get(payload, "enterprise.industry", "") or "")
        score = 70
        if industry and any(_same(industry, item) for item in resource.applicable_industries):
            score += 12
        if regions and any(region in resource.applicable_regions for region in regions):
            score += 10
        return {
            "resource_match_type": output_type,
            "resource_type": resource.resource_type,
            "resource_category": resource.resource_category,
            "resource_subtype": resource.resource_subtype,
            "match_score": min(score, 100),
            "applicable_countries": countries[:5],
            "matching_tags": resource.matching_tags,
            "selection_criteria": resource.selection_criteria,
            "recommended_use": resource.recommended_use,
            "explanation": f"{resource.description} 适用于{industry or '相关行业'}在{', '.join(sorted(regions)) if regions else '目标区域'}的资源对接。",
        }

    def _build_improvement_suggestions(self, dimensions: dict[str, dict[str, Any]], missing_fields: list[str]) -> list[str]:
        suggestions = []
        for key, item in dimensions.items():
            max_score = MATURITY_SCORE_WEIGHTS[key]
            if item["score"] < max_score * 0.6:
                suggestions.append(_suggestion_for_dimension(key))
        if missing_fields:
            suggestions.append("补充缺失字段：" + "、".join(missing_fields) + "，可提升规则判断准确度。")
        return _dedupe_strings(suggestions)


def _dimension(score: float, explanation: str, evidence: list[Any], dimension_key: str) -> dict[str, Any]:
    return {
        "score": round(min(score, MATURITY_SCORE_WEIGHTS[dimension_key]), 2),
        "explanation": explanation,
        "evidence": [str(item) for item in evidence if item],
    }


def _get(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, default)
        else:
            return default
    return current


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _payload_text(payload: dict[str, Any]) -> str:
    return str(payload)


def _norm(value: str) -> str:
    return value.strip().casefold().replace(" ", "")


def _same(left: str, right: str) -> bool:
    return _norm(left) == _norm(right)


def _potential_score(label: str) -> float:
    return {"高": 92, "中高": 80, "中": 66, "低": 45}.get(label, 62)


def _difficulty_score(label: str) -> float:
    # This is an ease score: higher is easier to enter.
    return {"低": 88, "中": 72, "中高": 58, "高": 42}.get(label, 62)


def _channel_stage(channel_type: str, maturity_score: float) -> str:
    if channel_type in {"海外工厂", "海外合资/办事处"}:
        return "长期布局" if maturity_score < 76 else "优先推进"
    if channel_type in {"本地仓", "本地KA渠道"}:
        return "渠道试点" if maturity_score < 76 else "优先推进"
    return "优先推进" if maturity_score >= 41 else "渠道试点"


def _suggestion_for_dimension(dimension_key: str) -> str:
    return {
        "product_internationalization": "补充 HS 编码、海外版参数、目标市场适配点和产品附件资料。",
        "overseas_channel_foundation": "沉淀海外客户案例，建立经销/代理/平台线索池并明确首批目标市场。",
        "english_material_completeness": "完善英文官网、产品手册、说明书、案例和视频素材。",
        "certification_status": "按行业模板核对 CE/FDA/ISO/Halal 等准入认证并规划检测周期。",
        "supply_chain_stability": "补充产能、MOQ、交期、质量体系、售后和备件保障信息。",
        "team_internationalization": "配置外贸、语言、法务财税和本地化运营负责人。",
        "capital_capacity": "明确认证、参展、备货、广告和渠道建设预算，并准备授信或融资方案。",
    }[dimension_key]


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = _norm(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _dedupe_resources(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for item in values:
        key = (item["resource_match_type"], item["resource_type"], item["resource_subtype"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return sorted(result, key=lambda row: row["match_score"], reverse=True)
