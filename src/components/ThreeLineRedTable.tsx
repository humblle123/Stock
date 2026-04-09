import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchThreeLineRedTable, type ThreeLineRedItem } from '../api'

type SortKey = keyof Pick<ThreeLineRedItem, 'consecutive_days' | 'cumulative_days' | 'entry_count' | 'first_added_date' | 'last_added_date'>

// 连续天数 → 颜色等级
const heatColor = (d: number) => {
  if (d >= 10) return { bg: '#e53935', color: '#fff', label: d + '天' }
  if (d >= 6)  return { bg: '#ff7043', color: '#fff', label: d + '天' }
  if (d >= 3)  return { bg: '#4caf50', color: '#fff', label: d + '天' }
  return { bg: '#f5f5f5', color: '#666', label: d + '天' }
}

// 进入次数 → 颜色
const entryColor = (n: number) => {
  if (n >= 5) return '#e53935'
  if (n >= 3) return '#ff9800'
  return '#999'
}

const fmt = (s: string) => s.slice(5)  // '2026-04-09' → '04-09'

export default function ThreeLineRedTable() {
  const navigate = useNavigate()
  const [list, setList] = useState<ThreeLineRedItem[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('consecutive_days')
  const [sortAsc, setSortAsc] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchThreeLineRedTable().then(data => {
      setList(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const sorted = [...list].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    if (av === bv) return 0
    return sortAsc ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  // 统计
  const current = sorted.filter(s => s.is_current === 1)
  const exited  = sorted.filter(s => s.is_current === 0)
  const avgCon  = current.length
    ? (current.reduce((sum, s) => sum + s.consecutive_days, 0) / current.length).toFixed(1)
    : '0'

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(false) }
  }

  const sortCh = (key: SortKey) =>
    key === sortKey ? (sortAsc ? ' ↑' : ' ↓') : ''

  return (
    <div className="tlrt-wrap">
      {loading ? (
        <div className="loading-screen"><div className="spinner" /><p>加载中...</p></div>
      ) : (
        <>
          {/* 统计栏 */}
          <div className="tlrt-stat-bar">
            <div className="tlrt-stat">
              <span className="tlrt-stat-num">{sorted.length}</span>
              <span className="tlrt-stat-lbl">全部</span>
            </div>
            <div className="tlrt-stat">
              <span className="tlrt-stat-num" style={{ color: 'var(--up)' }}>{current.length}</span>
              <span className="tlrt-stat-lbl">在榜</span>
            </div>
            <div className="tlrt-stat">
              <span className="tlrt-stat-num" style={{ color: 'var(--text3)' }}>{exited.length}</span>
              <span className="tlrt-stat-lbl">已退出</span>
            </div>
            <div className="tlrt-stat">
              <span className="tlrt-stat-num">{avgCon}</span>
              <span className="tlrt-stat-lbl">平均连续</span>
            </div>
          </div>

          {/* 表头 */}
          <table className="tlrt-table">
            <thead>
              <tr>
                <th style={{ width: '22%' }}>股票</th>
                <th className="sortable" onClick={() => handleSort('consecutive_days')}>
                  连续{sortCh('consecutive_days')}
                </th>
                <th className="sortable" onClick={() => handleSort('cumulative_days')}>
                  累计{sortCh('cumulative_days')}
                </th>
                <th className="sortable" onClick={() => handleSort('entry_count')}>
                  次数{sortCh('entry_count')}
                </th>
                <th className="sortable" onClick={() => handleSort('first_added_date')}>
                  首加{sortCh('first_added_date')}
                </th>
                <th className="sortable" onClick={() => handleSort('last_added_date')}>
                  近60d首加{sortCh('last_added_date')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s, i) => {
                const heat = heatColor(s.consecutive_days)
                return (
                  <tr
                    key={s.code}
                    className={`tlrt-row ${s.is_current === 1 ? 'on' : 'off'} ${i % 2 === 0 ? 'even' : ''}`}
                    onClick={() => navigate(`/chart/${s.code}?s=bian`)}
                  >
                    <td className="tlrt-name-cell">
                      <div className="tlrt-name-row">
                        {s.is_current === 1
                          ? <span className="tlrt-dot on" />
                          : <span className="tlrt-dot off" />
                        }
                        <div className="tlrt-name-info">
                          <span className="tlrt-name">{s.name}</span>
                          <span className="tlrt-code">{s.code}</span>
                        </div>
                      </div>
                    </td>
                    <td className="tlrt-center">
                      <span
                        className="tlrt-badge"
                        style={{ background: heat.bg, color: heat.color }}
                      >
                        {heat.label}
                      </span>
                    </td>
                    <td className="tlrt-center">
                      <span className="tlrt-cumul">{s.cumulative_days}</span>
                    </td>
                    <td className="tlrt-center">
                      <span
                        className="tlrt-entry"
                        style={{ color: entryColor(s.entry_count) }}
                      >
                        {s.entry_count}次
                      </span>
                    </td>
                    <td className="tlrt-date">{fmt(s.first_added_date)}</td>
                    <td className="tlrt-date">{fmt(s.last_added_date)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div className="tlrt-footer">{sorted.length} 只</div>
        </>
      )}
    </div>
  )
}
