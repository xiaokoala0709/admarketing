export const NODE_THEME_MAP = {
  traditional_festival: {
    bg: '#FDECEA',
    text: '#C0392B',
    border: '#F5C0BB',
    icon: '节',
  },
  public_holiday: {
    bg: '#FEF0E6',
    text: '#C05A1F',
    border: '#F8CEAA',
    icon: '假',
  },
  solar_term: {
    bg: '#E8F5EF',
    text: '#1E7D52',
    border: '#A8DFC4',
    icon: '气',
  },
  ecommerce_node: {
    bg: '#FEF9E6',
    text: '#A07D10',
    border: '#F5DFA0',
    icon: '商',
  },
  international_festival: {
    bg: '#E8F2FB',
    text: '#1A5F9E',
    border: '#A8CEEE',
    icon: '国',
  },
  lifestyle_trend: {
    bg: '#F0EEE8',
    text: '#6B6860',
    border: '#E0DDD6',
    icon: '趋',
  },
}

export function getNodeTheme(nodeType) {
  return NODE_THEME_MAP[nodeType] || NODE_THEME_MAP.lifestyle_trend
}

export function mapPlatformMark(platform) {
  if (platform === '小红书') {
    return '红'
  }
  if (platform === '抖音') {
    return '抖'
  }
  if (platform === '微博') {
    return '微'
  }
  if (platform === '微信') {
    return '微'
  }
  if (platform === 'B站') {
    return 'B'
  }
  return '热'
}
