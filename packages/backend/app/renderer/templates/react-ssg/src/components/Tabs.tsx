import { useState } from 'react'
import type { CSSProperties } from 'react'

export interface TabItem {
  id: string
  label: string
  content?: string
}

export interface TabsProps {
  tabs?: TabItem[]
  defaultTabId?: string
  className?: string
  style?: CSSProperties
}

const Tabs = ({ tabs = [], defaultTabId, className, style }: TabsProps) => {
  const initialTab = defaultTabId || tabs[0]?.id
  const [activeTab, setActiveTab] = useState(initialTab)

  const active = tabs.find((tab) => tab.id === activeTab)

  return (
    <div className={['ic-card flex flex-col gap-3 p-4', className].filter(Boolean).join(' ')} style={style}>
      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={
              tab.id === activeTab
                ? 'rounded-full bg-slate-900 px-3 py-1 text-xs text-white'
                : 'rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600'
            }
          >
            {tab.label}
          </button>
        ))}
      </div>
      {active?.content && <p className="text-xs text-slate-500">{active.content}</p>}
    </div>
  )
}

export default Tabs
