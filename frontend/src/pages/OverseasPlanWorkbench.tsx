import { useMemo, useState } from "react";

import "./overseas-plan-workbench/OverseasPlanWorkbench.css";

export type Option = {
  id: string;
  name: string;
};

export type ProductOption = Option & {
  enterpriseId: string;
  certifications?: string[];
  capacity?: string;
  moq?: string;
};

export type EnterpriseProfile = Option & {
  mainProducts: string[];
  currentMarkets: string[];
  exportRatio?: string;
  certifications?: string[];
  capacity?: string;
  moq?: string;
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

export type GeneratedPlan = {
  projectId?: string;
  sections: EditableSections;
  countryMatrix: CountryMatrixItem[];
  roadmap: RoadmapItem[];
  currentVersionNumber?: number;
  versions?: PlanVersionRecord[];
};

export type GeneratePlanPayload = {
  enterpriseId: string;
  productIds: string[];
  selectedIndustry: string;
  targetCountries: string[];
};

export type ExportType = "word" | "ppt" | "excel" | "resources";

export type OverseasPlanWorkbenchProps = {
  enterprises?: EnterpriseProfile[];
  products?: ProductOption[];
  industries?: Option[];
  countries?: Option[];
  currentUserId?: string;
  onGenerate?: (payload: GeneratePlanPayload) => Promise<GeneratedPlan>;
  onSaveDraft?: (draft: GeneratePlanPayload & { sections: EditableSections }) => Promise<void>;
  onExport?: (type: ExportType, plan: GeneratedPlan) => Promise<void>;
  onRestoreVersion?: (version: PlanVersionRecord, plan: GeneratedPlan) => Promise<GeneratedPlan | void>;
  onMarkFinalVersion?: (version: PlanVersionRecord, plan: GeneratedPlan) => Promise<PlanVersionRecord | void>;
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
    exportRatio: "18%",
    certifications: ["CE", "ISO 13485"],
    capacity: "10,000台/月",
    moq: "50台",
    maturityScore: 76,
    maturityLevel: "全球化布局型",
    missingFields: ["目标国售后服务商", "英文案例视频"],
  },
  {
    id: "ent-2",
    name: "样例新能源装备有限公司",
    mainProducts: ["储能逆变器", "户用储能柜"],
    currentMarkets: ["国内", "中东询盘"],
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
  { id: "prod-1", enterpriseId: "ent-1", name: "便携式检测仪", certifications: ["CE", "ISO 13485"], capacity: "10,000台/月", moq: "50台" },
  { id: "prod-2", enterpriseId: "ent-1", name: "智能监测终端", certifications: ["CE"], capacity: "6,000台/月", moq: "100台" },
  { id: "prod-3", enterpriseId: "ent-2", name: "储能逆变器", certifications: ["IEC"], capacity: "2,000套/月", moq: "20套" },
];

const defaultIndustries: Option[] = [
  { id: "medical-device", name: "医疗器械" },
  { id: "new-energy", name: "新能源装备" },
  { id: "industrial-equipment", name: "工业设备" },
  { id: "consumer-electronics", name: "消费电子" },
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

const buildPreviewPlan = (enterprise: EnterpriseProfile | undefined, countries: string[]): GeneratedPlan => {
  const countryNames = countries.length > 0 ? countries : ["德国", "美国", "阿联酋"];

  const createdAt = new Date().toISOString();
  const previewPlan: GeneratedPlan = {
    projectId: `preview-${Date.now()}`,
    sections: {
      enterpriseDiagnosis: `${enterprise?.name ?? "所选企业"}已具备基础产品与认证能力，建议优先补齐目标国准入、英文销售素材和本地售后网络。`,
      marketSelection: `建议优先评估${countryNames.join("、")}，按市场需求、政策准入、渠道成熟度和供应链适配度形成分层进入节奏。`,
      entryModeDesign: "第一阶段采用经销商+行业展会获客，第二阶段导入本地服务伙伴，第三阶段评估海外仓或轻量本地化组装。",
      resourceMatching: "重点对接当地行业协会、检测认证机构、头部经销商、物流仓储服务商和投促机构，形成可跟进清单。",
      exhibitionMarketing: "围绕年度行业展会、线上研讨会、LinkedIn内容矩阵和重点客户拜访制定季度推广节奏。",
      financingCapacity: "根据目标市场备货、认证、渠道保证金和售后备件需求，设计分阶段预算与产能扩充方案。",
      roadmap: "1-3个月完成资料补齐与国家筛选；3-6个月完成认证和渠道验证；6-12个月形成样板客户；12-24个月推进规模化复制。",
    },
    countryMatrix: countryNames.map((country, index) => ({
      country,
      marketPotential: Math.max(62, 90 - index * 8),
      entryDifficulty: Math.min(82, 48 + index * 11),
      priority: index === 0 ? "优先进入" : index === 1 ? "重点验证" : "机会储备",
      recommendation: index === 0 ? "渠道试点+展会获客" : "先做准入验证和伙伴筛选",
    })),
    roadmap: [
      { period: "1-3个月", title: "诊断与准备", actions: ["补齐认证/素材缺口", "完成目标国家优先级排序"], owner: "海外业务负责人" },
      { period: "3-6个月", title: "渠道验证", actions: ["对接经销商和认证机构", "启动小批量样品测试"], owner: "销售与产品团队" },
      { period: "6-9个月", title: "样板客户", actions: ["完成首批订单", "沉淀本地售后流程"], owner: "区域经理" },
      { period: "9-12个月", title: "规模复制", actions: ["扩大渠道覆盖", "建立季度推广机制"], owner: "增长团队" },
      { period: "12-24个月", title: "本地化布局", actions: ["评估海外仓/服务中心", "规划扩产与融资节点"], owner: "管理层" },
    ],
  };
  previewPlan.currentVersionNumber = 1;
  previewPlan.versions = [{
    version_number: 1,
    created_by: "AI",
    created_at: createdAt,
    generation_source: "AI生成",
    change_summary: "AI首次生成方案",
    content_json: { sections: previewPlan.sections, countryMatrix: previewPlan.countryMatrix, roadmap: previewPlan.roadmap },
  }];
  return previewPlan;
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
  onGenerate,
  onSaveDraft,
  onExport,
  onRestoreVersion,
  onMarkFinalVersion,
}: OverseasPlanWorkbenchProps) {
  const [enterpriseId, setEnterpriseId] = useState(enterprises[0]?.id ?? "");
  const [productIds, setProductIds] = useState<string[]>([]);
  const [industryId, setIndustryId] = useState(industries[0]?.id ?? "");
  const [targetCountryIds, setTargetCountryIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<PlanSectionKey>("enterpriseDiagnosis");
  const [plan, setPlan] = useState<GeneratedPlan>({ sections: emptySections, countryMatrix: [], roadmap: [] });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [previewVersionNumber, setPreviewVersionNumber] = useState<number | null>(null);

  const selectedEnterprise = enterprises.find((enterprise) => enterprise.id === enterpriseId);
  const availableProducts = useMemo(
    () => products.filter((product) => product.enterpriseId === enterpriseId),
    [enterpriseId, products],
  );
  const selectedIndustry = industries.find((industry) => industry.id === industryId)?.name ?? "";
  const selectedCountryNames = countries
    .filter((country) => targetCountryIds.includes(country.id))
    .map((country) => country.name);

  const missingWarnings = [
    !enterpriseId ? "请选择企业" : "",
    productIds.length === 0 ? "请选择至少一个产品" : "",
    !industryId ? "请选择行业" : "",
    targetCountryIds.length === 0 ? "请选择至少一个目标国家" : "",
    ...(selectedEnterprise?.missingFields ?? []),
  ].filter(Boolean);

  const payload: GeneratePlanPayload = {
    enterpriseId,
    productIds,
    selectedIndustry,
    targetCountries: selectedCountryNames,
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

  const handleGenerate = async () => {
    setError("");
    setNotice("");
    if (!enterpriseId || productIds.length === 0 || !industryId || targetCountryIds.length === 0) {
      setError("信息不完整，请先补充企业、产品、行业和目标国家后再生成方案。");
      return;
    }

    setLoading(true);
    try {
      const nextPlan = onGenerate ? await onGenerate(payload) : await new Promise<GeneratedPlan>((resolve) => {
        window.setTimeout(() => resolve(buildPreviewPlan(selectedEnterprise, selectedCountryNames)), 700);
      });
      setPlan(ensureVersionHistory(nextPlan, currentUserId, "AI生成"));
      setPreviewVersionNumber(nextPlan.currentVersionNumber ?? nextPlan.versions?.[nextPlan.versions.length - 1]?.version_number ?? null);
      setNotice("方案已生成，可在预览区编辑后导出，也可进入版本记录查看历史。");
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "方案生成失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
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
      await onExport?.(type, plan);
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

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}
      {missingWarnings.length > 0 && (
        <div className="alert alert--warning">
          <strong>信息缺失提醒：</strong>{missingWarnings.join("；")}
        </div>
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
        <button type="button" className="button button--secondary" onClick={() => setShowVersionPanel((open) => !open)}>
          {showVersionPanel ? "收起版本记录" : "查看版本记录"}
        </button>
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

      <section className="preview-grid">
        <article className="preview-card">
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

      {loading && <div className="loading-mask" role="status">AI正在生成方案，请稍候...</div>}
      <input type="hidden" value={currentUserId} readOnly />
    </main>
  );
}
