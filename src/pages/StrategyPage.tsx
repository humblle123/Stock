import { useEffect, useState, useMemo, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchReport, type ReportResponse, type StockSignal } from '../api'
import Header from '../components/Header'
import ThreeLineRedTable from '../components/ThreeLineRedTable'
import KD1Table from '../components/KD1Table'

// ── 常量 ────────────────────────────────────────────────────────────────────
type SortKey = 'change_pct' | 'RPS50' | 'RPS120' | 'RPS250' | 'price'
type ViewMode = 'sig' | 'rep'

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'change_pct', label: '涨跌幅' },
  { key: 'price',      label: '现价'   },
  { key: 'RPS50',      label: 'RPS50'  },
  { key: 'RPS120',     label: 'RPS120' },
  { key: 'RPS250',     label: 'RPS250' },
]

// ── 工具函数 ───────────────────────────────────────────────────────────────
function rpsColor(v: number | undefined): string {
  if (v == null) return 'rgba(150,150,150,0.5)'
  if (v >= 93) return '#e53935'
  if (v >= 85) return '#ff6f00'
  if (v >= 70) return '#f9a825'
  return '#43a047'
}

function rpsGlow(v: number | undefined): string {
  if (v == null || v < 90) return 'none'
  if (v >= 95) return '0 0 8px 2px rgba(229,57,49,0.55)'
  return '0 0 6px 1px rgba(255,111,0,0.45)'
}

function fmt(v: number | undefined, decimals = 2): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

function sortSignals(sig: StockSignal[], key: SortKey): StockSignal[] {
  return [...sig].sort((a, b) => {
    let av: number, bv: number
    if (key === 'price') {
      av = a.price ?? -1; bv = b.price ?? -1
    } else if (key === 'change_pct') {
      av = a.metadata.change_pct ?? -999; bv = b.metadata.change_pct ?? -999
    } else {
      av = (a.metadata as Record<string, number | undefined>)[key] ?? -999
      bv = (b.metadata as Record<string, number | undefined>)[key] ?? -999
    }
    return bv - av
  })
}

// ── 单只股票卡片 ───────────────────────────────────────────────────────────
function StockCard({ s, strategyKey }: { s: StockSignal; strategyKey: string }) {
  const navigate = useNavigate()
  const pct   = s.metadata.change_pct ?? s.up ?? 0
  const price = s.price
  const isUp  = pct >= 0

  return (
    <div
      className="sig-card"
      data-up={isUp}
      onClick={() => navigate(`/chart/${s.code}?s=${strategyKey}`)}
    >
      {/* 左侧：名称 + 价格 */}
      <div className="sig-left">
        <div className="sig-name">{s.name}</div>
        <div className="sig-code">{s.code}</div>
      </div>

      {/* 中间：涨跌 + 现价 */}
      <div className="sig-center">
        <div className="sig-pct" data-up={isUp}>
          {isUp ? '+' : ''}{fmt(pct)}%
        </div>
        {price != null && (
          <div className="sig-price">{price.toFixed(2)}</div>
        )}
      </div>

      {/* 右侧：RPS 指标 */}
      <div className="sig-indicators">
        {s.metadata.RPS50 != null && (
          <div
            className="ind-pill"
            style={{
              color:          rpsColor(s.metadata.RPS50),
              boxShadow:      rpsGlow(s.metadata.RPS50),
              borderColor:    rpsColor(s.metadata.RPS50) + '55',
            }}
          >
            <span className="ind-label">50</span>
            <b>{fmt(s.metadata.RPS50, 0)}</b>
          </div>
        )}
        {s.metadata.RPS120 != null && (
          <div
            className="ind-pill"
            style={{
              color:          rpsColor(s.metadata.RPS120),
              boxShadow:      rpsGlow(s.metadata.RPS120),
              borderColor:    rpsColor(s.metadata.RPS120) + '55',
            }}
          >
            <span className="ind-label">120</span>
            <b>{fmt(s.metadata.RPS120, 0)}</b>
          </div>
        )}
        {s.metadata.RPS250 != null && (
          <div
            className="ind-pill"
            style={{
              color:          rpsColor(s.metadata.RPS250),
              boxShadow:      rpsGlow(s.metadata.RPS250),
              borderColor:    rpsColor(s.metadata.RPS250) + '55',
            }}
          >
            <span className="ind-label">250</span>
            <b>{fmt(s.metadata.RPS250, 0)}</b>
          </div>
        )}
        {s.metadata.BKH && (
          <div className="ind-pill ind-bkh">{s.metadata.BKH}</div>
        )}
        {s.metadata.J != null && (
          <div className="ind-pill ind-j">
            <span className="ind-label">J</span>
            <b>{fmt(s.metadata.J, 0)}</b>
          </div>
        )}
      </div>
    </div>
  )
}

// ── 折叠卡片 ──────────────────────────────────────────────────────────────
interface SectionCardProps {
  title: string
  color: string
  bg: string
  count: number
  defaultOpen?: boolean
  strategyKey: string
  signals: StockSignal[]
  renderReport?: () => ReactNode
}

function SectionCard({
  title, color, bg, count, defaultOpen = false,
  strategyKey, signals, renderReport,
}: SectionCardProps) {
  const [open,     setOpen]    = useState(defaultOpen)
  const [view,    setView]    = useState<ViewMode>('sig')
  const [sortKey, setSortKey] = useState<SortKey>('change_pct')

  const sorted = useMemo(() => sortSignals(signals, sortKey), [signals, sortKey])

  return (
    <div className="section-card" data-open={open}>
      {/* 标题栏 */}
      <div className="sc-header" onClick={() => setOpen(o => !o)} role="button">
        <div className="sc-left">
          <div className="sc-tag" style={{ color, background: bg }}>
            {count > 0 ? count : '—'}
          </div>
          <span className="sc-title">{title}</span>
        </div>
        <div className="sc-right">
          <span className="sc-hint">{open ? '点击折叠' : '点击展开'}</span>
          <span className={`sc-arrow ${open ? 'open' : ''}`}>›</span>
        </div>
      </div>

      {/* 展开内容 */}
      {open && (
        <div className="sc-body">
          {/* 子 Tab */}
          <div className="sc-tabs">
            <button
              className={`sc-tab ${view === 'sig' ? 'active' : ''}`}
              style={view === 'sig' ? { borderBottomColor: color, color } : {}}
              onClick={() => setView('sig')}
            >
              信号列表
              {signals.length > 0 && <em>{signals.length}</em>}
            </button>
            <button
              className={`sc-tab ${view === 'rep' ? 'active' : ''}`}
              style={view === 'rep' ? { borderBottomColor: color, color } : {}}
              onClick={() => setView('rep')}
            >
              跟踪报表
            </button>
          </div>

          {view === 'sig' ? (
            <>
              {/* 排序 */}
              <div className="sc-sort">
                {SORT_OPTIONS.map(o => (
                  <button
                    key={o.key}
                    className={`sort-chip ${sortKey === o.key ? 'active' : ''}`}
                    style={sortKey === o.key ? {
                      background: color,
                      borderColor: color,
                      color: '#fff',
                    } : {}}
                    onClick={() => setSortKey(o.key)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>

              {/* 列表 */}
              <div className="sc-list">
                {sorted.length === 0 ? (
                  <div className="sc-empty">暂无信号</div>
                ) : (
                  sorted.map(s => (
                    <StockCard key={s.code} s={s} strategyKey={strategyKey} />
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="sc-report">
              {renderReport ? renderReport() : (
                <div className="sc-empty">暂无报表</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 策略页 ───────────────────────────────────────────────────────────────
export default function StrategyPage() {
  const { key } = useParams<{ key: string }>()

  const meta = key === 'bian'
    ? { title: '彼岸战法', color: '#e53935', bg: 'rgba(233,30,99,0.1)', tag: 'S3' }
    : { title: 'Z哥战法',  color: '#43a047', bg: 'rgba(67,160,71,0.1)',  tag: 'B1' }

  const [data,   setData]   = useState<ReportResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchReport()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [key])

  if (loading) {
    return (
      <div className="page-home">
        <Header />
        <div className="loading-screen">
          <div className="spinner" />
          <p>加载中…</p>
        </div>
      </div>
    )
  }

  const s3Signals   = (data?.signals ?? []).filter(s => s.section === 's3')
  const kd1Signals  = (data?.signals ?? []).filter(s => s.section === 'kd1')
  const techSignals = (data?.signals ?? []).filter(s => s.section === 'technical')

  return (
    <div className="page-home">
      <Header date={data?.date} />

      <div className="home-body">
        {/* 策略页大标题 */}
        <div className="strat-hero" style={{ borderLeftColor: meta.color }}>
          <div className="strat-hero-tag" style={{ color: meta.color, background: meta.bg }}>
            {meta.tag}
          </div>
          <span className="strat-hero-name">{meta.title}</span>
          <span className="strat-hero-date">{data?.date ?? ''}</span>
        </div>

        {key === 'bian' ? (
          <>
            <SectionCard
              title="RPS三线红"
              color="#e53935"
              bg="rgba(233,30,99,0.08)"
              count={s3Signals.length}
              defaultOpen={true}
              strategyKey="bian"
              signals={s3Signals}
              renderReport={() => <ThreeLineRedTable />}
            />
            <SectionCard
              title="KD1一线红"
              color="#ff8f00"
              bg="rgba(255,143,0,0.08)"
              count={kd1Signals.length}
              defaultOpen={false}
              strategyKey="bian"
              signals={kd1Signals}
              renderReport={() => <KD1Table />}
            />
          </>
        ) : (
          <SectionCard
            title="强势突破"
            color="#43a047"
            bg="rgba(67,160,71,0.08)"
            count={techSignals.length}
            defaultOpen={true}
            strategyKey="z"
            signals={techSignals}
          />
        )}
      </div>
    </div>
  )
}
