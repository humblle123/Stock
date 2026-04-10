import { useState } from 'react'
import type { StockSignal, StrategyMeta } from '../types'
import StockCard from './StockCard'

interface OHLC { o: number; h: number; l: number; c: number }

interface Props {
  strategy: StrategyMeta
  signals: StockSignal[]
  prices: Record<string, number>
  thumbs: Record<string, OHLC[]>
}

type SortKey = 'change_pct' | 'RPS50' | 'RPS120' | 'RPS250'

export default function StrategyColumn({ strategy, signals, prices, thumbs }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('change_pct')
  const [collapsed, setCollapsed] = useState(false)

  const sorted = [...signals].sort((a, b) => {
    const av = a.metadata[sortKey] ?? -999
    const bv = b.metadata[sortKey] ?? -999
    return bv - av
  })

  return (
    <div className="strategy-col">
      <div className="col-header">
        <div className="col-title-row">
          <button
            className="col-collapse-btn"
            onClick={() => setCollapsed(c => !c)}
            aria-label={collapsed ? '展开' : '折叠'}
          >
            <span className={`col-arrow ${collapsed ? 'collapsed' : ''}`}>▼</span>
          </button>
          <span className="col-tag" style={{ color: strategy.color, background: strategy.bg }}>
            {strategy.tag}
          </span>
          <span className="col-name">{strategy.label}</span>
          <span className="col-count">{signals.length}</span>
        </div>
        {!collapsed && (
          <div className="col-sort">
            <span className="sort-label">排序</span>
            <select value={sortKey} onChange={e => setSortKey(e.target.value as SortKey)} className="sort-select">
              <option value="change_pct">涨跌幅</option>
              <option value="RPS50">RPS50</option>
              <option value="RPS120">RPS120</option>
              <option value="RPS250">RPS250</option>
            </select>
          </div>
        )}
      </div>
      {!collapsed && (
        <div className="col-list">
          {sorted.map(s => (
            <StockCard
              key={s.code}
              signal={s}
              strategy={strategy}
              lastPrice={prices[s.code]}
              thumb={thumbs[s.code]}
            />
          ))}
          {signals.length === 0 && <div className="col-empty">暂无信号</div>}
        </div>
      )}
    </div>
  )
}
