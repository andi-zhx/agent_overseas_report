import { useMemo, useState } from "react";

import "./overseas-plan-workbench/OverseasPlanWorkbench.css";

export type Option = {
  id: string;
  name: string;
};

export type ProductOption = Option & {
  enterpriseId: string;
  category?: string;
  hsCode?: string;
  certifications?: string[];
  capacity?: string;
  moq?: string;
  leadTime?: string;
  priceBand?: string;
  exportSuitable?: boolean;
  attachments?: string[];
};

export type EnterpriseProfile = Option & {
  industry?: string;
  mainBusiness?: string;
  mainProducts: string[];
  annualRevenue?: string;
  currentMarkets: string[];
  exportRatio?: string;
  certifications?: string[];
  capacity?: string;
  moq?: string;
  hasOverseasCustomers?: boolean;
  teamInternationalization?: string;
  capitalCapacity?: string;
  targetChannels?: string[];
  targetCustomerTypes?: string[];
  planExhibition?: boolean;
  needFinancing?: boolean;
  overseasWarehouseOrFactory?: boolean;
  maturityScore?: number;
  maturityLevel?: string;
  missingFields?: string[];
};

export type PlanSectionKey =
  | "enterpriseDiagnosis"
  | "marketSelection"
  | "entryModeDesign"
  | "resourceMatching"
  | "exhibitionMarketing"
  | "financingCapacity"
  | "roadmap";

export type EditableSections = Record<PlanSectionKey, string>;

export type CountryMatrixItem = {
  country: string;
  marketPotential: number;
  entryDifficulty: number;
  priority: string;
  recommendation: string;
};

export type RoadmapItem = {
  period: "1-3个月" | "3-6个月" | "6-9个月" | "9-12个月" | "12-24个月";
  title: string;
  actions: string[];
  owner?: string;
};

export type GenerationSource = "AI生成" | "用户编辑" | "重新生成";

export type PlanVersionRecord = {
  version_number: number;
  created_by?: string;
  created_at: string;
  generation_source: GenerationSource;
  change_summary?: string;
  content_json: { sections: EditableSections; countryMatrix?: CountryMatrixItem[]; roadmap?: RoadmapItem[] };
  is_final?: boolean;
};

export type ReadinessStatus = "可生成" | "可生成但质量较低" | "不建议生成";

export type MissingFieldCategory = {
  category: "企业层面" | "产品层面" | "出海目标层面";
  fields: string[];
};

export type GenerationReadiness = {
  status: ReadinessStatus;
  statusCode: "ready" | "low_quality" | "not_recommended";
  message: string;
  missingCategories: MissingFieldCategory[];
  missingCount: number;
  criticalMissingFields: string[];
  shouldPopup: boolean;
  manualReviewRequired: boolean;
};

export type ReportDepth = "basic" | "standard" | "investment_analyst";

export type AuditLogRecord = {
  id: string;
  action_type: string;
  user_id?: string;
  username?: string;
  created_at: string;
  result_status: string;
  export_type?: string;
  export_audience?: string;
  edited_by?: string;
  finalized_by?: string;
  used_enterprise_data?: Array<Record<string, unknown>>;
  used_product_data?: Array<Record<string, unknown>>;
  used_local_knowledge_files?: Array<Record<string, unknown>>;
  web_research_enabled?: boolean;
  external_sources?: Array<Record<string, unknown>>;
};

export type DataSourceItem = {
  id: string;
  name: string;
  type: "企业库" | "产品库" | "本地知识库" | "网络研究" | "人工编辑";
  url?: string;
  updatedAt?: string;
};

export type QualityScore = {
  overall: number;
  completeness: number;
  evidence: number;
  feasibility: number;
  riskCoverage: number;
  comment?: string;
};

export type GeneratedPlan = {
  projectId?: string;
  sections: EditableSections;
  countryMatrix: CountryMatrixItem[];
  roadmap: RoadmapItem[];
  dataQualityReview?: GenerationReadiness;
  dataSources?: DataSourceItem[];
  qualityScore?: QualityScore;
  currentVersionNumber?: number;
  versions?: PlanVersionRecord[];
  auditLogs?: AuditLogRecord[];
};

export type GeneratePlanPayload = {
  enterpriseId: string;
  productIds: string[];
  selectedIndustry: string;
  targetCountries: string[];
  reportDepth: ReportDepth;
  useLocalKnowledgeBase: boolean;
  useWebResearch: boolean;
  continueOnValidationWarning?: boolean;
  generationReadiness?: GenerationReadiness;
};

export type ExportType = "word" | "ppt" | "excel" | "resources";

export type OverseasPlanWorkbenchProps = {
  enterprises?: EnterpriseProfile[];
  products?: ProductOption[];
  industries?: Option[];
  countries?: Option[];
  currentUserId?: string;
  apiBaseUrl?: string;
  onGenerate?: (payload: GeneratePlanPayload) => Promise<GeneratedPlan>;
  onSaveDraft?: (draft: GeneratePlanPayload & { sections: EditableSections }) => Promise<void>;
  onExport?: (type: ExportType, plan: GeneratedPlan) => Promise<void>;
  onRestoreVersion?: (version: PlanVersionRecord, plan: GeneratedPlan) => Promise<GeneratedPlan | void>;
  onMarkFinalVersion?: (version: PlanVersionRecord, plan: GeneratedPlan) => Promise<PlanVersionRecord | void>;
  onOpenAuditLog?: (projectId?: string) => void;
};

const sectionTabs: Array<{ key: PlanSectionKey; label: string }> = [
  { key: "enterpriseDiagnosis", label: "企业现状诊断" },
  { key: "marketSelection", label: "海外市场选择" },
  { key: "entryModeDesign", label: "出海模式设计" },
  { key: "resourceMatching", label: "海外资源对接" },
  { key: "exhibitionMarketing", label: "展会与推广计划" },
  { key: "financingCapacity", label: "投融资与扩产规划" },
  { key: "roadmap", label: "12-24个月路线图" },
];

const defaultEnterprises: EnterpriseProfile[] = [
  {
    id: "ent-1",
    name: "示例医疗科技有限公司",
    mainProducts: ["便携式检测仪", "智能监测终端"],
    currentMarkets: ["华东", "东南亚试单"],
    industry: "医疗器械",
    mainBusiness: "便携式检测和智能监测终端研发制造",
    annualRevenue: "1.2亿元",
    exportRatio: "18%",
    certifications: ["CE", "ISO 13485"],
    capacity: "10,000台/月",
    moq: "50台",
    hasOverseasCustomers: true,
    teamInternationalization: "3名外贸/多语种成员",
    capitalCapacity: "年度出海预算80万元",
    targetChannels: ["经销商", "行业展会"],
    targetCustomerTypes: ["区域代理商", "医疗机构"],
    planExhibition: true,
    needFinancing: false,
    overseasWarehouseOrFactory: true,
    maturityScore: 76,
    maturityLevel: "全球化布局型",
    missingFields: ["目标国售后服务商", "英文案例视频"],
  },
  {
    id: "ent-2",
    name: "样例新能源装备有限公司",
    mainProducts: ["储能逆变器", "户用储能柜"],
    currentMarkets: ["国内", "中东询盘"],
    industry: "新能源装备",
    mainBusiness: "储能逆变器和户用储能柜研发生产",
    exportRatio: "8%",
    certifications: ["IEC"],
    capacity: "2,000套/月",
    moq: "20套",
    maturityScore: 58,
    maturityLevel: "增长型",
    missingFields: ["UL认证", "海外渠道价格体系"],
  },
];

const defaultProducts: ProductOption[] = [
  { id: "prod-1", enterpriseId: "ent-1", name: "便携式检测仪", category: "医疗检测设备", hsCode: "902780", certifications: ["CE", "ISO 13485"], capacity: "10,000台/月", moq: "50台", leadTime: "30天", priceBand: "USD 200-500", exportSuitable: true, attachments: ["英文说明书", "产品图片"] },
  { id: "prod-2", enterpriseId: "ent-1", name: "智能监测终端", category: "智能硬件", hsCode: "901819", certifications: ["CE"], capacity: "6,000台/月", moq: "100台", leadTime: "35天", priceBand: "USD 100-300", exportSuitable: true, attachments: ["产品图片"] },
  { id: "prod-3", enterpriseId: "ent-2", name: "储能逆变器", certifications: ["IEC"], capacity: "2,000套/月", moq: "20套" },
];

const defaultIndustries: Option[] = [
  { id: "medical-device", name: "医疗器械" },
  { id: "new-energy", name: "新能源装备" },
  { id: "industrial-equipment", name: "工业设备" },
  { id: "consumer-electronics", name: "消费电子" },
];

const reportDepthOptions: Array<{ id: ReportDepth; name: string; description: string }> = [
  { id: "basic", name: "基础版", description: "快速生成关键建议与行动清单" },
  { id: "standard", name: "标准版", description: "补充市场、渠道、资源与路线图" },
  { id: "investment_analyst", name: "投资分析师版", description: "强化财务、风险、竞争与投资判断" },
];

const defaultCountries: Option[] = [
  { id: "DE", name: "德国" },
  { id: "US", name: "美国" },
  { id: "AE", name: "阿联酋" },
  { id: "ID", name: "印度尼西亚" },
  { id: "BR", name: "巴西" },
];

const emptySections: EditableSections = {
  enterpriseDiagnosis: "等待生成企业现状诊断。",
  marketSelection: "等待生成海外市场选择建议。",
  entryModeDesign: "等待生成出海模式设计。",
  resourceMatching: "等待生成海外资源对接建议。",
  exhibitionMarketing: "等待生成展会与推广计划。",
  financingCapacity: "等待生成投融资与扩产规划。",
  roadmap: "等待生成12-24个月路线图。",
};

const createLocalVersion = (
  plan: GeneratedPlan,
  createdBy: string,
  generationSource: GenerationSource,
  changeSummary: string,
): PlanVersionRecord => {
  const latestVersionNumber = Math.max(0, ...(plan.versions ?? []).map((version) => version.version_number));

  return {
    version_number: latestVersionNumber + 1,
    created_by: createdBy,
    created_at: new Date().toISOString(),
    generation_source: generationSource,
    change_summary: changeSummary,
    content_json: { sections: plan.sections, countryMatrix: plan.countryMatrix, roadmap: plan.roadmap },
  };
};


const ENTERPRISE_REQUIRED_FIELDS: Array<{ label: string; isMissing: (enterprise: EnterpriseProfile | undefined, selectedIndustry: string) => boolean; critical?: boolean }> = [
  { label: "企业名称", critical: true, isMissing: (enterprise) => !enterprise?.name?.trim() },
  { label: "所属行业", critical: true, isMissing: (enterprise, selectedIndustry) => !selectedIndustry && !enterprise?.industry?.trim() },
  { label: "主营业务", isMissing: (enterprise) => !enterprise?.mainBusiness?.trim() && (enterprise?.mainProducts.length ?? 0) === 0 },
  { label: "年营收", isMissing: (enterprise) => !enterprise?.annualRevenue?.trim() },
  { label: "当前市场", isMissing: (enterprise) => (enterprise?.currentMarkets.length ?? 0) === 0 },
  { label: "出口占比", isMissing: (enterprise) => !enterprise?.exportRatio?.trim() },
  { label: "工厂产能", isMissing: (enterprise) => !enterprise?.capacity?.trim() },
  { label: "是否已有海外客户", isMissing: (enterprise) => enterprise?.hasOverseasCustomers === undefined },
  { label: "团队国际化能力", isMissing: (enterprise) => !enterprise?.teamInternationalization?.trim() },
  { label: "资金能力", isMissing: (enterprise) => !enterprise?.capitalCapacity?.trim() },
];

const PRODUCT_REQUIRED_FIELDS: Array<{ label: string; isMissing: (product: ProductOption) => boolean; critical?: boolean }> = [
  { label: "产品名称", critical: true, isMissing: (product) => !product.name?.trim() },
  { label: "产品类别", isMissing: (product) => !product.category?.trim() },
  { label: "HS编码", isMissing: (product) => !product.hsCode?.trim() },
  { label: "认证情况", isMissing: (product) => (product.certifications?.length ?? 0) === 0 },
  { label: "MOQ", isMissing: (product) => !product.moq?.trim() },
  { label: "交期", isMissing: (product) => !product.leadTime?.trim() },
  { label: "价格带", isMissing: (product) => !product.priceBand?.trim() },
  { label: "产能", isMissing: (product) => !product.capacity?.trim() },
  { label: "是否适合出口", isMissing: (product) => product.exportSuitable === undefined },
  { label: "产品图片/资料附件", isMissing: (product) => (product.attachments?.length ?? 0) === 0 },
];

const TARGET_REQUIRED_FIELDS: Array<{ label: string; isMissing: (enterprise: EnterpriseProfile | undefined, targetCountries: string[]) => boolean; critical?: boolean }> = [
  { label: "目标国家", critical: true, isMissing: (_enterprise, targetCountries) => targetCountries.length === 0 },
  { label: "目标渠道", isMissing: (enterprise) => (enterprise?.targetChannels?.length ?? 0) === 0 },
  { label: "目标客户类型", isMissing: (enterprise) => (enterprise?.targetCustomerTypes?.length ?? 0) === 0 },
  { label: "是否计划参展", isMissing: (enterprise) => enterprise?.planExhibition === undefined },
  { label: "是否需要融资", isMissing: (enterprise) => enterprise?.needFinancing === undefined },
  { label: "是否考虑海外仓/海外工厂", isMissing: (enterprise) => enterprise?.overseasWarehouseOrFactory === undefined },
];

const assessFrontendReadiness = (
  enterprise: EnterpriseProfile | undefined,
  selectedProducts: ProductOption[],
  selectedIndustry: string,
  targetCountries: string[],
): GenerationReadiness => {
  const enterpriseMissing = ENTERPRISE_REQUIRED_FIELDS.filter((field) => field.isMissing(enterprise, selectedIndustry)).map((field) => field.label);
  const productMissing = selectedProducts.length === 0
    ? PRODUCT_REQUIRED_FIELDS.map((field) => field.label)
    : PRODUCT_REQUIRED_FIELDS.filter((field) => selectedProducts.some((product) => field.isMissing(product))).map((field) => field.label);
  const targetMissing = TARGET_REQUIRED_FIELDS.filter((field) => field.isMissing(enterprise, targetCountries)).map((field) => field.label);
  const missingCategories = [
    { category: "企业层面" as const, fields: enterpriseMissing },
    { category: "产品层面" as const, fields: productMissing },
    { category: "出海目标层面" as const, fields: targetMissing },
  ].filter((category) => category.fields.length > 0);
  const missingCount = missingCategories.reduce((total, category) => total + category.fields.length, 0);
  const criticalMissingFields = [
    ...ENTERPRISE_REQUIRED_FIELDS.filter((field) => field.critical && field.isMissing(enterprise, selectedIndustry)).map((field) => field.label),
    ...PRODUCT_REQUIRED_FIELDS.filter((field) => field.critical && (selectedProducts.length === 0 || selectedProducts.some((product) => field.isMissing(product)))).map((field) => field.label),
    ...TARGET_REQUIRED_FIELDS.filter((field) => field.critical && field.isMissing(enterprise, targetCountries)).map((field) => field.label),
  ];

  const status: ReadinessStatus = criticalMissingFields.length > 0
    ? "不建议生成"
    : missingCount >= 10
      ? "可生成但质量较低"
      : "可生成";

  return {
    status,
    statusCode: status === "可生成" ? "ready" : status === "可生成但质量较低" ? "low_quality" : "not_recommended",
    message: status === "不建议生成"
      ? "基础字段缺失较严重，不建议直接生成；如继续生成，方案将标记需人工补充/复核。"
      : status === "可生成但质量较低"
        ? "可以生成，但关键字段缺失会降低方案质量。"
        : "信息基本完整，可生成方案。",
    missingCategories,
    missingCount,
    criticalMissingFields,
    shouldPopup: status === "不建议生成",
    manualReviewRequired: missingCount > 0,
  };
};

const ensureVersionHistory = (plan: GeneratedPlan, createdBy: string, generationSource: GenerationSource): GeneratedPlan => {
  if (plan.versions?.length) {
    return {
      ...plan,
      currentVersionNumber: plan.currentVersionNumber ?? plan.versions[plan.versions.length - 1]?.version_number,
    };
  }

  const version = createLocalVersion(plan, createdBy, generationSource, generationSource === "重新生成" ? "AI重新生成方案" : "AI生成方案");
  return { ...plan, currentVersionNumber: version.version_number, versions: [version] };
};

export default function OverseasPlanWorkbench({
  enterprises = defaultEnterprises,
  products = defaultProducts,
  industries = defaultIndustries,
  countries = defaultCountries,
  currentUserId = "current-user",
  apiBaseUrl = "",
  onGenerate,
  onSaveDraft,
  onExport,
  onRestoreVersion,
  onMarkFinalVersion,
  onOpenAuditLog,
}: OverseasPlanWorkbenchProps) {
  const [enterpriseId, setEnterpriseId] = useState(enterprises[0]?.id ?? "");
  const [productIds, setProductIds] = useState<string[]>([]);
  const [industryId, setIndustryId] = useState(industries[0]?.id ?? "");
  const [targetCountryIds, setTargetCountryIds] = useState<string[]>([]);
  const [reportDepth, setReportDepth] = useState<ReportDepth>("standard");
  const [useLocalKnowledgeBase, setUseLocalKnowledgeBase] = useState(true);
  const [useWebResearch, setUseWebResearch] = useState(false);
  const [allowMissingFields, setAllowMissingFields] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [activeTab, setActiveTab] = useState<PlanSectionKey>("enterpriseDiagnosis");
  const [plan, setPlan] = useState<GeneratedPlan>({ sections: emptySections, countryMatrix: [], roadmap: [] });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [showAuditPanel, setShowAuditPanel] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);
  const [pendingSevereReadiness, setPendingSevereReadiness] = useState<GenerationReadiness | null>(null);

  const selectedEnterprise = enterprises.find((enterprise) => enterprise.id === enterpriseId);
  const availableProducts = useMemo(
    () => products.filter((product) => product.enterpriseId === enterpriseId),
    [enterpriseId, products],
  );
  const selectedIndustry = industries.find((industry) => industry.id === industryId)?.name ?? "";
  const selectedCountryNames = countries
    .filter((country) => targetCountryIds.includes(country.id))
    .map((country) => country.name);
  const selectedProducts = availableProducts.filter((product) => productIds.includes(product.id));
  const readiness = assessFrontendReadiness(selectedEnterprise, selectedProducts, selectedIndustry, selectedCountryNames);

  const payload: GeneratePlanPayload = {
    enterpriseId,
    productIds,
    selectedIndustry,
    targetCountries: selectedCountryNames,
    reportDepth,
    useLocalKnowledgeBase,
    useWebResearch,
    continueOnValidationWarning: allowMissingFields,
    generationReadiness: readiness,
  };

  const toggleProduct = (productId: string) => {
    setProductIds((current) =>
      current.includes(productId) ? current.filter((id) => id !== productId) : [...current, productId],
    );
  };

  const toggleCountry = (countryId: string) => {
    setTargetCountryIds((current) =>
      current.includes(countryId) ? current.filter((id) => id !== countryId) : [...current, countryId],
    );
  };

  const requestGeneration = async (generationPayload: GeneratePlanPayload) => {
    if (onGenerate) {
      return onGenerate(generationPayload);
    }

    const response = await fetch(`${apiBaseUrl}/api/overseas-plans/generations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enterprise_id: generationPayload.enterpriseId,
        product_ids: generationPayload.productIds,
        selected_industry: generationPayload.selectedIndustry,
        target_countries: generationPayload.targetCountries,
        report_depth: generationPayload.reportDepth,
        use_local_knowledge_base: generationPayload.useLocalKnowledgeBase,
        use_web_research: generationPayload.useWebResearch,
        continue_on_validation_warning: generationPayload.continueOnValidationWarning,
      }),
    });

    if (!response.ok) {
      throw new Error(`方案生成接口异常：${response.status}`);
    }

    return response.json() as Promise<GeneratedPlan>;
  };

  const runGenerate = async (continueOnValidationWarning = false) => {
    setLoading(true);
    setGenerationProgress(12);
    try {
      const generationPayload = { ...payload, continueOnValidationWarning };
      setGenerationProgress(35);
      const nextPlan = await requestGeneration(generationPayload);
      setGenerationProgress(82);
      const nextPlanWithHistory = ensureVersionHistory(nextPlan, currentUserId, "AI生成");
      setPlan(nextPlanWithHistory);
      setPreviewVersionNumber(nextPlanWithHistory.currentVersionNumber ?? nextPlanWithHistory.versions?.[nextPlanWithHistory.versions.length - 1]?.version_number ?? null);
      setGenerationProgress(100);
      setNotice(continueOnValidationWarning || readiness.manualReviewRequired ? "方案已生成，并已标记需人工补充/复核。" : "方案已生成，可在预览区编辑后导出，也可进入版本记录查看历史。");
    } catch (generateError) {
      setGenerationProgress(0);
      setError(generateError instanceof Error ? generateError.message : "方案生成失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setError("");
    setNotice("");
    if (readiness.shouldPopup && !allowMissingFields) {
      setPendingSevereReadiness(readiness);
      return;
    }
    await runGenerate(allowMissingFields);
  };

  const handleContinueGenerate = async () => {
    setPendingSevereReadiness(null);
    await runGenerate(true);
  };

  const handleSaveDraft = async () => {
    setSaving(true);
    setError("");
    try {
      const nextVersion = createLocalVersion(plan, currentUserId, "用户编辑", "用户保存草稿/编辑内容");
      const nextPlan = { ...plan, currentVersionNumber: nextVersion.version_number, versions: [...(plan.versions ?? []), nextVersion] };
      setPlan(nextPlan);
      setPreviewVersionNumber(nextVersion.version_number);
      await onSaveDraft?.({ ...payload, sections: plan.sections });
      setNotice("草稿已保存，并已写入版本记录。");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存草稿失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async (type: ExportType) => {
    setError("");
    try {
      if (onExport) {
        await onExport(type, plan);
      } else {
        if (!plan.projectId) {
          throw new Error("请先生成报告后再导出。");
        }
        const response = await fetch(`${apiBaseUrl}/api/overseas-plans/${plan.projectId}/exports/${type}`, { method: "POST" });
        if (!response.ok) {
          throw new Error(`导出接口异常：${response.status}`);
        }
      }
      setNotice("导出任务已提交，请在下载中心查看生成文件。");
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "导出失败，请稍后重试。");
    }
  };

  const versionBeingPreviewed = plan.versions?.find((version) => version.version_number === previewVersionNumber);
  const visiblePlan = versionBeingPreviewed
    ? {
      ...plan,
      sections: versionBeingPreviewed.content_json.sections,
      countryMatrix: versionBeingPreviewed.content_json.countryMatrix ?? plan.countryMatrix,
      roadmap: versionBeingPreviewed.content_json.roadmap ?? plan.roadmap,
    }
    : plan;
  const isViewingHistoricalVersion = Boolean(versionBeingPreviewed && versionBeingPreviewed.version_number !== plan.currentVersionNumber);

  const handleSelectVersion = (version: PlanVersionRecord) => {
    setPreviewVersionNumber(version.version_number);
    setNotice(`正在查看 v${version.version_number}，如需继续使用请点击恢复为当前版本。`);
  };

  const handleRestoreVersion = async (version: PlanVersionRecord) => {
    setError("");
    try {
      const restored = await onRestoreVersion?.(version, plan);
      const nextPlan = restored ?? {
        ...plan,
        sections: version.content_json.sections,
        countryMatrix: version.content_json.countryMatrix ?? plan.countryMatrix,
        roadmap: version.content_json.roadmap ?? plan.roadmap,
        currentVersionNumber: version.version_number,
      };
      setPlan(nextPlan);
      setPreviewVersionNumber(nextPlan.currentVersionNumber ?? version.version_number);
      setNotice(`已恢复 v${version.version_number} 为当前版本。`);
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "恢复版本失败，请稍后重试。");
    }
  };

  const handleMarkFinalVersion = async (version: PlanVersionRecord) => {
    setError("");
    try {
      await onMarkFinalVersion?.(version, plan);
      setPlan((current) => ({
        ...current,
        versions: current.versions?.map((item) => ({ ...item, is_final: item.version_number === version.version_number })),
      }));
      setNotice(`v${version.version_number} 已设为最终版，后续导出将默认使用该版本。`);
    } catch (finalError) {
      setError(finalError instanceof Error ? finalError.message : "设置最终版失败，请稍后重试。");
    }
  };

  const handleToggleAuditPanel = async () => {
    const nextOpen = !showAuditPanel;
    setShowAuditPanel(nextOpen);
    if (!nextOpen) {
      return;
    }
    if (onOpenAuditLog) {
      onOpenAuditLog(plan.projectId);
      setAuditLogs(plan.auditLogs ?? []);
      return;
    }
    if (!plan.projectId) {
      setAuditLogs(plan.auditLogs ?? []);
      return;
    }
    try {
      const response = await fetch(`${apiBaseUrl}/api/overseas-plans/${plan.projectId}/audit-logs`);
      if (!response.ok) {
        throw new Error(`审计日志接口异常：${response.status}`);
      }
      const payload = await response.json();
      setAuditLogs(payload.logs ?? []);
    } catch (auditError) {
      setError(auditError instanceof Error ? auditError.message : "获取审计日志失败，请稍后重试。");
    }
  };

  const visibleAuditLogs = auditLogs.length > 0 ? auditLogs : (plan.auditLogs ?? []);

  const updateSection = (value: string) => {
    setPlan((current) => ({
      ...current,
      sections: { ...current.sections, [activeTab]: value },
    }));
  };

  return (
    <main className="overseas-workbench">
      <header className="overseas-workbench__header">
        <div>
          <p className="overseas-workbench__eyebrow">AI Overseas Expansion Planner</p>
          <h1>企业出海方案生成</h1>
          <p>基于企业库与产品库数据，快速生成、预览、编辑并导出企业出海方案。</p>
        </div>
        <div className="overseas-workbench__actions">
          <button type="button" className="button button--secondary" onClick={handleSaveDraft} disabled={saving || loading}>
            {saving ? "保存中..." : "保存草稿"}
          </button>
          <button type="button" className="button button--primary" onClick={handleGenerate} disabled={loading}>
            {loading ? "生成中..." : "生成方案"}
          </button>
        </div>
      </header>

      <section className="selector-panel" aria-label="方案生成条件">
        <label>
          企业选择器
          <select value={enterpriseId} onChange={(event) => { setEnterpriseId(event.target.value); setProductIds([]); }}>
            {enterprises.map((enterprise) => <option key={enterprise.id} value={enterprise.id}>{enterprise.name}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>产品多选器</legend>
          <div className="chip-list">
            {availableProducts.map((product) => (
              <button key={product.id} type="button" className={productIds.includes(product.id) ? "chip chip--active" : "chip"} onClick={() => toggleProduct(product.id)}>
                {product.name}
              </button>
            ))}
          </div>
        </fieldset>
        <label>
          行业选择器
          <select value={industryId} onChange={(event) => setIndustryId(event.target.value)}>
            {industries.map((industry) => <option key={industry.id} value={industry.id}>{industry.name}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>目标国家选择器</legend>
          <div className="chip-list">
            {countries.map((country) => (
              <button key={country.id} type="button" className={targetCountryIds.includes(country.id) ? "chip chip--active" : "chip"} onClick={() => toggleCountry(country.id)}>
                {country.name}
              </button>
            ))}
          </div>
        </fieldset>
      </section>
      <section className="options-panel" aria-label="生成策略配置">
        <div>
          <p className="card-label">报告深度</p>
          <div className="depth-options">
            {reportDepthOptions.map((depth) => (
              <button key={depth.id} type="button" className={reportDepth === depth.id ? "depth-card depth-card--active" : "depth-card"} onClick={() => setReportDepth(depth.id)}>
                <strong>{depth.name}</strong>
                <span>{depth.description}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="switch-list">
          <label className="switch-row">
            <input type="checkbox" checked={useLocalKnowledgeBase} onChange={(event) => setUseLocalKnowledgeBase(event.target.checked)} />
            <span>启用本地知识库</span>
            <small>由后端检索企业资料、模板与历史案例</small>
          </label>
          <label className="switch-row">
            <input type="checkbox" checked={useWebResearch} onChange={(event) => setUseWebResearch(event.target.checked)} />
            <span>启用网络研究</span>
            <small>由后端联网补充公开市场信息与引用来源</small>
          </label>
          <label className="switch-row">
            <input type="checkbox" checked={allowMissingFields} onChange={(event) => setAllowMissingFields(event.target.checked)} />
            <span>允许缺失字段继续生成</span>
            <small>方案会提示需人工复核，前端不补造缺失数据</small>
          </label>
        </div>
      </section>

      {(loading || generationProgress > 0) && (
        <section className="progress-card" aria-label="生成进度展示">
          <div className="section-heading"><h2>生成进度</h2><span>{loading ? "后端任务处理中" : "已完成"}</span></div>
          <div className="progress-bar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={generationProgress} role="progressbar">
            <span style={{ width: `${generationProgress}%` }} />
          </div>
          <p>{generationProgress < 35 ? "提交生成参数..." : generationProgress < 82 ? "等待后端编排知识库/联网研究与报告生成..." : generationProgress < 100 ? "接收并渲染报告结果..." : "生成完成"}</p>
        </section>
      )}

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}
      {readiness.missingCategories.length > 0 && (
        <section className="readiness-card" aria-label="生成前缺失信息提醒">
          <div className={`readiness-card__status readiness-card__status--${readiness.statusCode}`}>
            <strong>{readiness.status}</strong>
            <span>{readiness.message}</span>
          </div>
          <div className="missing-groups">
            {readiness.missingCategories.map((category) => (
              <article className="missing-group" key={category.category}>
                <h3>{category.category}</h3>
                <div className="missing-tags">
                  {category.fields.map((field) => <span key={field}>{field}</span>)}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="diagnosis-card">
        <div>
          <p className="card-label">企业名称</p>
          <h2>{selectedEnterprise?.name ?? "未选择企业"}</h2>
        </div>
        <dl>
          <div><dt>主营产品</dt><dd>{selectedEnterprise?.mainProducts.join("、") || "--"}</dd></div>
          <div><dt>当前市场</dt><dd>{selectedEnterprise?.currentMarkets.join("、") || "--"}</dd></div>
          <div><dt>出口占比</dt><dd>{selectedEnterprise?.exportRatio ?? "待补充"}</dd></div>
          <div><dt>认证情况</dt><dd>{selectedEnterprise?.certifications?.join("、") || "待补充"}</dd></div>
          <div><dt>产能</dt><dd>{selectedEnterprise?.capacity ?? "待补充"}</dd></div>
          <div><dt>MOQ</dt><dd>{selectedEnterprise?.moq ?? "待补充"}</dd></div>
          <div><dt>成熟度评分</dt><dd>{selectedEnterprise?.maturityScore ?? "--"}</dd></div>
          <div><dt>成熟度等级</dt><dd>{selectedEnterprise?.maturityLevel ?? "待评估"}</dd></div>
        </dl>
      </section>

      <section className="version-entry-card">
        <div>
          <p className="card-label">版本记录</p>
          <h2>当前版本：v{plan.currentVersionNumber ?? "--"}</h2>
          <p>每次AI生成、重新生成和用户保存编辑都会保留历史版本；导出默认使用最终版，没有最终版时使用最新完成版。</p>
        </div>
        <div className="version-entry-card__actions">
          <button type="button" className="button button--secondary" onClick={() => setShowVersionPanel((open) => !open)}>
            {showVersionPanel ? "收起版本记录" : "查看版本记录"}
          </button>
          <button type="button" className="button button--secondary" onClick={handleToggleAuditPanel}>{showAuditPanel ? "收起审计日志" : "审计日志入口"}</button>
        </div>
      </section>

      {showVersionPanel && (
        <section className="version-panel" aria-label="方案版本记录">
          {(plan.versions ?? []).map((version) => (
            <article className={version.version_number === previewVersionNumber ? "version-item version-item--active" : "version-item"} key={version.version_number}>
              <div>
                <strong>v{version.version_number}{version.is_final ? " · 最终版" : ""}</strong>
                <span>{new Date(version.created_at).toLocaleString()} · {version.created_by ?? "--"} · {version.generation_source}</span>
                {version.change_summary && <p>{version.change_summary}</p>}
              </div>
              <div className="version-item__actions">
                <button type="button" onClick={() => handleSelectVersion(version)}>切换查看</button>
                <button type="button" onClick={() => handleRestoreVersion(version)}>恢复为当前版本</button>
                <button type="button" onClick={() => handleMarkFinalVersion(version)} disabled={version.is_final}>设为最终版</button>
              </div>
            </article>
          ))}
          {(plan.versions ?? []).length === 0 && <div className="empty-state">生成或保存方案后展示版本记录。</div>}
        </section>
      )}

      {showAuditPanel && (
        <section className="audit-panel" aria-label="方案审计日志">
          {visibleAuditLogs.map((log) => (
            <article className="audit-item" key={log.id}>
              <div>
                <strong>{log.action_type}</strong>
                <span>{new Date(log.created_at).toLocaleString()} · {log.username ?? log.user_id ?? log.edited_by ?? log.finalized_by ?? "--"} · {log.result_status}</span>
                {log.export_type && <p>导出类型：{log.export_type} · 版本：{log.export_audience === "internal" ? "内部版" : "客户版"}</p>}
              </div>
              <dl className="audit-item__meta">
                <div><dt>企业资料</dt><dd>{log.used_enterprise_data?.length ?? 0}</dd></div>
                <div><dt>产品资料</dt><dd>{log.used_product_data?.length ?? 0}</dd></div>
                <div><dt>本地知识库</dt><dd>{log.used_local_knowledge_files?.length ?? 0}</dd></div>
                <div><dt>联网研究</dt><dd>{log.web_research_enabled ? "已启用" : "未启用"}</dd></div>
                <div><dt>外部来源</dt><dd>{log.external_sources?.length ?? 0}</dd></div>
              </dl>
            </article>
          ))}
          {visibleAuditLogs.length === 0 && <div className="empty-state">生成、编辑、定稿或导出后展示审计日志。</div>}
        </section>
      )}

      <section className="preview-grid">
        <article className="preview-card">
          <div className="section-heading"><h2>报告结果预览 / 人工编辑</h2><span>{isViewingHistoricalVersion ? "历史版本只读" : "当前版本可编辑"}</span></div>
          <div className="tab-list" role="tablist">
            {sectionTabs.map((tab) => (
              <button key={tab.key} type="button" role="tab" aria-selected={activeTab === tab.key} className={activeTab === tab.key ? "tab tab--active" : "tab"} onClick={() => setActiveTab(tab.key)}>
                {tab.label}
              </button>
            ))}
          </div>
          <textarea className="editor" value={visiblePlan.sections[activeTab]} onChange={(event) => updateSection(event.target.value)} aria-label={`${sectionTabs.find((tab) => tab.key === activeTab)?.label}编辑区`} readOnly={isViewingHistoricalVersion} />
          {isViewingHistoricalVersion && <p className="editor-hint">当前为历史版本只读预览，请先恢复为当前版本后再编辑。</p>}
        </article>

        <aside className="export-card">
          <h2>导出方案</h2>
          <p>支持在编辑AI生成内容后导出不同交付物。</p>
          <button type="button" onClick={() => handleExport("word")}>导出Word方案</button>
          <button type="button" onClick={() => handleExport("ppt")}>导出PPT方案</button>
          <button type="button" onClick={() => handleExport("excel")}>导出Excel行动计划表</button>
          <button type="button" onClick={() => handleExport("resources")}>导出资源对接清单</button>
        </aside>
      </section>


      <section className="insight-grid" aria-label="数据来源和质量评分">
        <article className="source-card">
          <div className="section-heading"><h2>数据来源展示</h2><span>{useWebResearch ? "含联网研究" : "未启用联网研究"}</span></div>
          {(visiblePlan.dataSources ?? []).map((source) => (
            <div className="source-item" key={source.id}>
              <strong>{source.name}</strong>
              <span>{source.type}{source.updatedAt ? ` · ${source.updatedAt}` : ""}</span>
              {source.url && <a href={source.url} target="_blank" rel="noreferrer">查看来源</a>}
            </div>
          ))}
          {(visiblePlan.dataSources ?? []).length === 0 && <div className="empty-state">生成方案后由后端返回引用来源、知识库命中文档和人工编辑记录。</div>}
        </article>
        <article className="quality-card">
          <div className="section-heading"><h2>质量评分展示</h2><span>{visiblePlan.qualityScore ? `${visiblePlan.qualityScore.overall}/100` : "待评分"}</span></div>
          {visiblePlan.qualityScore ? (
            <dl className="quality-list">
              <div><dt>完整度</dt><dd>{visiblePlan.qualityScore.completeness}</dd></div>
              <div><dt>证据充分性</dt><dd>{visiblePlan.qualityScore.evidence}</dd></div>
              <div><dt>落地可行性</dt><dd>{visiblePlan.qualityScore.feasibility}</dd></div>
              <div><dt>风险覆盖</dt><dd>{visiblePlan.qualityScore.riskCoverage}</dd></div>
              {visiblePlan.qualityScore.comment && <div className="quality-list__comment"><dt>评分说明</dt><dd>{visiblePlan.qualityScore.comment}</dd></div>}
            </dl>
          ) : <div className="empty-state">生成方案后展示后端质量评分，不在前端计算评分。</div>}
        </article>
      </section>

      <section className="matrix-card">
        <div className="section-heading">
          <h2>国家优先级矩阵</h2>
          <span>X轴：市场潜力 / Y轴：进入难度</span>
        </div>
        <div className="matrix-table" role="table" aria-label="国家优先级矩阵">
          <div className="matrix-table__row matrix-table__row--head" role="row">
            <span>国家</span><span>市场潜力</span><span>进入难度</span><span>优先级</span><span>建议</span>
          </div>
          {visiblePlan.countryMatrix.map((item) => (
            <div className="matrix-table__row" role="row" key={item.country}>
              <span>{item.country}</span><span>{item.marketPotential}</span><span>{item.entryDifficulty}</span><span>{item.priority}</span><span>{item.recommendation}</span>
            </div>
          ))}
          {visiblePlan.countryMatrix.length === 0 && <div className="empty-state">生成方案后展示国家优先级矩阵。</div>}
        </div>
      </section>

      <section className="roadmap-card">
        <div className="section-heading"><h2>12-24个月路线图</h2><span>按阶段推进市场验证、渠道建设与本地化布局</span></div>
        <div className="timeline">
          {visiblePlan.roadmap.map((item) => (
            <article className="timeline__item" key={item.period}>
              <time>{item.period}</time>
              <h3>{item.title}</h3>
              <ul>{item.actions.map((action) => <li key={action}>{action}</li>)}</ul>
              {item.owner && <p>负责人：{item.owner}</p>}
            </article>
          ))}
          {visiblePlan.roadmap.length === 0 && <div className="empty-state">生成方案后展示分阶段路线图。</div>}
        </div>
      </section>

      {pendingSevereReadiness && (
        <div className="modal-backdrop" role="presentation">
          <section className="validation-modal" role="dialog" aria-modal="true" aria-label="缺失信息严重提示">
            <p className="card-label">生成前校验</p>
            <h2>{pendingSevereReadiness.status}</h2>
            <p>{pendingSevereReadiness.message}</p>
            <div className="missing-groups missing-groups--modal">
              {pendingSevereReadiness.missingCategories.map((category) => (
                <article className="missing-group" key={category.category}>
                  <h3>{category.category}</h3>
                  <div className="missing-tags">
                    {category.fields.map((field) => <span key={field}>{field}</span>)}
                  </div>
                </article>
              ))}
            </div>
            <p className="validation-modal__hint">继续生成后，系统会将方案标记为“需人工补充/复核”，并要求AI不要编造缺失信息。</p>
            <div className="validation-modal__actions">
              <button type="button" className="button button--secondary" onClick={() => setPendingSevereReadiness(null)}>返回补充</button>
              <button type="button" className="button button--primary" onClick={handleContinueGenerate}>继续生成</button>
            </div>
          </section>
        </div>
      )}

      {loading && <div className="loading-mask" role="status">AI正在生成方案，请稍候...</div>}
      <input type="hidden" value={currentUserId} readOnly />
    </main>
  );
}
