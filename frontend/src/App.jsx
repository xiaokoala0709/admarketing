import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import NodePill from './NodePill'
import { mapPlatformMark } from './nodeThemes'
import { fetchTodayHotspots, generateBrandAssetBrief, generateImage, runAgent } from './api/agents'
import './App.css'

function formatCurrentDate(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}.${month}.${day}`
}

const currentNode = {
  date: formatCurrentDate(),
  type: 'international',
}

const todayHotspots = [
  {
    id: 1,
    title: '通勤防晒与轻户外内容持续升温',
    platform: '抖音',
    platformMark: '抖',
    tag: '夏季出行',
    category: '服饰 / 防晒用品',
    date: formatCurrentDate(),
    node_type: 'lifestyle_trend',
    node_label: '生活趋势',
  },
  {
    id: 2,
    title: '办公室低负担零食饮料讨论增加',
    platform: '小红书',
    platformMark: '红',
    tag: '办公室补给',
    category: '食品饮料 / 即食轻餐',
    date: formatCurrentDate(),
    node_type: 'lifestyle_trend',
    node_label: '生活趋势',
  },
  {
    id: 3,
    title: '夏季居家清洁与香氛内容关注上升',
    platform: '小红书',
    platformMark: '红',
    tag: '入夏焕新',
    category: '家清 / 家居香氛',
    date: formatCurrentDate(),
    node_type: 'solar_term',
    node_label: '二十四节气',
  },
  {
    id: 4,
    title: '618 囤货清单内容升温，低负担消费表达增加',
    platform: '小红书',
    platformMark: '红',
    tag: '囤货清单',
    category: '美妆 / 食品饮料 / 家清',
    date: formatCurrentDate(),
    node_type: 'ecommerce_node',
    node_label: '电商节点',
  },
  {
    id: 5,
    title: '周末城市短途出逃与轻装备内容走高',
    platform: '微信',
    platformMark: '微',
    tag: '城市短逃',
    category: '旅行 / 户外装备',
    date: formatCurrentDate(),
    node_type: 'lifestyle_trend',
    node_label: '生活趋势',
  },
]

const defaultPrompt = `你是一名品牌内容策略顾问。请基于所选热点，为 AdaMarketing 输出适合社媒运营团队直接使用的建议。
品牌背景：新消费品牌，关注年轻都市人群，语气克制、有审美感、不喊口号。
输出要求：给出一份适合品牌运营查看的热点工作台内容，重点说明：热点背景、用户情绪、品类机会、品牌切入角度、内容选题、执行动作、风险提醒。`

function buildHotspotContext(trend) {
  if (!trend) {
    return ''
  }

  return [
    `- 热点标题：${trend.title}`,
    `- 平台：${trend.platform}`,
    `- 标签：${trend.tag}`,
    `- 适合品类：${trend.category}`,
    `- 节点类型：${trend.node_label}`,
    `- 日期：${trend.date}`,
  ].join('\n')
}

const defaultCampaignBrandForm = {
  brandName: '初晴',
  productName: '初晴轻萃白桃气泡饮 330ml × 6 / 59 元',
  category: '低糖气泡饮',
  audience: '25-35 岁的一线城市女性白领',
  goal: '促进转化',
  timing: '618',
  formatPreference: '线上内容种草 + 直播联动',
  budget: '180000',
  resources: '品牌短片、达人种草素材、线下快闪空间',
  support: '小红书首页曝光与城市级联动资源',
}

const defaultCampaignPlatformForm = {
  platformName: '小红书',
  audienceProfile: '关注情绪价值与生活方式表达的年轻女性',
  themeDirection: '夏日轻养生活节',
  goal: '品牌声量与用户增长',
  timing: '618',
  targetBrands: '美妆个护、轻食品饮、家居香氛',
  resources: '话题会场、达人共创、搜索联想位',
  budgetSupport: '5 万 - 20 万',
  conditions: '品牌需提供明确主视觉、节点权益和可转化货盘',
}

const defaultBrandAssetForm = {
  kvProductName: '初晴轻萃白桃气泡饮',
  kvSlogan: '让今天轻一点，也亮一点',
  kvSellingPoint: '0 蔗糖、清爽白桃风味、轻盈气泡感',
  detailProductName: '初晴轻萃白桃气泡饮',
  detailSellingPoint1: '0 蔗糖',
  detailSellingPoint2: '白桃清香',
  detailSellingPoint3: '330ml 便携装',
  detailPlatform: '小红书',
  socialTitle: '把初夏第一口清爽留给自己',
  socialBenefit: '低负担解馋，也适合分享给闺蜜',
  socialPlatform: '小红书',
  promotionText: '618低至6.18折',
  visualStyle: '参考图风格',
  addTextLayer: true,
}

function inferPlatformName(text) {
  const source = text || ''

  if (source.includes('小红书')) {
    return '小红书'
  }

  if (source.includes('抖音')) {
    return '抖音'
  }

  if (source.includes('微博')) {
    return '微博'
  }

  if (source.includes('B站')) {
    return 'B站'
  }

  if (source.includes('微信')) {
    return '微信'
  }

  return '内容平台'
}

function buildCreativeCampaignName(role, primaryName, timing) {
  const name = (primaryName || (role === 'brand' ? '品牌' : '平台')).replace(/\s+/g, '').slice(0, 3)

  if (timing.includes('618')) {
    return role === 'brand' ? `${name}抢鲜局` : `${name}囤货局`
  }

  if (timing.includes('母亲节')) {
    return role === 'brand' ? `${name}心意局` : `${name}礼赠局`
  }

  if (timing.includes('开学')) {
    return role === 'brand' ? `${name}开学局` : `${name}新学局`
  }

  if (timing.includes('七夕')) {
    return role === 'brand' ? `${name}告白局` : `${name}甜度局`
  }

  return role === 'brand' ? `${name}上新局` : `${name}招募局`
}

function buildCampaignPromptEntries(role, form) {
  if (role === 'brand') {
    return [
      ['角色类型', '品牌方'],
      ['品牌名', form.brandName || '未填写'],
      ['产品信息（全称 / 价格 / 规格）', form.productName || '未填写'],
      ['品类', form.category || '未填写'],
      ['目标用户', form.audience || '未填写'],
      ['活动核心目标', form.goal || '未填写'],
      ['节点档期', form.timing || '未填写'],
      ['活动形式偏向', form.formatPreference || '未填写'],
      ['预算（元）', form.budget || '未填写'],
      ['可配合资源', form.resources || '未填写'],
      ['期望平台支持', form.support || '未填写'],
    ]
  }

  return [
    ['角色类型', '平台方'],
    ['平台名', form.platformName || '未填写'],
    ['核心用户画像', form.audienceProfile || '未填写'],
    ['活动主题方向', form.themeDirection || '未填写'],
    ['核心目标', form.goal || '未填写'],
    ['节点档期', form.timing || '未填写'],
    ['招募品牌方向', form.targetBrands || '未填写'],
    ['可提供资源', form.resources || '未填写'],
    ['预算支持范围（元）', form.budgetSupport || '未填写'],
    ['合作条件', form.conditions || '未填写'],
  ]
}

function buildCampaignPrompt(role, form) {
  return buildCampaignPromptEntries(role, form)
    .map(([key, value]) => `- ${key}：${value}`)
    .join('\n')
}

function buildCampaignPayload(role, form) {
  const entries = buildCampaignPromptEntries(role, form).map(([key, value]) => ({
    key,
    value,
  }))

  return {
    prompt: buildCampaignPrompt(role, form),
    structured_context: {
      role,
      entries,
    },
  }
}

function buildCampaignMarkdown(plan, note) {
  if (!plan) {
    return ''
  }

  const sections = plan.sections
    .map((section) => {
      const body = section.markdown || section.paragraphs.join('\n\n')
      return `## ${section.title}\n\n${body}`
    })
    .join('\n\n')

  const adjustment = note ? `\n\n## 微调方向\n\n${note}` : ''

  return `# ${plan.title}\n\n${plan.intro}\n\n${sections}${adjustment}`
}

function pickSectionBullets(section, limit = 3) {
  const markdownText = String(section?.markdown ?? section?.paragraphs?.join('\n') ?? '').trim()
  if (!markdownText) {
    return []
  }

  const bulletMatches = markdownText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => /^(-|\*|\d+\.)\s+/.test(line))
    .map((line) => line.replace(/^(-|\*|\d+\.)\s+/, '').replace(/^- \[ \]\s+/, '').trim())
    .filter(Boolean)

  if (bulletMatches.length) {
    return bulletMatches.slice(0, limit)
  }

  return markdownText
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, limit)
}

function buildCampaignSummary(plan) {
  if (!plan) {
    return {
      conclusion: '已生成策略方案，可切换模块查看详情。',
      opportunities: [],
      priorities: [],
    }
  }

  const sections = Array.isArray(plan.sections) ? plan.sections : []
  const strategySection = sections.find((section) => section.title.includes('策略判断')) ?? sections[0]
  const opportunitySection = sections.find((section) => section.title.includes('机会')) ?? sections[1] ?? sections[0]
  const actionSection =
    sections.find((section) => section.title.includes('执行清单')) ??
    sections.find((section) => section.title.includes('活动机制')) ??
    sections.find((section) => section.title.includes('执行节奏')) ??
    sections[2] ??
    sections[0]

  const conclusion = pickSectionBullets(strategySection, 1)[0] || plan.intro || '已生成策略方案，可切换模块查看详情。'
  const opportunities = pickSectionBullets(opportunitySection, 3)
  const priorities = pickSectionBullets(actionSection, 3)

  return {
    conclusion,
    opportunities: opportunities.length ? opportunities : sections.slice(0, 3).map((section) => section.title),
    priorities: priorities.length ? priorities : sections.slice(0, 3).map((section) => section.title),
  }
}

function buildBrandAssetContext(taskType, form, uploads) {
  if (taskType === 'kv') {
    return [
      `任务类型：品牌 KV 主视觉`,
      `产品名：${form.kvProductName || '未填写'}`,
      `品牌 Slogan：${form.kvSlogan || '未填写'}`,
      `主卖点：${form.kvSellingPoint || '未填写'}`,
      `产品图：${uploads.productImage || '未上传'}`,
      `参考风格图：${uploads.styleImage || '未上传'}`,
    ].join('\n')
  }

  if (taskType === 'detail') {
    return [
      `任务类型：产品详情页主图`,
      `产品名：${form.detailProductName || '未填写'}`,
      `卖点一：${form.detailSellingPoint1 || '未填写'}`,
      `卖点二：${form.detailSellingPoint2 || '未填写'}`,
      `卖点三：${form.detailSellingPoint3 || '未填写'}`,
      `发布平台：${form.detailPlatform || '未填写'}`,
      `产品图：${uploads.productImage || '未上传'}`,
      `参考风格图：${uploads.styleImage || '未上传'}`,
    ].join('\n')
  }

  return [
    `任务类型：社交媒体海报`,
    `主标题：${form.socialTitle || '未填写'}`,
    `副标题：${form.socialBenefit || '未填写'}`,
    `发布平台：${form.socialPlatform || '未填写'}`,
    `产品图：${uploads.productImage || '未上传'}`,
    `参考风格图：${uploads.styleImage || '未上传'}`,
  ].join('\n')
}

function buildBrandAssetPrompt(taskType, form) {
  if (taskType === 'kv') {
    return `请生成一份适合品牌 KV 主视觉的视觉 brief 和 image prompt，突出 ${form.kvProductName || '产品主体'}，强调 ${form.kvSellingPoint || '核心卖点'}，并保留品牌文案展示空间。`
  }

  if (taskType === 'detail') {
    return `请生成一份适合电商详情页主图的视觉 brief 和 image prompt，围绕 ${form.detailProductName || '产品主体'} 展开，清晰表达 ${form.detailSellingPoint1 || '卖点一'}、${form.detailSellingPoint2 || '卖点二'}、${form.detailSellingPoint3 || '卖点三'}。`
  }

  return `请生成一份适合社交媒体海报的视觉 brief 和 image prompt，主标题为“${form.socialTitle || '待补充'}”，副标题聚焦“${form.socialBenefit || '待补充'}”，平台场景为 ${form.socialPlatform || '内容平台'}。`
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('图片读取失败，请重新上传'))
    reader.readAsDataURL(file)
  })
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function InlineField({ value, onChange, placeholder }) {
  const width = Math.max(80, ((value || placeholder).length + 1) * 14)

  return (
    <input
      className="inline-field"
      style={{ width: `${width}px` }}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

function BriefPage({
  selectedId,
  setSelectedId,
  prompt,
  setPrompt,
  promptExpanded,
  setPromptExpanded,
  briefResult,
  setBriefResult,
  briefLoading,
  setBriefLoading,
  briefError,
  setBriefError,
  hotspots,
  copied,
  setCopied,
}) {
  const navigate = useNavigate()
  const selectedTrend = useMemo(
    () => hotspots.find((trend) => trend.id === selectedId) ?? null,
    [hotspots, selectedId],
  )

  function handleSelectTrend(trend) {
    setSelectedId(trend.id)
    setBriefResult(null)
    setBriefError('')
    setCopied(false)
  }

  async function handleGenerate() {
    if (!selectedTrend) {
      return
    }

    setBriefLoading(true)
    setBriefError('')
    setCopied(false)

    try {
      const result = await runAgent('agent_1', {
        prompt,
        context: buildHotspotContext(selectedTrend),
      })
      setBriefResult(result.output ?? null)
    } catch (error) {
      setBriefResult(null)
      setBriefError(error instanceof Error ? error.message : '生成失败，请稍后重试')
    } finally {
      setBriefLoading(false)
    }
  }

  async function handleCopy() {
    if (!briefResult) {
      return
    }

    const content = [
      `热点背景：${briefResult.background}`,
      `用户情绪：${briefResult.emotion}`,
      `品类机会：${briefResult.categoryOpportunity}`,
      `品牌切入角度：${briefResult.brandAngle}`,
      `内容选题：\n${briefResult.contentTopics.map((item) => `- ${item}`).join('\n')}`,
      `执行动作：\n${briefResult.actionSteps.map((item) => `- ${item}`).join('\n')}`,
      `风险提醒：${briefResult.riskAlert}`,
    ].join('\n\n')

    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <main className="page-shell page-body">
      <section className="trends-column">
        <div className="page-title-block section-heading">
          <h1>热点速递站</h1>
          <p>从今天值得关注的话题中，挑一个适合品牌借势表达的入口。</p>
        </div>

        <div className="trend-list">
          {hotspots.map((trend) => {
            const isSelected = trend.id === selectedId

            return (
              <button
                key={trend.id}
                className={`trend-card trend-card--${trend.node_type}${isSelected ? ' trend-card--selected' : ''}`}
                type="button"
                onClick={() => handleSelectTrend(trend)}
              >
                <div className="trend-card__title">{trend.title}</div>

                <div className="trend-card__meta-row">
                  <span className="platform">
                    <span className={`platform__icon platform__icon--${trend.platform}`}>
                      {trend.platformMark}
                    </span>
                    <span>{trend.platform}</span>
                  </span>
                  <NodePill nodeType={trend.node_type} nodeLabel={trend.node_label} />
                </div>

                <div className="trend-card__footer">
                  <span className="trend-card__category">{trend.category}</span>
                  <span className="trend-card__date">{trend.date}</span>
                </div>
              </button>
            )
          })}
        </div>
      </section>

      <section className="strategy-column">
        {!selectedTrend ? (
          <div className="empty-state">选择一个今日热点，开始生成运营建议</div>
        ) : (
          <div className="strategy-panel">
            <div className="strategy-panel__hero">
              <div className="eyebrow">已选热点</div>
              <h2>{selectedTrend.title}</h2>
              <div className="strategy-panel__meta">
                <span className="strategy-meta-pill">{selectedTrend.platform}</span>
                <NodePill nodeType={selectedTrend.node_type} nodeLabel={selectedTrend.node_label} className="node-pill--compact" />
                <span className="strategy-meta-pill">{selectedTrend.category}</span>
              </div>
              <p className={`strategy-summary${briefResult?.summary ? '' : ' strategy-summary--placeholder'}`}>
                {briefResult?.summary || '生成后，这里会先给出一条适合运营快速理解的借势判断。'}
              </p>
            </div>

            <div className="prompt-card prompt-card--editorial">
              <div className="prompt-card__header">
                <span className="card-title">用户背景 Prompt</span>
                <button
                  className="text-link text-link--small"
                  type="button"
                  onClick={() => setPromptExpanded((current) => !current)}
                >
                  {promptExpanded ? '收起' : '展开'}
                </button>
              </div>

              <textarea
                className={`prompt-input${promptExpanded ? ' prompt-input--expanded' : ''}`}
                rows={promptExpanded ? 6 : 1}
                value={prompt}
                onFocus={() => setPromptExpanded(true)}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </div>

            <div className="strategy-panel__actions">
              <button className="generate-button" type="button" onClick={handleGenerate} disabled={briefLoading}>
                {briefLoading ? '生成中...' : '生成运营建议'}
              </button>
            </div>

            {briefError ? <div className="empty-state empty-state--panel">{briefError}</div> : null}
            {!briefError && !briefResult ? (
              <div className="empty-state empty-state--panel">
                {briefLoading ? '正在生成今日热点运营建议...' : '点击生成运营建议，查看今天的借势思路'}
              </div>
            ) : null}

            {briefResult ? (
              <div className="output-stack">
                <div className="strategy-grid">
                  <article className="output-card output-card--panel">
                    <h3>热点背景</h3>
                    <p>{briefResult.background}</p>
                  </article>

                  <article className="output-card output-card--panel">
                    <h3>用户情绪</h3>
                    <p>{briefResult.emotion}</p>
                  </article>

                  <article className="output-card output-card--panel">
                    <h3>品类机会</h3>
                    <p>{briefResult.categoryOpportunity}</p>
                  </article>

                  <article className="output-card output-card--panel">
                    <h3>品牌切入角度</h3>
                    <p>{briefResult.brandAngle}</p>
                  </article>
                </div>

                <article className="output-card output-card--panel output-card--wide">
                  <h3>内容选题</h3>
                  <ul className="output-list">
                    {briefResult.contentTopics.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>

                <article className="output-card output-card--panel output-card--wide">
                  <h3>执行动作</h3>
                  <ul className="output-list">
                    {briefResult.actionSteps.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>

                <article className="output-card output-card--panel output-card--wide output-card--muted">
                  <h3>风险提醒</h3>
                  <p>{briefResult.riskAlert}</p>
                </article>

                <div className="output-footer">
                  <button className="secondary-button" type="button" onClick={handleCopy}>
                    {copied ? '已复制' : '复制'}
                  </button>
                  <button className="secondary-button" type="button" onClick={() => navigate('/workshop')}>
                    带入创意工作坊
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </main>
  )
}

function WorkshopPage({
  campaignRole,
  setCampaignRole,
  campaignBrandForm,
  setCampaignBrandForm,
  campaignPlatformForm,
  setCampaignPlatformForm,
  campaignOutput,
  setCampaignOutput,
  campaignLoading,
  setCampaignLoading,
  campaignError,
  setCampaignError,
  campaignAdjustment,
  setCampaignAdjustment,
  campaignAdjustmentNote,
  setCampaignAdjustmentNote,
  setBrandAssetTaskType,
  setBrandAssetForm,
}) {
  const navigate = useNavigate()
  const [selectedCampaignSection, setSelectedCampaignSection] = useState(0)

  const campaignSections = campaignOutput?.sections ?? []
  const campaignSummary = useMemo(() => buildCampaignSummary(campaignOutput), [campaignOutput])
  const activeCampaignSection = campaignSections[selectedCampaignSection] ?? campaignSections[0] ?? null

  useEffect(() => {
    setSelectedCampaignSection(0)
  }, [campaignOutput])

  function handleCampaignFieldChange(field, value) {
    if (campaignRole === 'brand') {
      setCampaignBrandForm((current) => ({
        ...current,
        [field]: value,
      }))
      return
    }

    setCampaignPlatformForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  async function handleGenerateCampaign() {
    const source = campaignRole === 'brand' ? campaignBrandForm : campaignPlatformForm

    setCampaignLoading(true)
    setCampaignError('')
    setCampaignAdjustmentNote('')

    try {
      const result = await runAgent('agent_2', buildCampaignPayload(campaignRole, source))
      setCampaignOutput(result.output)
      setCampaignError('')
    } catch (error) {
      setCampaignOutput(null)
      setCampaignError(error instanceof Error ? error.message : '生成失败，请稍后重试')
    } finally {
      setCampaignLoading(false)
    }
  }

  function handleCampaignAdjustmentSubmit() {
    if (!campaignAdjustment.trim()) {
      return
    }

    setCampaignAdjustmentNote(campaignAdjustment.trim())
    setCampaignAdjustment('')
  }

  function handleExportCampaignMarkdown() {
    if (!campaignOutput) {
      return
    }

    downloadText(
      'adamarketing-campaign-plan.md',
      buildCampaignMarkdown(campaignOutput, campaignAdjustmentNote),
    )
  }

  function handleCarryToBrandAssets() {
    if (!campaignOutput) {
      return
    }

    setBrandAssetTaskType('social')
    setBrandAssetForm((current) => ({
      ...current,
      socialTitle: campaignOutput.title,
      socialBenefit: campaignOutput.sections[0]?.paragraphs[0] || current.socialBenefit,
      socialPlatform: '小红书',
    }))
    navigate('/brand-assets')
  }

  function renderCampaignTemplate() {
    if (campaignRole === 'brand') {
      return (
        <p className="template-paragraph">
          我是{' '}
          <InlineField
            value={campaignBrandForm.brandName}
            placeholder="品牌名称"
            onChange={(value) => handleCampaignFieldChange('brandName', value)}
          />{' '}
          品牌方的营销小伙伴，这次活动的主推产品是{' '}
          <InlineField
            value={campaignBrandForm.productName}
            placeholder="产品全称、价格、规格"
            onChange={(value) => handleCampaignFieldChange('productName', value)}
          />{' '}
          ，属于{' '}
          <InlineField
            value={campaignBrandForm.category}
            placeholder="品类"
            onChange={(value) => handleCampaignFieldChange('category', value)}
          />{' '}
          品类，目标用户是{' '}
          <InlineField
            value={campaignBrandForm.audience}
            placeholder="目标用户"
            onChange={(value) => handleCampaignFieldChange('audience', value)}
          />{' '}
          ，活动核心目标是{' '}
          <InlineField
            value={campaignBrandForm.goal}
            placeholder="提升曝光 / 促进转化 / 拉新"
            onChange={(value) => handleCampaignFieldChange('goal', value)}
          />{' '}
          ，节点档期是{' '}
          <InlineField
            value={campaignBrandForm.timing}
            placeholder="618 / 母亲节 / 开学季"
            onChange={(value) => handleCampaignFieldChange('timing', value)}
          />{' '}
          ，活动形式偏向{' '}
          <InlineField
            value={campaignBrandForm.formatPreference}
            placeholder="线上内容种草 / 直播 / 线下快闪"
            onChange={(value) => handleCampaignFieldChange('formatPreference', value)}
          />{' '}
          ，这次活动能动用的预算是{' '}
          <InlineField
            value={campaignBrandForm.budget}
            placeholder="预算"
            onChange={(value) => handleCampaignFieldChange('budget', value)}
          />{' '}
          元，可配合的资源包括{' '}
          <InlineField
            value={campaignBrandForm.resources}
            placeholder="可用资源"
            onChange={(value) => handleCampaignFieldChange('resources', value)}
          />{' '}
          ，最希望从平台方获得的是{' '}
          <InlineField
            value={campaignBrandForm.support}
            placeholder="平台支持"
            onChange={(value) => handleCampaignFieldChange('support', value)}
          />{' '}
          。
        </p>
      )
    }

    return (
      <p className="template-paragraph">
        我是{' '}
        <InlineField
          value={campaignPlatformForm.platformName}
          placeholder="平台名称"
          onChange={(value) => handleCampaignFieldChange('platformName', value)}
        />{' '}
        平台方的营销小伙伴，平台的核心用户画像是{' '}
        <InlineField
          value={campaignPlatformForm.audienceProfile}
          placeholder="核心用户画像"
          onChange={(value) => handleCampaignFieldChange('audienceProfile', value)}
        />{' '}
        ，这次活动的主题方向是{' '}
        <InlineField
          value={campaignPlatformForm.themeDirection}
          placeholder="活动主题方向"
          onChange={(value) => handleCampaignFieldChange('themeDirection', value)}
        />{' '}
        ，核心目标是{' '}
        <InlineField
          value={campaignPlatformForm.goal}
          placeholder="招商 GMV / 品牌声量 / 用户增长"
          onChange={(value) => handleCampaignFieldChange('goal', value)}
        />{' '}
        ，节点档期是{' '}
        <InlineField
          value={campaignPlatformForm.timing}
          placeholder="节点档期"
          onChange={(value) => handleCampaignFieldChange('timing', value)}
        />{' '}
        ，招募的品牌方向是{' '}
        <InlineField
          value={campaignPlatformForm.targetBrands}
          placeholder="品牌方向"
          onChange={(value) => handleCampaignFieldChange('targetBrands', value)}
        />{' '}
        ，能为品牌方提供的资源包括{' '}
        <InlineField
          value={campaignPlatformForm.resources}
          placeholder="平台资源"
          onChange={(value) => handleCampaignFieldChange('resources', value)}
        />{' '}
        ，预算支持范围是{' '}
        <InlineField
          value={campaignPlatformForm.budgetSupport}
          placeholder="预算支持范围"
          onChange={(value) => handleCampaignFieldChange('budgetSupport', value)}
        />{' '}
        元，品牌方需要满足的合作条件是{' '}
        <InlineField
          value={campaignPlatformForm.conditions}
          placeholder="合作条件"
          onChange={(value) => handleCampaignFieldChange('conditions', value)}
        />{' '}
        。
      </p>
    )
  }

  return (
    <main className="page-shell single-workshop-shell">
      <section className="single-workshop-main">
        <div className="workshop-grid">
          <div className="workshop-config">
            <div className="page-title-block section-heading section-heading--compact">
              <h1>创意工作坊</h1>
              <p>通过填空式 Prompt，快速整理品牌或平台的节点策略与执行动作。</p>
            </div>

            <div className="tab-row">
              <button
                className={`soft-tab${campaignRole === 'brand' ? ' soft-tab--active' : ''}`}
                type="button"
                onClick={() => setCampaignRole('brand')}
              >
                品牌方
              </button>
              <button
                className={`soft-tab${campaignRole === 'platform' ? ' soft-tab--active' : ''}`}
                type="button"
                onClick={() => setCampaignRole('platform')}
              >
                平台方
              </button>
            </div>

            <div className="template-card">{renderCampaignTemplate()}</div>

            <div className="workshop-actions">
              <button
                className="generate-button"
                type="button"
                onClick={handleGenerateCampaign}
                disabled={campaignLoading}
              >
                {campaignLoading ? '生成中...' : '生成策略方案'}
              </button>
            </div>
          </div>

          <div className="workshop-output">
            {campaignError ? <div className="empty-state">{campaignError}</div> : null}
            {!campaignError && !campaignOutput ? (
              <div className="empty-state">
                {campaignLoading ? '正在调用 Agent 2 生成策略方案...' : '填写左侧信息，开始生成策略方案'}
              </div>
            ) : null}
            {campaignOutput ? (
              <div className="article-output">
                <header className="article-output__header">
                  <h2>{campaignOutput.title}</h2>
                  <p>{campaignOutput.intro}</p>
                </header>

                <section className="campaign-summary-card">
                  <div className="campaign-summary-card__block">
                    <span className="campaign-summary-card__label">一句话策略结论</span>
                    <p>{campaignSummary.conclusion}</p>
                  </div>

                  <div className="campaign-summary-card__grid">
                    <div>
                      <span className="campaign-summary-card__label">3 个核心机会</span>
                      <ul>
                        {campaignSummary.opportunities.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <span className="campaign-summary-card__label">3 个优先动作</span>
                      <ul>
                        {campaignSummary.priorities.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </section>

                <div className="campaign-section-tabs" role="tablist" aria-label="策略模块导航">
                  {campaignSections.map((section, index) => (
                    <button
                      key={section.title}
                      className={`campaign-section-tab${index === selectedCampaignSection ? ' campaign-section-tab--active' : ''}`}
                      type="button"
                      onClick={() => setSelectedCampaignSection(index)}
                    >
                      {section.title.replace(/^\d+[.、]\s*/, '')}
                    </button>
                  ))}
                </div>

                {activeCampaignSection ? (
                  <div className="article-output__body article-output__body--single">
                    <section className="article-section article-section--focused">
                      <h3>{activeCampaignSection.title}</h3>
                      {activeCampaignSection.markdown ? (
                        <div className="article-markdown">
                          <ReactMarkdown>{activeCampaignSection.markdown}</ReactMarkdown>
                        </div>
                      ) : (
                        activeCampaignSection.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)
                      )}
                    </section>
                  </div>
                ) : null}

                <div className="refine-box">
                  <label className="refine-box__label" htmlFor="campaign-adjustment">
                    对这份方案有什么想调整的？
                  </label>
                  <div className="refine-box__controls">
                    <input
                      id="campaign-adjustment"
                      className="refine-box__input"
                      value={campaignAdjustment}
                      placeholder="例如：更偏平台招商口径、再强化预算分配"
                      onChange={(event) => setCampaignAdjustment(event.target.value)}
                    />
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={handleCampaignAdjustmentSubmit}
                    >
                      提交
                    </button>
                  </div>
                  {campaignAdjustmentNote ? (
                    <p className="refine-box__note">已记录微调方向：{campaignAdjustmentNote}</p>
                  ) : null}
                </div>

                <div className="output-footer output-footer--stacked">
                  <button className="generate-button" type="button" onClick={handleGenerateCampaign}>
                    重新生成
                  </button>
                  <button className="secondary-button" type="button" onClick={handleExportCampaignMarkdown}>
                    导出完整方案
                  </button>
                  <button className="secondary-button" type="button" onClick={handleCarryToBrandAssets}>
                    带入品牌素材库
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    </main>
  )
}

function BrandAssetsPage({
  brandAssetTaskType,
  setBrandAssetTaskType,
  brandAssetForm,
  setBrandAssetForm,
  brandAssetUploads,
  setBrandAssetUploads,
  productImageDataUrl,
  setProductImageDataUrl,
  referenceImageDataUrl,
  setReferenceImageDataUrl,
  brandAssetBrief,
  setBrandAssetBrief,
  brandAssetBriefLoading,
  setBrandAssetBriefLoading,
  brandAssetBriefError,
  setBrandAssetBriefError,
  generatedImage,
  setGeneratedImage,
  generatedImageUrl,
  setGeneratedImageUrl,
  imageLoading,
  setImageLoading,
  imageError,
  setImageError,
}) {
  function handleFieldChange(field, value) {
    setBrandAssetForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  async function handleUpload(type, file) {
    if (!file) {
      return
    }

    try {
      const dataUrl = await readFileAsDataUrl(file)
      setImageError('')
      setGeneratedImage(null)
      setGeneratedImageUrl('')
      setBrandAssetUploads((current) => ({
        ...current,
        [type]: file.name,
      }))

      if (type === 'productImage') {
        setProductImageDataUrl(dataUrl)
        return
      }

      setReferenceImageDataUrl(dataUrl)
    } catch (error) {
      setImageError(error instanceof Error ? error.message : '图片读取失败，请重新上传')
    }
  }

  async function handleGenerateBrief() {
    setBrandAssetBriefLoading(true)
    setBrandAssetBriefError('')
    setImageError('')
    setGeneratedImage(null)
    setGeneratedImageUrl('')

    try {
      const result = await generateBrandAssetBrief({
        task_type: brandAssetTaskType,
        prompt: buildBrandAssetPrompt(brandAssetTaskType, brandAssetForm),
        context: buildBrandAssetContext(brandAssetTaskType, brandAssetForm, brandAssetUploads),
      })
      setBrandAssetBrief(result)
    } catch (error) {
      setBrandAssetBrief(null)
      setBrandAssetBriefError(error instanceof Error ? error.message : '生成 brief 失败，请稍后重试')
    } finally {
      setBrandAssetBriefLoading(false)
    }
  }

  async function handleGenerateImage() {
    if (!brandAssetBrief?.imagePrompt) {
      return
    }

    if (!productImageDataUrl) {
      setImageError('请先上传产品图，避免模型凭空生成错误产品。')
      return
    }

    setImageLoading(true)
    setImageError(referenceImageDataUrl ? '' : '未上传参考风格图，将仅根据 prompt 生成风格。')

    try {
      const data = await generateImage({
        prompt: brandAssetBrief.imagePrompt,
        asset_type: brandAssetTaskType,
        product_image: productImageDataUrl,
        reference_image: referenceImageDataUrl,
        product_image_name: brandAssetUploads.productImage,
        reference_image_name: brandAssetUploads.styleImage,
        headline: brandAssetForm.socialTitle,
        promotion_text: brandAssetForm.promotionText,
        platform_text: brandAssetForm.socialPlatform,
        visual_style: brandAssetForm.visualStyle,
        add_text_layer: brandAssetForm.addTextLayer,
      })
      const imageSrc = data.image_url
        ? data.image_url
        : data.image_base64
          ? `data:image/png;base64,${data.image_base64}`
          : ''
      setGeneratedImage(data)
      if (imageSrc) {
        setGeneratedImageUrl(imageSrc)
      } else {
        setImageError('图片已生成，但未返回可预览图片。')
      }
    } catch (error) {
      setGeneratedImage(null)
      setGeneratedImageUrl('')
      setImageError(error instanceof Error ? error.message : '生成图片失败，请稍后重试')
    } finally {
      setImageLoading(false)
    }
  }

  function handleDownloadBrief() {
    if (!brandAssetBrief) {
      return
    }

    const content = [
      `标题：${brandAssetBrief.title}`,
      '',
      '视觉 Brief：',
      brandAssetBrief.brief,
      '',
      'Image Prompt：',
      brandAssetBrief.imagePrompt,
      '',
      '优化建议：',
      ...brandAssetBrief.suggestions.map((item) => `- ${item}`),
    ].join('\n')

    downloadText('adamarketing-brand-assets-brief.txt', content)
  }

  function renderTemplate() {
    if (brandAssetTaskType === 'kv') {
      return (
        <p className="template-paragraph">
          这次要做一张品牌主视觉（3:4），产品全称是{' '}
          <InlineField
            value={brandAssetForm.kvProductName}
            placeholder="产品全称"
            onChange={(value) => handleFieldChange('kvProductName', value)}
          />{' '}
          ，品牌 Slogan 是{' '}
          <InlineField
            value={brandAssetForm.kvSlogan}
            placeholder="品牌 Slogan"
            onChange={(value) => handleFieldChange('kvSlogan', value)}
          />{' '}
          ，主卖点是{' '}
          <InlineField
            value={brandAssetForm.kvSellingPoint}
            placeholder="主卖点"
            onChange={(value) => handleFieldChange('kvSellingPoint', value)}
          />{' '}
          。
        </p>
      )
    }

    if (brandAssetTaskType === 'detail') {
      return (
        <p className="template-paragraph">
          这次要做一张电商详情页主图（3:4），产品是{' '}
          <InlineField
            value={brandAssetForm.detailProductName}
            placeholder="产品名称"
            onChange={(value) => handleFieldChange('detailProductName', value)}
          />{' '}
          ，三大卖点是{' '}
          <InlineField
            value={brandAssetForm.detailSellingPoint1}
            placeholder="卖点一"
            onChange={(value) => handleFieldChange('detailSellingPoint1', value)}
          />{' '}
          、
          <InlineField
            value={brandAssetForm.detailSellingPoint2}
            placeholder="卖点二"
            onChange={(value) => handleFieldChange('detailSellingPoint2', value)}
          />{' '}
          、
          <InlineField
            value={brandAssetForm.detailSellingPoint3}
            placeholder="卖点三"
            onChange={(value) => handleFieldChange('detailSellingPoint3', value)}
          />{' '}
          ，发布平台是{' '}
          <InlineField
            value={brandAssetForm.detailPlatform}
            placeholder="平台"
            onChange={(value) => handleFieldChange('detailPlatform', value)}
          />{' '}
          。
        </p>
      )
    }

    return (
      <p className="template-paragraph">
        这次要做一张社媒海报，主标题是{' '}
        <InlineField
          value={brandAssetForm.socialTitle}
          placeholder="主标题"
          onChange={(value) => handleFieldChange('socialTitle', value)}
        />{' '}
        ，促销信息是{' '}
        <InlineField
          value={brandAssetForm.promotionText}
          placeholder="促销信息"
          onChange={(value) => handleFieldChange('promotionText', value)}
        />{' '}
        ，利益点是{' '}
        <InlineField
          value={brandAssetForm.socialBenefit}
          placeholder="利益点"
          onChange={(value) => handleFieldChange('socialBenefit', value)}
        />{' '}
        ，平台 / 场景是{' '}
        <InlineField
          value={brandAssetForm.socialPlatform}
          placeholder="平台 / 场景"
          onChange={(value) => handleFieldChange('socialPlatform', value)}
        />{' '}
        ，画面风格是{' '}
        <InlineField
          value={brandAssetForm.visualStyle}
          placeholder="画面风格"
          onChange={(value) => handleFieldChange('visualStyle', value)}
        />{' '}
        。{' '}
        <label className="inline-checkbox">
          <input
            type="checkbox"
            checked={brandAssetForm.addTextLayer}
            onChange={(event) => handleFieldChange('addTextLayer', event.target.checked)}
          />
          添加文字层
        </label>
      </p>
    )
  }

  return (
    <main className="page-shell single-workshop-shell">
      <section className="single-workshop-main">
        <div className="workshop-grid">
          <div className="workshop-config">
            <div className="page-title-block section-heading section-heading--compact">
              <h1>品牌素材库</h1>
              <p>先生成视觉 brief / image prompt，再单独触发图片生成。</p>
            </div>

            <div className="tab-row tab-row--wrap">
              <button
                className={`soft-tab${brandAssetTaskType === 'kv' ? ' soft-tab--active' : ''}`}
                type="button"
                onClick={() => setBrandAssetTaskType('kv')}
              >
                KV 主视觉
              </button>
              <button
                className={`soft-tab${brandAssetTaskType === 'detail' ? ' soft-tab--active' : ''}`}
                type="button"
                onClick={() => setBrandAssetTaskType('detail')}
              >
                产品详情页
              </button>
              <button
                className={`soft-tab${brandAssetTaskType === 'social' ? ' soft-tab--active' : ''}`}
                type="button"
                onClick={() => setBrandAssetTaskType('social')}
              >
                社交媒体海报
              </button>
            </div>

            <div className="template-card">{renderTemplate()}</div>

            <div className="upload-grid">
              <label className="upload-tile">
                <input
                  type="file"
                  hidden
                  onChange={(event) => handleUpload('productImage', event.target.files?.[0])}
                />
                <span className="upload-tile__title">产品图</span>
                <span className="upload-tile__meta">{brandAssetUploads.productImage || '点击上传素材'}</span>
              </label>
              <label className="upload-tile">
                <input
                  type="file"
                  hidden
                  onChange={(event) => handleUpload('styleImage', event.target.files?.[0])}
                />
                <span className="upload-tile__title">参考风格图</span>
                <span className="upload-tile__meta">{brandAssetUploads.styleImage || '点击上传参考'}</span>
              </label>
            </div>

            <div className="brand-assets-actions">
              <button className="generate-button" type="button" onClick={handleGenerateBrief} disabled={brandAssetBriefLoading}>
                {brandAssetBriefLoading ? '生成中...' : '第一步：生成视觉 brief'}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={handleGenerateImage}
                disabled={!brandAssetBrief?.imagePrompt || imageLoading}
              >
                {imageLoading ? '生成中...' : '第二步：生成并合成海报'}
              </button>
              <p className="brand-assets-action-note">AI 生成背景，系统保留原始产品图，并用可控文字层生成标题和促销信息，避免包装与中文变形。</p>
              <p className="brand-assets-action-note">当前版本会保留原始产品图，若产品图为白底，建议上传透明底 PNG 以获得最佳效果。</p>
            </div>
          </div>

          <div className="workshop-output">
            {brandAssetBriefError ? <div className="empty-state empty-state--panel">{brandAssetBriefError}</div> : null}
            {!brandAssetBriefError && !brandAssetBrief ? (
              <div className="empty-state empty-state--panel">
                {brandAssetBriefLoading ? '正在生成视觉 brief...' : '先填写左侧信息，开始生成视觉 brief 与 image prompt'}
              </div>
            ) : null}

            {brandAssetBrief ? (
              <div className="poster-result">
                <div className="poster-result__content">
                  <div className="poster-preview-card">
                    <div className="poster-preview-card__stage">
                      {generatedImageUrl ? (
                        <div className="campaign-poster-preview">
                          <img
                            src={generatedImageUrl}
                            alt="Generated brand asset"
                            className="poster-preview-card__image"
                          />
                          {brandAssetForm.addTextLayer ? (
                            <div className="campaign-poster-preview__text-layer" aria-hidden="true">
                              <div className="campaign-poster-preview__platform">{brandAssetForm.socialPlatform}</div>
                              <h3>{brandAssetForm.socialTitle}</h3>
                              <div className="campaign-poster-preview__footer">
                                <span>{brandAssetForm.socialBenefit}</span>
                                <strong>{brandAssetForm.promotionText}</strong>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <div className="poster-preview-card__poster">
                          <span>{brandAssetBrief.title}</span>
                        </div>
                      )}
                    </div>
                    <button className="secondary-button" type="button" onClick={handleDownloadBrief}>
                      下载视觉 brief
                    </button>
                    {imageError ? <div className="empty-state empty-state--panel">{imageError}</div> : null}
                    {generatedImage?.message ? <p className="brand-assets-note">{generatedImage.message}</p> : null}
                  </div>

                  <div className="poster-doc-card">
                    <h2>{brandAssetBrief.title}</h2>
                    <div className="poster-doc-card__group">
                      <span className="output-label">视觉 Brief</span>
                      <p>{brandAssetBrief.brief}</p>
                    </div>
                    <div className="poster-doc-card__group">
                      <span className="output-label">Image Prompt</span>
                      <p className="brand-assets-prompt">{brandAssetBrief.imagePrompt}</p>
                    </div>
                    <div className="poster-doc-card__group">
                      <span className="output-label">优化建议</span>
                      <ul>
                        {brandAssetBrief.suggestions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    </main>
  )
}

function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedId, setSelectedId] = useState(null)
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [promptExpanded, setPromptExpanded] = useState(false)
  const [briefResult, setBriefResult] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState('')
  const [hotspots, setHotspots] = useState(todayHotspots)
  const [hotspotsSource, setHotspotsSource] = useState('simulated')
  const [copied, setCopied] = useState(false)
  const [campaignRole, setCampaignRole] = useState('brand')
  const [campaignBrandForm, setCampaignBrandForm] = useState(defaultCampaignBrandForm)
  const [campaignPlatformForm, setCampaignPlatformForm] = useState(defaultCampaignPlatformForm)
  const [campaignOutput, setCampaignOutput] = useState(null)
  const [campaignLoading, setCampaignLoading] = useState(false)
  const [campaignError, setCampaignError] = useState('')
  const [campaignAdjustment, setCampaignAdjustment] = useState('')
  const [campaignAdjustmentNote, setCampaignAdjustmentNote] = useState('')
  const [brandAssetTaskType, setBrandAssetTaskType] = useState('kv')
  const [brandAssetForm, setBrandAssetForm] = useState(defaultBrandAssetForm)
  const [brandAssetUploads, setBrandAssetUploads] = useState({
    productImage: '',
    styleImage: '',
  })
  const [productImageDataUrl, setProductImageDataUrl] = useState('')
  const [referenceImageDataUrl, setReferenceImageDataUrl] = useState('')
  const [brandAssetBrief, setBrandAssetBrief] = useState(null)
  const [brandAssetBriefLoading, setBrandAssetBriefLoading] = useState(false)
  const [brandAssetBriefError, setBrandAssetBriefError] = useState('')
  const [generatedImage, setGeneratedImage] = useState(null)
  const [generatedImageUrl, setGeneratedImageUrl] = useState('')
  const [imageLoading, setImageLoading] = useState(false)
  const [imageError, setImageError] = useState('')

  const navItems = [
    { label: '热点速递站', path: '/' },
    { label: '创意工作坊', path: '/workshop' },
    { label: '品牌素材库', path: '/brand-assets' },
  ]

  function isActiveNav(path) {
    return location.pathname === path
  }

  useEffect(() => {
    let active = true

    fetchTodayHotspots()
      .then((data) => {
        if (!active) {
          return
        }

        const normalizedHotspots = Array.isArray(data?.hotspots)
          ? data.hotspots.map((item) => ({
              ...item,
              platformMark: mapPlatformMark(item.platform),
            }))
          : []

        if (normalizedHotspots.length) {
          setHotspots(normalizedHotspots)
          setHotspotsSource(data?.source || 'simulated')
          if (!normalizedHotspots.some((item) => item.id === selectedId)) {
            setSelectedId(null)
          }
        }
      })
      .catch(() => {
        if (!active) {
          return
        }
        setHotspots(todayHotspots)
        setHotspotsSource('simulated')
      })

    return () => {
      active = false
    }
  }, [selectedId])

  return (
    <div className="adamarketing-app">
      <header className="topbar">
        <Link className="brand-button" to="/">
          AdaMarketing
        </Link>

        <div className="topbar__meta">
          <span className="topbar__date">{currentNode.date}</span>
        </div>

        <nav className="topbar__nav" aria-label="主导航">
          {navItems.map((item) => (
            <button
              key={item.path}
              className={`nav-pill${isActiveNav(item.path) ? ' nav-pill--active' : ''}`}
              type="button"
              onClick={() => navigate(item.path)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <Routes>
        <Route
          path="/"
          element={
            <BriefPage
              selectedId={selectedId}
              setSelectedId={setSelectedId}
              prompt={prompt}
              setPrompt={setPrompt}
              promptExpanded={promptExpanded}
              setPromptExpanded={setPromptExpanded}
              briefResult={briefResult}
              setBriefResult={setBriefResult}
              briefLoading={briefLoading}
              setBriefLoading={setBriefLoading}
              briefError={briefError}
              setBriefError={setBriefError}
              hotspots={hotspots}
              copied={copied}
              setCopied={setCopied}
            />
          }
        />
        <Route
          path="/workshop"
          element={
            <WorkshopPage
              campaignRole={campaignRole}
              setCampaignRole={setCampaignRole}
              campaignBrandForm={campaignBrandForm}
              setCampaignBrandForm={setCampaignBrandForm}
              campaignPlatformForm={campaignPlatformForm}
              setCampaignPlatformForm={setCampaignPlatformForm}
              campaignOutput={campaignOutput}
              setCampaignOutput={setCampaignOutput}
              campaignLoading={campaignLoading}
              setCampaignLoading={setCampaignLoading}
              campaignError={campaignError}
              setCampaignError={setCampaignError}
              campaignAdjustment={campaignAdjustment}
              setCampaignAdjustment={setCampaignAdjustment}
              campaignAdjustmentNote={campaignAdjustmentNote}
              setCampaignAdjustmentNote={setCampaignAdjustmentNote}
              setBrandAssetTaskType={setBrandAssetTaskType}
              setBrandAssetForm={setBrandAssetForm}
            />
          }
        />
        <Route
          path="/brand-assets"
          element={
            <BrandAssetsPage
              brandAssetTaskType={brandAssetTaskType}
              setBrandAssetTaskType={setBrandAssetTaskType}
              brandAssetForm={brandAssetForm}
              setBrandAssetForm={setBrandAssetForm}
              brandAssetUploads={brandAssetUploads}
              setBrandAssetUploads={setBrandAssetUploads}
              productImageDataUrl={productImageDataUrl}
              setProductImageDataUrl={setProductImageDataUrl}
              referenceImageDataUrl={referenceImageDataUrl}
              setReferenceImageDataUrl={setReferenceImageDataUrl}
              brandAssetBrief={brandAssetBrief}
              setBrandAssetBrief={setBrandAssetBrief}
              brandAssetBriefLoading={brandAssetBriefLoading}
              setBrandAssetBriefLoading={setBrandAssetBriefLoading}
              brandAssetBriefError={brandAssetBriefError}
              setBrandAssetBriefError={setBrandAssetBriefError}
              generatedImage={generatedImage}
              setGeneratedImage={setGeneratedImage}
              generatedImageUrl={generatedImageUrl}
              setGeneratedImageUrl={setGeneratedImageUrl}
              imageLoading={imageLoading}
              setImageLoading={setImageLoading}
              imageError={imageError}
              setImageError={setImageError}
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return <AppShell />
}
