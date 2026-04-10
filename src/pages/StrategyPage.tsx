import { useEffect, useState, useMemo, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchReport, type ReportResponse, type StockSignal } from '../api'
import Header from '../components/Header'
import ThreeLineRedTable from '../components/ThreeLineRedTable'
import KD1Table from '../components/KD1Table'

// ── 常量 ────────────────────────────────────────────────────────────────────
type SortKey = 'change_pct' | 'RPS50' | 'RPS120' | 'RPS250' | 'price'
type SortDir  = 'desc' | 'asc'
type ViewMode = 'sig' | 'rep'


// ── 工具函数 ───────────────────────────────────────────────────────────────
function rpsColor(v: number | undefined): string {
  if (v == null) return 'rgba(150,150,150,0.5)'
  if (v >= 93) return '#e53935'
  if (v >= 85) return '#ff6f00'
  if (v >= 70) return '#f9a825'
  return '#43a047'
}


function fmt(v: number | undefined, decimals = 2): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

function sortSignals(sig: StockSignal[], key: SortKey, dir: SortDir): StockSignal[] {
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
    return dir === 'desc' ? bv - av : av - bv
  })
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
  const navigate = useNavigate()
  const [open,     setOpen]    = useState(defaultOpen)
  const [view,    setView]    = useState<ViewMode>('sig')
  const [sortKey, setSortKey] = useState<SortKey>('change_pct')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const sorted = useMemo(() => sortSignals(signals, sortKey, sortDir), [signals, sortKey, sortDir])

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
              {/* 表格 */}
              <div className="sig-table-wrap">
                <table className="sig-table">
                  <thead>
                    <tr>
                      <th className="sortable" onClick={() => { setSortKey('change_pct'); setSortDir(d => d === 'desc' && sortKey === 'change_pct' ? 'asc' : 'desc') }}>
                        涨跌幅{sortKey === 'change_pct' ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                      <th className="sortable" onClick={() => { setSortKey('price'); setSortDir(d => d === 'desc' && sortKey === 'price' ? 'asc' : 'desc') }}>
                        现价{sortKey === 'price' ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                      <th className="sortable" onClick={() => { setSortKey('RPS50'); setSortDir(d => d === 'desc' && sortKey === 'RPS50' ? 'asc' : 'desc') }}>
                        RPS50{sortKey === 'RPS50' ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                      <th className="sortable" onClick={() => { setSortKey('RPS120'); setSortDir(d => d === 'desc' && sortKey === 'RPS120' ? 'asc' : 'desc') }}>
                        RPS120{sortKey === 'RPS120' ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                      <th className="sortable" onClick={() => { setSortKey('RPS250'); setSortDir(d => d === 'desc' && sortKey === 'RPS250' ? 'asc' : 'desc') }}>
                        RPS250{sortKey === 'RPS250' ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.length === 0 ? (
                      <tr><td colSpan={5} className="sig-empty">暂无信号</td></tr>
                    ) : (
                      sorted.map(s => {
                        const pct   = s.metadata.change_pct ?? s.up ?? 0
                        const isUp  = pct >= 0
                        return (
                          <tr key={s.code} className="sig-row" onClick={() => navigate(`/chart/${s.code}?s=${strategyKey}&tab=${s.section === 'kd1' ? 'kd1' : ''}`)}>
                            <td className="sig-name-cell">
                              <span className="sig-name">{s.name}</span>
                              <span className="sig-code">{s.code}</span>
                            </td>
                            <td className={`sig-pct-cell ${isUp ? 'up' : 'down'}`}>
                              {isUp ? '+' : ''}{fmt(pct)}%
                            </td>
                            <td className="sig-price-cell">{s.price != null ? s.price.toFixed(2) : '—'}</td>
                            <td className="sig-rps-cell" style={{ color: rpsColor(s.metadata.RPS50), fontWeight: s.metadata.RPS50 != null && s.metadata.RPS50 >= 90 ? 700 : 400 }}>
                              {s.metadata.RPS50 != null ? fmt(s.metadata.RPS50, 0) : '—'}
                            </td>
                            <td className="sig-rps-cell" style={{ color: rpsColor(s.metadata.RPS120), fontWeight: s.metadata.RPS120 != null && s.metadata.RPS120 >= 90 ? 700 : 400 }}>
                              {s.metadata.RPS120 != null ? fmt(s.metadata.RPS120, 0) : '—'}
                            </td>
                            <td className="sig-rps-cell" style={{ color: rpsColor(s.metadata.RPS250), fontWeight: s.metadata.RPS250 != null && s.metadata.RPS250 >= 90 ? 700 : 400 }}>
                              {s.metadata.RPS250 != null ? fmt(s.metadata.RPS250, 0) : '—'}
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
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
              color="#7b1fa2"
              bg="rgba(123,31,162,0.08)"
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
