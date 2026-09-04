const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function splitMarkdownIntoSections(markdown, fallbackTitle = '方案正文') {
  const source = String(markdown ?? '').replace(/\r\n/g, '\n').trim()

  if (!source) {
    return []
  }

  const withoutTopHeading = source.replace(/^#\s+.+?\n+/, '').trim()
  const h2Pattern = /^##\s+(.+)$/gm
  const matches = [...withoutTopHeading.matchAll(h2Pattern)]

  if (!matches.length) {
    return [
      {
        title: fallbackTitle,
        markdown: withoutTopHeading,
        paragraphs: [withoutTopHeading],
      },
    ]
  }

  const sections = []
  const leadIn = withoutTopHeading.slice(0, matches[0].index).trim()
  if (leadIn) {
    sections.push({
      title: fallbackTitle,
      markdown: leadIn,
      paragraphs: [leadIn],
    })
  }

  matches.forEach((match, index) => {
    const title = match[1].trim()
    const bodyStart = match.index + match[0].length
    const bodyEnd = index + 1 < matches.length ? matches[index + 1].index : withoutTopHeading.length
    const body = withoutTopHeading.slice(bodyStart, bodyEnd).trim()

    sections.push({
      title,
      markdown: body,
      paragraphs: body ? [body] : [],
    })
  })

  return sections.filter((section) => section.markdown.trim() || section.paragraphs.length)
}

function normalizeSection(section) {
  if (!section || typeof section !== 'object') {
    return null
  }

  const title = section.title ?? section.heading ?? '原始输出'
  const rawText = section.markdown ?? section.content ?? section.paragraphs ?? ''
  const markdownText = Array.isArray(rawText)
    ? rawText.map(String).map((item) => item.trim()).filter(Boolean).join('\n\n')
    : String(rawText ?? '').trim()
  const paragraphsSource = section.paragraphs ?? section.content ?? markdownText
  const paragraphs = Array.isArray(paragraphsSource)
    ? paragraphsSource.map(String).map((item) => item.trim()).filter(Boolean)
    : [String(paragraphsSource ?? '').trim()].filter(Boolean)

  if (!markdownText && !paragraphs.length) {
    return null
  }

  return {
    title,
    markdown: markdownText,
    paragraphs: paragraphs.length ? paragraphs : [markdownText],
  }
}

function normalizeHotspotWorkbench(output) {
  if (!output || typeof output !== 'object') {
    return {
      summary: '',
      background: '',
      emotion: '',
      categoryOpportunity: '',
      brandAngle: '',
      contentTopics: [],
      actionSteps: [],
      riskAlert: '',
    }
  }

  return {
    summary: String(output.summary ?? '').trim(),
    background: String(output.background ?? '').trim(),
    emotion: String(output.emotion ?? '').trim(),
    categoryOpportunity: String(output.category_opportunity ?? '').trim(),
    brandAngle: String(output.brand_angle ?? '').trim(),
    contentTopics: Array.isArray(output.content_topics)
      ? output.content_topics.map(String).map((item) => item.trim()).filter(Boolean)
      : [],
    actionSteps: Array.isArray(output.action_steps)
      ? output.action_steps.map(String).map((item) => item.trim()).filter(Boolean)
      : [],
    riskAlert: String(output.risk_alert ?? '').trim(),
  }
}

function normalizeBrandAssetBrief(output) {
  if (!output || typeof output !== 'object') {
    return {
      taskType: 'social',
      title: '视觉 brief',
      brief: '',
      imagePrompt: '',
      suggestions: [],
    }
  }

  return {
    taskType: String(output.task_type ?? 'social'),
    title: String(output.title ?? '视觉 brief').trim(),
    brief: String(output.brief ?? '').trim(),
    imagePrompt: String(output.image_prompt ?? '').trim(),
    suggestions: Array.isArray(output.suggestions)
      ? output.suggestions.map(String).map((item) => item.trim()).filter(Boolean)
      : [],
  }
}

function normalizeImageOutput(output) {
  if (!output || typeof output !== 'object') {
    return {
      imageUrl: '',
      imageBase64: '',
      image_url: '',
      image_base64: '',
      status: 'ready',
      message: '',
    }
  }

  const imageUrl = String(output.image_url ?? '').trim()
  const imageBase64 = String(output.image_base64 ?? '').trim()

  return {
    imageUrl,
    imageBase64,
    image_url: imageUrl,
    image_base64: imageBase64,
    status: String(output.status ?? 'ready').trim(),
    message: String(output.message ?? '').trim(),
  }
}

function normalizeAgentOutput(output) {
  if (!output || typeof output !== 'object') {
    return {
      title: '策略方案生成结果',
      intro: '后端返回内容格式异常，已使用兜底展示。',
      sections: [
        {
          title: '原始输出',
          markdown: typeof output === 'string' ? output : '',
          paragraphs: [typeof output === 'string' ? output : '没有可展示的内容。'],
        },
      ],
    }
  }

  if ('background' in output || 'emotion' in output || 'brand_angle' in output) {
    return normalizeHotspotWorkbench(output)
  }

  if ('image_prompt' in output || 'task_type' in output) {
    return normalizeBrandAssetBrief(output)
  }

  if ('image_url' in output || 'status' in output) {
    return normalizeImageOutput(output)
  }

  const normalizedSections = Array.isArray(output.sections)
    ? output.sections.map(normalizeSection).filter(Boolean)
    : []

  const expandedSections = normalizedSections.flatMap((section) => {
    if (!section.markdown || !/^#{1,2}\s+/m.test(section.markdown)) {
      return [section]
    }

    const splitSections = splitMarkdownIntoSections(section.markdown, section.title)
    return splitSections.length ? splitSections : [section]
  })

  return {
    ...output,
    title: output.title ?? '策略方案生成结果',
    intro: output.intro ?? output.summary ?? '模型已返回结果。',
    sections: expandedSections.length
      ? expandedSections
      : [
          {
            title: '原始输出',
            markdown: '',
            paragraphs: ['没有可展示的内容。'],
          },
        ],
  }
}

async function parseResponse(response) {
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const message = data?.detail || data?.error || 'Request failed'
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }

  if (data?.output !== undefined) {
    return {
      ...data,
      output: normalizeAgentOutput(data.output),
    }
  }

  return normalizeAgentOutput(data)
}

export async function fetchAgents() {
  const response = await fetch(`${API_BASE_URL}/api/agents`)
  return parseResponse(response)
}

export async function fetchTodayHotspots() {
  const response = await fetch(`${API_BASE_URL}/api/hotspots/today`)
  return parseResponse(response)
}

export async function refreshTodayHotspots() {
  const response = await fetch(`${API_BASE_URL}/api/hotspots/refresh`, {
    method: 'POST',
  })
  return parseResponse(response)
}

export async function runAgent(agentName, payload) {
  const response = await fetch(`${API_BASE_URL}/api/agents/${agentName}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function generateBrandAssetBrief(payload) {
  const response = await fetch(`${API_BASE_URL}/api/agents/agent_3/brief`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}

export async function generateImage(payload) {
  const response = await fetch(`${API_BASE_URL}/api/images/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return parseResponse(response)
}
