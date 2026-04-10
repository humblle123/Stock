import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchReport } from '../api'
import Header from '../components/Header'
import type { ReportResponse } from '../api'

const TACTICS = [
  {
    key: 'z',
    title: 'Z哥战法',
    desc: '中长线策略',
    color: '#4caf50',
    bg: 'rgba(76,175,80,0.1)',
    border: 'rgba(76,175,80,0.3)',
    icon: '📈',
    path: '/strategy/z',
  },
  {
    key: 'bian',
    title: '彼岸战法',
    desc: 'RPS三线红 + KD1一线红',
    color: '#f44336',
    bg: 'rgba(244,67,54,0.1)',
    border: 'rgba(244,67,54,0.3)',
    icon: '🎯',
    path: '/strategy/bian',
  },
]

export default function HomePage() {
  const [data, setData] = useState<ReportResponse | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetchReport().then(d => setData(d)).catch(() => {})
  }, [])

  return (
    <div className="page-home">
      <Header date={data?.date} />
      <div className="home-body">
        <div className="tactics-grid">
          {TACTICS.map(t => (
            <div
              key={t.key}
              className="tactic-card"
              style={{
                borderColor: t.border,
                background: t.bg,
              }}
              onClick={() => navigate(t.path)}
            >
              <span className="tactic-icon">{t.icon}</span>
              <div className="tactic-info">
                <div className="tactic-title" style={{ color: t.color }}>{t.title}</div>
                <div className="tactic-desc">{t.desc}</div>
              </div>
              <span className="tactic-arrow">›</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
