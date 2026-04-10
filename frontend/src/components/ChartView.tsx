import { useEffect, useRef, useState } from 'react'
import type { KLineResponse } from '../api'

// ─── 指标计算 ─────────────────────────────────────────────────────────────────

function calcMA(closes: number[], period: number): (number | null)[] {
  const r = new Array<number | null>(closes.length).fill(null)
  for (let i = period - 1; i < closes.length; i++)
    r[i] = closes.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period
  return r
}

function calcEMA2(closes: number[], p = 10): (number | null)[] {
  const r = new Array<number | null>(closes.length).fill(null)
  let ema1: number | null = null
  let ema2: number | null = null
  for (let i = 0; i < closes.length; i++) {
    ema1 = ema1 === null ? closes[i] : closes[i] * (2 / (p + 1)) + ema1 * (1 - 2 / (p + 1))
    if (i >= p - 1) {
      ema2 = ema2 === null ? ema1 : ema1 * (2 / (p + 1)) + ema2 * (1 - 2 / (p + 1))
    }
    r[i] = ema2
  }
  return r
}

function calcBigBro(closes: number[]): (number | null)[] {
  const m14  = calcMA(closes, 14)
  const m28  = calcMA(closes, 28)
  const m57  = calcMA(closes, 57)
  const m114 = calcMA(closes, 114)
  return m14.map((v, i) => {
    if (v == null || m28[i] == null || m57[i] == null || m114[i] == null) return null
    return (v + m28[i]! + m57[i]! + m114[i]!) / 4
  })
}

function calcKDJ(highs: number[], lows: number[], closes: number[], n = 9) {
  const K = new Array<number | null>(closes.length).fill(null)
  const D = new Array<number | null>(closes.length).fill(null)
  const J = new Array<number | null>(closes.length).fill(null)
  K[n - 1] = D[n - 1] = 50
  for (let i = n; i < closes.length; i++) {
    const ll = Math.min(...lows.slice(i - n + 1, i + 1))
    const hh = Math.max(...highs.slice(i - n + 1, i + 1))
    const rsv = hh === ll ? 50 : (closes[i] - ll) / (hh - ll) * 100
    K[i] = rsv / 3 + K[i - 1]! * 2 / 3
    D[i] = (K[i]! + D[i - 1]!) / 2
    J[i] = 3 * K[i]! - 2 * D[i]!
  }
  return { K, D, J }
}



// ─── 配置 ─────────────────────────────────────────────────────────────────────
type MainKey = 'daxian' | 'zxdkx'

const MAIN_TOGGLES: { key: MainKey; label: string; color: string }[] = [
  { key: 'daxian', label: '大哥线',  color: '#f5d300' },
  { key: 'zxdkx',  label: '知行多空', color: '#ff7800' },
]

interface Props { code: string; name: string; kdata: KLineResponse }

// ─── 组件 ─────────────────────────────────────────────────────────────────────

export default function ChartView({ code, name, kdata }: Props) {
  const mainRef = useRef<HTMLDivElement>(null)
  const subRef1 = useRef<HTMLDivElement>(null)
  const subRef2 = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const charts  = useRef<Record<string, any>>({})

  const [mainVis, setMainVis] = useState<Record<MainKey, boolean>>({ daxian: true, zxdkx: true })
  const [kdjVals, setKdjVals] = useState<{K: number; D: number; J: number} | null>(null)
  const [mainVals, setMainVals] = useState<{close: number; daxian: number; zxdkx: number; changePct: number} | null>(null)

  useEffect(() => {
    const { candles } = kdata
    const dates   = candles.map(d => d.date)
    const opens   = candles.map(d => d.open)
    const closes  = candles.map(d => d.close)
    const highs   = candles.map(d => d.high)
    const lows    = candles.map(d => d.low)
    const volumes = candles.map(d => d.volume)
    const ups     = candles.map(d => d.up)

    const defaultStart = Math.max(0, dates.length - 80)

    const daxian = calcBigBro(closes)
    const zxdkx  = calcEMA2(closes)
    const { K, D, J } = calcKDJ(highs, lows, closes)

    const cat = (arr: (number | null)[]) =>
      arr.map((v, i) => v == null ? [i, '-'] : [i, +v.toFixed(2)])

    const volColor = (u: number) => u > 0 ? '#ef5350' : u < 0 ? '#26a69a' : '#9e9e9e'

    import('echarts').then((echarts: typeof import('echarts')) => {

      // ── 主图 ─────────────────────────────────────────────────────────
      if (!charts.current.main && mainRef.current)
        charts.current.main = echarts.init(mainRef.current)

      charts.current.main.setOption({
        backgroundColor: '#fff', animation: false,
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'cross' },
          formatter: (params: unknown) => {
            const arr = params as { seriesName: string; value: unknown[]; color: string }[]
            let html = ''
            arr.forEach(p => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const dp = (p as any)
              const isCandle = dp.seriesName === 'K线'
              if (isCandle) {
                // ECharts candlestick: [open, close, low, high], dataIndex gives position
                const chg = kdata.candles[dp.dataIndex]?.up ?? 0
                const chgColor = chg > 0 ? '#ef5350' : chg < 0 ? '#26a69a' : '#999'
                const chgSign  = chg > 0 ? '+' : ''
                const v = dp.value as number[]
                const o = v[0], c = v[1], l = v[2], h = v[3]
                html += `<span style="color:#ef5350">●</span> 开 <b>${o?.toFixed(2)}</b> 高 <b>${h?.toFixed(2)}</b> 低 <b>${l?.toFixed(2)}</b> 收 <b>${c?.toFixed(2)}</b><br/><span style="color:${chgColor}">涨幅</span> <b>${chgSign}${chg.toFixed(2)}%</b>`
              } else {
                const v = typeof p.value[1] === 'number' ? +p.value[1].toFixed(3) : '—'
                html += `<span style="color:${p.color}">●</span> ${p.seriesName} <b>${v}</b> &nbsp; `
              }
            })
            return html
          },
        },
        axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#777' } },
        grid: [{ left: 60, right: 16, top: 8, bottom: 8 }],
        title: {
          text: name,
          left: 'center', top: 4,
          textStyle: { fontSize: 13, color: '#333', fontWeight: '700' },
        },
        xAxis: [{ type: 'category' as const, data: dates, axisLine: { lineStyle: { color: '#ddd' } }, axisLabel: { fontSize: 10, color: '#999' }, splitLine: { show: false } }],
        yAxis: [{ scale: true, splitLine: { lineStyle: { color: '#f0f0f0' } }, axisLabel: { color: '#666' } }],
        dataZoom: [{ type: 'inside' as const, start: (defaultStart / dates.length) * 100, end: 100 }],
        series: [
          { type: 'candlestick' as const, name: 'K线', data: opens.map((o, i) => [o, closes[i], lows[i], highs[i]]),
            itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' } },
          ...(mainVis.daxian ? [{ type: 'line' as const, name: '大哥线', data: cat(daxian), lineStyle: { color: '#f5d300', width: 1.5 }, symbol: 'none' as const }] : []),
          ...(mainVis.zxdkx  ? [{ type: 'line' as const, name: '知行多空', data: cat(zxdkx), lineStyle: { color: '#ff7800', width: 1.5 }, symbol: 'none' as const }] : []),
        ],
        legend: { show: false },
      }, true)

      // 初始化主图标注值
      const lastClose  = closes[closes.length - 1]
      const lastDaxian = daxian[daxian.length - 1]
      const lastZxdkx  = zxdkx[zxdkx.length - 1]
      const prevClose = closes[closes.length - 2] ?? closes[closes.length - 1]
      const changePct = prevClose ? ((lastClose - prevClose) / prevClose * 100) : 0
      if (lastClose != null && lastDaxian != null && lastZxdkx != null)
        setMainVals({ close: +lastClose, daxian: +lastDaxian, zxdkx: +lastZxdkx, changePct })

      // ── KDJ ─────────────────────────────────────────────────────────
      if (!charts.current.kdj && subRef1.current)
        charts.current.kdj = echarts.init(subRef1.current)

      const lastK = K[K.length - 1]
      const lastD = D[D.length - 1]
      const lastJ = J[J.length - 1]
      if (lastK != null && lastD != null && lastJ != null)
        setKdjVals({ K: +lastK.toFixed(2), D: +lastD.toFixed(2), J: +lastJ.toFixed(2) })

      const kdjColor = (v: number | null, c: string) => v != null && v >= 90 ? '#e53935' : c

      charts.current.kdj.setOption({
        backgroundColor: '#fff', animation: false,
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'cross' },
          formatter: (params: unknown) => {
            const arr = params as { seriesName: string; value: [number, string | number]; color: string }[]
            let html = ''
            arr.forEach(p => {
              const v = typeof p.value[1] === 'number' ? +p.value[1].toFixed(2) : 0
              html += `<span style="color:${p.color}">●</span> ${p.seriesName} <b>${v}</b> &nbsp; `
            })
            return html
          },
        },
        axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#777' } },
        grid: [{ left: 60, right: 50, top: 8, bottom: 8 }],
        xAxis: [{ type: 'category' as const, data: dates, axisLine: { lineStyle: { color: '#ddd' } }, axisLabel: { fontSize: 10, color: '#999' }, splitLine: { show: false } }],
        yAxis: [{ max: 100, min: 0, splitNumber: 2, splitLine: { lineStyle: { color: '#f0f0f0' } }, axisLabel: { color: '#666' } }],
        dataZoom: [{ type: 'inside' as const, start: (defaultStart / dates.length) * 100, end: 100 }],
        series: [
          { type: 'line' as const, name: 'K', data: cat(K), lineStyle: { color: '#9c27b0', width: 1.2 }, symbol: 'none' as const },
          { type: 'line' as const, name: 'D', data: cat(D), lineStyle: { color: '#ff9800', width: 1.2 }, symbol: 'none' as const },
          { type: 'line' as const, name: 'J', data: cat(J), lineStyle: { color: '#2196f3', width: 1 }, symbol: 'none' as const,
            areaStyle: { color: 'rgba(33,150,243,0.06)' } },
          // K 最终值标注
          ...(lastK != null ? [{ type: 'line' as const, name: '_K', data: [[K.length - 1, lastK]], symbol: 'none' as const,
              label: { show: true, formatter: `K ${lastK.toFixed(2)}`, position: 'insideTop', color: kdjColor(lastK, '#9c27b0'),
                fontSize: 10, fontWeight: 700, backgroundColor: 'rgba(255,255,255,0.9)', padding: [2, 4], borderRadius: 2 } }] : []),
          // D 最终值标注
          ...(lastD != null ? [{ type: 'line' as const, name: '_D', data: [[D.length - 1, lastD]], symbol: 'none' as const,
              label: { show: true, formatter: `D ${lastD.toFixed(2)}`, position: 'insideTop', color: kdjColor(lastD, '#ff9800'),
                fontSize: 10, fontWeight: 700, backgroundColor: 'rgba(255,255,255,0.9)', padding: [2, 4], borderRadius: 2 } }] : []),
          // J 最终值标注
          ...(lastJ != null ? [{ type: 'line' as const, name: '_J', data: [[J.length - 1, lastJ]], symbol: 'none' as const,
              label: { show: true, formatter: `J ${lastJ.toFixed(2)}`, position: 'insideTop', color: kdjColor(lastJ, '#2196f3'),
                fontSize: 10, fontWeight: 700, backgroundColor: 'rgba(255,255,255,0.9)', padding: [2, 4], borderRadius: 2 } }] : []),
        ],
        legend: { show: false },
      }, true)

      // ── 成交量 ──────────────────────────────────────────────────────
      if (!charts.current.vol && subRef2.current)
        charts.current.vol = echarts.init(subRef2.current)
      charts.current.vol.setOption({
        backgroundColor: '#fff', animation: false,
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#777' } },
        grid: [{ left: 60, right: 16, top: 8, bottom: 8 }],
        xAxis: [{ type: 'category' as const, data: dates, axisLine: { lineStyle: { color: '#ddd' } }, axisLabel: { show: false }, splitLine: { show: false } }],
        yAxis: [{ show: false, scale: true, splitLine: { lineStyle: { color: '#f0f0f0' } } }],
        dataZoom: [{ type: 'inside' as const, start: (defaultStart / dates.length) * 100, end: 100 }],
        series: [{ type: 'bar' as const, name: '成交量', data: volumes.map((v, i) => ({ value: v, itemStyle: { color: volColor(ups[i]) } })) }],
        legend: { show: false },
      }, true)

    })

    const handler = () => Object.values(charts.current).forEach((c: unknown) => (c as { resize?: () => void })?.resize?.())
    window.addEventListener('resize', handler)
    return () => {
      window.removeEventListener('resize', handler)
      Object.values(charts.current).forEach((c: unknown) => (c as { dispose?: () => void })?.dispose?.())
      charts.current = {}
    }
  }, [code, kdata, mainVis])

  const toggleMain = (key: MainKey) => setMainVis(v => ({ ...v, [key]: !v[key] }))

  return (
    <div className="charts-wrap">
      <div className="chart-legend-toggle">
        {MAIN_TOGGLES.map(({ key, label, color }) => (
          <button
            key={key}
            className={`leg-btn ${mainVis[key] ? 'active' : ''}`}
            style={{ '--c': color } as React.CSSProperties}
            onClick={() => toggleMain(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="charts-stack">
        {/* 主图 */}
        <div className="chart-panel">
          <div className="sub-label-row">
            {mainVals && (
              <>
                <span className="sub-label" style={{ color: '#1a1a1a' }}>
                  收盘 <b>{mainVals.close.toFixed(2)}</b>
                </span>
                <span className="sub-label" style={{ color: '#f5d300' }}>
                  大哥线 <b>{mainVals.daxian.toFixed(2)}</b>
                </span>
                <span className="sub-label" style={{ color: '#ff7800' }}>
                  知行多空 <b>{mainVals.zxdkx.toFixed(2)}</b>
                </span>
                <span className="sub-label" style={{ color: mainVals.changePct >= 0 ? '#ef5350' : '#26a69a' }}>
                  涨幅 <b>{mainVals.changePct > 0 ? '+' : ''}{mainVals.changePct.toFixed(2)}%</b>
                </span>
              </>
            )}
          </div>
          <div ref={mainRef} style={{ height: 280 }} />
        </div>

        {/* KDJ */}
        <div className="chart-panel chart-gap">
          <div className="sub-label-row">
            {kdjVals && (
              <>
                <span className="sub-label" style={{ color: '#9c27b0' }}>K <b>{kdjVals.K}</b></span>
                <span className="sub-label" style={{ color: '#ff9800' }}>D <b>{kdjVals.D}</b></span>
                <span className="sub-label" style={{ color: '#2196f3' }}>J <b>{kdjVals.J}</b></span>
              </>
            )}
          </div>
          <div ref={subRef1} style={{ height: 110 }} />
        </div>

        {/* 成交量 */}
        <div className="chart-panel chart-gap" ref={subRef2} style={{ height: 110 }} />
      </div>
    </div>
  )
}
