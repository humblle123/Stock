import { Link } from 'react-router-dom'

interface HeaderProps {
  date?: string
}

export default function Header({ date }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-logo">
        <span className="logo-icon">📈</span>
        <span className="logo-text">股策分析</span>
      </div>
      <nav className="header-nav">
        <Link to="/" className="nav-link">首页</Link>
      </nav>
      {date && (
        <span className="header-date">
          数据日期：{date}
        </span>
      )}
    </header>
  )
}
