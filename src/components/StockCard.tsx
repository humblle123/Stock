import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type { StockSignal, StrategyMeta } from '../types'

interface OHLC { o: number; h: number; l: number; c: number }

interface Props {
  signal: StockSignal
  strategy: StrategyMeta
  lastPrice?: number
  thumb?: OHLC[]
}

const RPS_COLOR = (v: number | undefined, threshold = 90) =>
  v == null ? '#bbb' : v >= threshold ? '#e53935' : v >= 70 ? '#ff9800' : '#4caf50'

function CandleThumb({ ohlc }: { ohlc: OHLC[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !ohlc || ohlc.length < 2) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = 80
    const H = 36
    canvas.width = W
    canvas.height = H
    // 只取最近30天
    const recent = ohlc.slice(-30)
    const n = recent.length
    const vals: number[] = []
    for (const d of ohlc) { vals.push(d.o, d.h, d.l, d.c) }
    const minV = Math.min(...vals)
    const maxV = Math.max(...vals)
    const range = maxV - minV || 1
    const pad = 2

    // 白色背景 + 灰边框，区别于白底
    ctx.fillStyle = '#f5f5f5'
    ctx.fillRect(0, 0, W, H)
    ctx.strokeStyle = '#e0e0e0'
    ctx.lineWidth = 0.5
    ctx.strokeRect(0.5, 0.5, W - 1, H - 1)

    recent.forEach((d, i) => {
      const x = ((i + 0.5) / n) * W
      const bodyTop = H - ((d.c - minV) / range) * (H - pad * 2) - pad
      const bodyBot = H - ((d.o - minV) / range) * (H - pad * 2) - pad
      const bodyH = Math.max(1, Math.abs(bodyTop - bodyBot))
      const hiY = H - ((d.h - minV) / range) * (H - pad * 2) - pad
      const loY = H - ((d.l - minV) / range) * (H - pad * 2) - pad
      const color = d.c >= d.o ? '#ef5350' : '#26a69a'

      ctx.strokeStyle = color
      ctx.lineWidth = 0.5
      ctx.beginPath()
      ctx.moveTo(x, hiY)
      ctx.lineTo(x, bodyTop)
      ctx.moveTo(x, bodyBot)
      ctx.lineTo(x, loY)
      ctx.stroke()

      ctx.fillStyle = color
      ctx.fillRect(x - 1.5, Math.min(bodyTop, bodyBot), 3, bodyH)
    })
  }, [ohlc])

  return <canvas ref={canvasRef} className="card-sparkline" />
}

export default function StockCard({ signal, strategy, lastPrice, thumb }: Props) {
  const navigate = useNavigate()
  const { code, name, metadata } = signal
  const pct = metadata.change_pct ?? 0
  const isUp = pct >= 0

  return (
    <div
      className="stock-card"
      data-section={strategy.key}
      onClick={() => navigate(`/chart/${code}`)}
    >
      <div className="card-left">
        <div className="card-top">
          <div className="card-name-row">
            <span className="card-name">{name}</span>
            {lastPrice != null && (
              <span className={`card-price ${isUp ? 'up' : 'down'}`}>
                {lastPrice.toFixed(2)}
              </span>
            )}
          </div>
          <div className="card-code-row">
            <span className="card-code">{code}</span>
            <span className={`card-pct ${isUp ? 'up' : 'down'}`}>
              {isUp ? '+' : ''}{pct.toFixed(2)}%
            </span>
          </div>
        </div>

        <div className="card-indicators">
          {strategy.key !== 'technical' && metadata.RPS50 != null && (
            <span className="ind-tag ind-rps" style={{ color: RPS_COLOR(metadata.RPS50) }}>
              <span className="ind-rps-label">RPS50</span>
              <b>{metadata.RPS50.toFixed(0)}</b>
            </span>
          )}
          {strategy.key !== 'technical' && metadata.RPS120 != null && (
            <span className="ind-tag ind-rps" style={{ color: RPS_COLOR(metadata.RPS120) }}>
              <span className="ind-rps-label">RPS120</span>
              <b>{metadata.RPS120.toFixed(0)}</b>
            </span>
          )}
          {strategy.key !== 'technical' && metadata.RPS250 != null && (
            <span className="ind-tag ind-rps" style={{ color: RPS_COLOR(metadata.RPS250) }}>
              <span className="ind-rps-label">RPS250</span>
              <b>{metadata.RPS250.toFixed(0)}</b>
            </span>
          )}
          {strategy.key === 's2' && metadata.B != null && (
            <span className="ind-tag ind-b">B{metadata.B}</span>
          )}
          {strategy.key === 's3' && metadata.BKH && (
            <span className="ind-tag ind-bkh">{metadata.BKH}</span>
          )}
          {metadata.J != null && (
            <span className="ind-tag ind-j">J<b>{metadata.J.toFixed(0)}</b></span>
          )}
        </div>
      </div>

      {thumb && thumb.length >= 5 && (
        <div className="card-thumb">
          <CandleThumb ohlc={thumb} />
        </div>
      )}
    </div>
  )
}
