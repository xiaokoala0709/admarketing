import { getNodeTheme } from './nodeThemes'

export default function NodePill({ nodeType, nodeLabel, className = '' }) {
  const theme = getNodeTheme(nodeType)

  return (
    <span
      className={`node-pill${className ? ` ${className}` : ''}`}
      style={{
        background: theme.bg,
        color: theme.text,
        borderColor: theme.border,
      }}
    >
      <span className="node-pill__icon" style={{ background: theme.text }}>
        {theme.icon}
      </span>
      <span>{nodeLabel}</span>
    </span>
  )
}
