// ─── 数据模型 ──────────────────────────────────────────────────────────────────

export interface StockSignal {
  code: string
  name: string
  section: string
  reason: string
  metadata: {
    change_pct?: number
    J?: number
    RPS50?: number
    RPS120?: number
    RPS250?: number
    BKH?: string
    near_250hhm?: number
    B?: number
    AA?: number
  }
}

export interface DailyBriefing {
  date: string
  technical: StockSignal[]
  s2: StockSignal[]
  s3: StockSignal[]
}

export interface StockInfo {
  code: string
  name: string
  market: string
  industry: string
}

export interface KLineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  up: number
}

export type StrategyKey = 'technical' | 's2' | 's3'

export interface StrategyMeta {
  key: StrategyKey
  label: string
  tag: string
  color: string
  bg: string
}

export const STRATEGIES: StrategyMeta[] = [
  { key: 'technical', label: '中长线',   tag: 'B1', color: '#4caf50', bg: 'rgba(76,175,80,0.12)' },
  { key: 's3',        label: 'RPS三线红', tag: 'S3', color: '#f44336', bg: 'rgba(244,67,54,0.12)' },
]
