import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchKD1Table, type KD1TableItem } from '../api'

type SortKey = keyof Pick<KD1TableItem, 'consec_days' | 'total_days' | 'times' | 'first_date' | 'last_date'>

const heatColor = (d: number) => {
  if (d >= 10) return { bg: '#e53935', color: '#fff', label: d + '天' }
  if (d >= 6)  return { bg: '#ff7043', color: '#fff', label: d + '天' }
  if (d >= 3)  return { bg: '#4caf50', color: '#fff', label: d + '天' }
  return { bg: '#f5f5f5', color: '#666', label: d + '天' }
}

const entryColor = (n: number) => {
  if (n >= 5) return '#e53935'
  if (n >= 3) return '#ff9800'
  return '#999'
}

const fmt = (s: string) => s?.slice(5) ?? '--'

export default function KD1Table() {
  const navigate = useNavigate()
  const [list, setList] = useState<KD1TableItem[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('consec_days')
  const [sortAsc, setSortAsc] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchKD1Table().then(data => { setList(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const sorted = [...list].sort((a, b) => {
    const av = a[sortKey] as number | string
    const bv = b[sortKey] as number | string
    if (av === bv) return 0
    return sortAsc ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  const current = sorted.filter(s => s.status === 'active')
  const exited  = sorted.filter(s => s.status === 'exit')
  const avgCon  = current.length
    ? (current.reduce((sum, s) => sum + s.consec_days, 0) / current.length).toFixed(1)
    : '0'

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(false) }
  }
  const sortCh = (key: SortKey) => key === sortKey ? (sortAsc ? ' ↑' : ' ↓') : ''

  return (
    <div className="tlrt-wrap">
      {loading ? (
        <div className="loading-screen"><div className="spinner" /><p>加载中...</p></div>
      ) : (
        <>
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

          <table className="tlrt-table">
            <thead>
              <tr>
                <th style={{ width: '22%' }}>股票</th>
                <th className="sortable" onClick={() => handleSort('consec_days')}>
                  连续{sortCh('consec_days')}
                </th>
                <th className="sortable" onClick={() => handleSort('total_days')}>
                  累计{sortCh('total_days')}
                </th>
                <th className="sortable" onClick={() => handleSort('times')}>
                  次数{sortCh('times')}
                </th>
                <th className="sortable" onClick={() => handleSort('first_date')}>
                  首加{sortCh('first_date')}
                </th>
                <th className="sortable" onClick={() => handleSort('last_date')}>
                  近60d首加{sortCh('last_date')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, i) => {
                const heat = heatColor(row.consec_days)
                const isActive = row.status === 'active'
                return (
                  <tr
                    key={row.code}
                    className={`tlrt-row ${isActive ? 'on' : 'off'} ${i % 2 === 0 ? 'even' : ''}`}
                    onClick={() => navigate(`/chart/${row.code}?s=bian`)}
                  >
                    <td className="tlrt-name-cell">
                      <div className="tlrt-name-row">
                        <span className={`tlrt-dot ${isActive ? 'on' : 'off'}`} />
                        <div className="tlrt-name-info">
                          <span className="tlrt-name">{row.name}</span>
                          <span className="tlrt-code">{row.code}</span>
                        </div>
                      </div>
                    </td>
                    <td className="tlrt-center">
                      <span className="tlrt-badge" style={{ background: heat.bg, color: heat.color }}>
                        {heat.label}
                      </span>
                    </td>
                    <td className="tlrt-center">
                      <span className="tlrt-cumul">{row.total_days}</span>
                    </td>
                    <td className="tlrt-center">
                      <span className="tlrt-entry" style={{ color: entryColor(row.times) }}>
                        {row.times}次
                      </span>
                    </td>
                    <td className="tlrt-date">{fmt(row.first_date)}</td>
                    <td className="tlrt-date">{fmt(row.last_date)}</td>
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
