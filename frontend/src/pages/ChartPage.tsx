import { lazy, Suspense, useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { fetchKLine, fetchReport, type ReportResponse } from '../api'
import Header from '../components/Header'

const ChartView = lazy(() => import('../components/ChartView'))

// section key -> display label
const SECTION_LABELS: Record<string, string> = {
  technical: '强势突破',
  s2:        '月线反转',
  s3:        'RPS三线红',
  kd1:       'KD1一线红',
}

export default function ChartPage() {
  const { code } = useParams<{ code: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const strategy = searchParams.get('s') ?? ''
  // /chart/:code?s=bian → 展示 s3（彼岸战法）
  const section      = strategy === 'bian' ? 's3' : (strategy || 'technical')
  const sectionLabel  = SECTION_LABELS[section] ?? section

  const [info,   setInfo]   = useState<{ name: string; code: string; industry: string } | null>(null)
  const [kdata, setKdata]  = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [report, setReport]  = useState<ReportResponse | null>(null)

  // ── 加载 K 线和报告 ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!code) return
    setLoading(true)
    Promise.all([fetchKLine(code), fetchReport()])
      .then(([k, r]) => {
        setInfo(k.info); setKdata(k as any); setReport(r); setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [code])

  // ── 列表导航 ────────────────────────────────────────────────────────────────
  const list = report ? (report.signals ?? []).filter(s => s.section === section) : []
  const idx  = list.findIndex(s => s.code === code)
  const total = list.length

  const goPrev = useCallback(() => {
    if (idx > 0)        navigate(`/chart/${list[idx - 1].code}?s=${strategy}`)
  }, [idx, list, strategy, navigate])

  const goNext = useCallback(() => {
    if (idx < total - 1) navigate(`/chart/${list[idx + 1].code}?s=${strategy}`)
  }, [idx, total, list, strategy, navigate])

  // ── 键盘 ↑↓ ─────────────────────────────────────────────────────────────────
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!report || !code) return
    if (e.key === 'ArrowDown') { e.preventDefault(); goNext() }
    else if (e.key === 'ArrowUp') { e.preventDefault(); goPrev() }
  }, [report, code, goPrev, goNext])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // ── 移动端滑动手势 ──────────────────────────────────────────────────────────
  const touchStartX = useRef<number | null>(null)
  const touchStartY = useRef<number | null>(null)

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX
    touchStartY.current = e.touches[0].clientY
  }, [])

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (touchStartX.current == null || touchStartY.current == null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    const dy = e.changedTouches[0].clientY - touchStartY.current
    // 只识别水平滑动（排除对角线或上下滑动）
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 44) {
      if (dx < 0) goNext()   // 左滑 → 下一只
      else        goPrev()   // 右滑 → 上一只
    }
    touchStartX.current = null
    touchStartY.current = null
  }, [goPrev, goNext])

  // ── 渲染 ─────────────────────────────────────────────────────────────────────
  const info_ = info ?? { name: code ?? '', code: code ?? '', industry: '' }
  const hasPrev = idx > 0
  const hasNext = idx < total - 1

  // 末根 K 线：现价 + 涨幅
  const lastCandle = kdata ? (kdata as any).candles[(kdata as any).candles.length - 1] : null
  const curPrice = lastCandle?.close as number | undefined
  const curUp    = lastCandle?.up    as number | undefined

  return (
    <div
      className="page-chart"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <Header />

      {/* ── 股票信息栏 ────────────────────────────────────────────────────── */}
      <div className="chart-info-bar">
        <button
          className="chart-back-btn"
          onClick={() => navigate(-1)}
          aria-label="返回"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <div className="chart-stock-info">
          <span className="ci-name">{info_.name}</span>
          <span className="ci-code">{info_.code}</span>
        </div>
        <div className="chart-price-block">
          {curPrice != null && (
            <span className="ci-price">{curPrice.toFixed(2)}</span>
          )}
          {curUp != null && (
            <span className="ci-up" data-up={curUp >= 0}>
              {curUp >= 0 ? '+' : ''}{curUp.toFixed(2)}%
            </span>
          )}
        </div>
        <div className="chart-position">
          {sectionLabel}
          {total > 0 && (
            <span className="ci-counter">{idx + 1} / {total}</span>
          )}
        </div>
      </div>

      {/* ── K 线图 ────────────────────────────────────────────────────────── */}
      <div className="chart-page-body">
        {loading ? (
          <div className="chart-loading"><div className="spinner" /></div>
        ) : kdata ? (
          <Suspense fallback={<div className="chart-loading"><div className="spinner" /></div>}>
            <ChartView code={code!} name={info_.name} kdata={kdata as any} />
          </Suspense>
        ) : null}
      </div>

      {/* ── 底部快捷导航栏（手机端） ───────────────────────────────────────── */}
      <div className="chart-bottom-nav">
        <button
          className="nav-btn nav-prev"
          onClick={goPrev}
          disabled={!hasPrev}
          aria-label="上一只"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M15 18l-6-6 6-6" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>上一只</span>
        </button>

        <div className="nav-center">
          <span className="nav-name">{info_.name}</span>
          <span className="nav-idx">{idx + 1} / {total}</span>
        </div>

        <button
          className="nav-btn nav-next"
          onClick={goNext}
          disabled={!hasNext}
          aria-label="下一只"
        >
          <span>下一只</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* ── 滑动手势提示（首次显示） ─────────────────────────────────────── */}
      {total > 1 && (
        <div className="swipe-hint">
          ← 左滑 / 右滑 → 切换
        </div>
      )}
    </div>
  )
}
