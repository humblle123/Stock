import { HashRouter, Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import StrategyPage from './pages/StrategyPage'
import ChartPage from './pages/ChartPage'
import './App.css'

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/strategy/:key" element={<StrategyPage />} />
        <Route path="/chart/:code" element={<ChartPage />} />
      </Routes>
    </HashRouter>
  )
}
