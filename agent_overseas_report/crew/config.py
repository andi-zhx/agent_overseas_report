"""Configuration helpers for the enterprise CrewAI orchestration path."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_overseas_report.config import AppSettings

NO_FABRICATION_CONSTRAINT = "不得编造数据；若 ContextBundle 未提供事实、数值、年份、来源或假设，必须标记为信息缺口/需人工复核。"
CITATION_CONSTRAINT = "所有事实、数据、政策、市场判断和资源建议必须附 citations，引用 ContextBundle 中的 source_id、url、文件名或资料标识。"
CONTEXT_ONLY_CONSTRAINT = "不得自行访问数据库或绕过服务层取数；唯一事实输入为统一传入的 ContextBundle 及上游步骤输出。"


@dataclass(frozen=True, slots=True)
class CrewAgentConfig:
    """Static configuration for one CrewAI agent role."""

    role: str
    goal: str
    backstory: str
    input_spec: str
    output_spec: str
    constraints: tuple[str, ...] = (NO_FABRICATION_CONSTRAINT, CITATION_CONSTRAINT, CONTEXT_ONLY_CONSTRAINT)
    allow_delegation: bool = False

    def instruction_block(self) -> str:
        """Return a compact block that makes input/output constraints explicit."""

        constraints = "\n".join(f"- {constraint}" for constraint in self.constraints)
        return f"输入：{self.input_spec}\n输出：{self.output_spec}\n约束：\n{constraints}"


@dataclass(frozen=True, slots=True)
class CrewAISettings:
    """Runtime settings for the enterprise CrewAI report workflow."""

    enabled: bool = False
    process: str = "sequential"
    verbose: bool = False
    agent_configs: dict[str, CrewAgentConfig] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "CrewAISettings":
        """Build settings from environment variables.

        CrewAI is intentionally opt-in so the legacy ``OverseasPlanGenerationService``
        path remains the default production behavior.
        """

        settings = AppSettings.from_env()
        return cls(enabled=settings.enable_crewai, verbose=settings.crewai_verbose, agent_configs=default_agent_configs())


def is_crewai_enabled() -> bool:
    """Return whether the CrewAI orchestration path should be used."""

    return CrewAISettings.from_env().enabled


def default_agent_configs() -> dict[str, CrewAgentConfig]:
    """Return the complete enterprise overseas-report multi-agent configuration."""

    common = (NO_FABRICATION_CONSTRAINT, CITATION_CONSTRAINT, CONTEXT_ONLY_CONSTRAINT)
    return {
        "company_diagnosis": CrewAgentConfig(
            role="CompanyDiagnosisAgent",
            goal="诊断企业、产品、团队、产能、认证和出海准备度，明确优势、短板与信息缺口。",
            backstory="企业出海诊断顾问，擅长把企业主数据、产品资料、规则引擎评分和 ContextBundle 证据转化为可审计的诊断结论。",
            input_spec="ContextBundle.enterprise_data、ContextBundle.rule_engine_outputs、ContextBundle.missing_field_analysis、用户参数和上游空输入。",
            output_spec="可保存的企业与产品诊断结果，包含 readiness_score、strengths、gaps、assumptions、citations、manual_review_items。",
            constraints=common,
        ),
        "market_research": CrewAgentConfig(
            role="MarketResearchAgent",
            goal="研究目标国家/地区的市场需求、竞争、准入、价格、客户和证据边界。",
            backstory="国际市场研究员，专注基于本地 RAG、WebResearch 和模板资料做有来源的国家市场对比，不把猜测包装成事实。",
            input_spec="ContextBundle.local_chunks、ContextBundle.web_research_sources、ContextBundle.templates、用户目标国家，以及企业诊断输出。",
            output_spec="可保存的市场与国家研究结果，按国家列出 opportunity、barriers、evidence、data_gaps、citations。",
            constraints=common,
        ),
        "channel_strategy": CrewAgentConfig(
            role="ChannelStrategyAgent",
            goal="设计渠道进入策略、客户路径、展会营销动作和 12-24 个月渠道里程碑。",
            backstory="海外渠道策略顾问，擅长把市场研究和企业能力转化为可执行的经销、直销、平台和展会组合。",
            input_spec="ContextBundle、企业诊断输出、市场研究输出、规则引擎渠道建议。",
            output_spec="可保存的渠道策略，包含 target_segments、entry_mode、channel_mix、marketing_actions、timeline、citations。",
            constraints=common,
        ),
        "resource_matching": CrewAgentConfig(
            role="ResourceMatchingAgent",
            goal="匹配展会、服务商、平台招商、认证、物流、产业园和政府/金融资源。",
            backstory="资源生态匹配专家，熟悉资源库模板和企业需求映射，强调资源适配理由、使用前提和证据来源。",
            input_spec="ContextBundle.templates.resource_templates、local_chunks、web_research_sources、渠道策略输出和企业诊断输出。",
            output_spec="可保存的资源匹配清单，包含 resource_name、resource_type、fit_reason、next_action、assumptions、citations。",
            constraints=common,
        ),
        "financial_planning": CrewAgentConfig(
            role="FinancialPlanningAgent",
            goal="分析投融资、预算、现金流、扩产与阶段性投入产出假设。",
            backstory="跨境投融资与产能规划顾问，擅长把预算、产能、价格带、渠道计划转换为带假设的财务规划。",
            input_spec="ContextBundle.enterprise_data.finance/capacity、产品价格带、渠道策略、资源匹配和规则引擎输出。",
            output_spec="可保存的投融资与扩产分析，包含 budget_plan、capacity_plan、funding_options、assumptions、sensitivities、citations。",
            constraints=common,
        ),
        "risk_compliance": CrewAgentConfig(
            role="RiskComplianceAgent",
            goal="检查目标市场合规、认证、贸易、税务、数据、合同和运营风险。",
            backstory="合规风控顾问，专注识别缺证据的政策/认证/关税结论，输出风险等级、触发条件和复核建议。",
            input_spec="ContextBundle.web_research_sources、local_chunks、产品 HS/认证、市场研究、渠道资源和财务规划输出。",
            output_spec="可保存的合规与风险检查，包含 risk_register、compliance_requirements、mitigations、manual_review_items、citations。",
            constraints=common,
        ),
        "report_writer": CrewAgentConfig(
            role="ReportWriterAgent",
            goal="把所有步骤产出整合为兼容现有 schema 的企业出海报告 JSON。",
            backstory="投资级报告撰写专家，负责结构化表达、字段完整性、旧版 sections 兼容和引用保留。",
            input_spec="原始报告 prompt、JSON schema 示例、ContextBundle 以及全部上游步骤输出。",
            output_spec="可保存的最终报告 JSON 文本，包含 investment_analysis_report、legacy sections、citations、assumptions 和 manual_review_items。",
            constraints=common,
        ),
        "quality_review": CrewAgentConfig(
            role="QualityReviewAgent",
            goal="复核最终报告是否有来源、结论是否具体、预算是否有假设，并决定 approved 或 revision_required。",
            backstory="质量审核负责人，负责阻断无来源、空泛结论和无假设预算，给出可执行修订意见。",
            input_spec="ContextBundle、全部上游步骤输出、最终报告 JSON 文本和质量门槛。",
            output_spec="可保存的质量复核 JSON，必须包含 status=approved|revision_required、issues、required_revisions、citations_check、budget_assumption_check。",
            constraints=common + ("若发现缺少来源、结论空泛或预算无假设，必须返回 status=revision_required。",),
        ),
    }


def config_file_path() -> Path:
    """Return the packaged CrewAI config file path for documentation/tooling."""

    return Path(__file__).with_name("crew_config.json")


def load_packaged_config() -> dict[str, Any]:
    """Load the lightweight packaged CrewAI config without extra YAML dependencies."""

    import json

    return json.loads(config_file_path().read_text(encoding="utf-8"))
