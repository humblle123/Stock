import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export interface KLineItem {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  up: number
}

export interface KLineResponse {
  code: string
  info: { code: string; name: string; market: string; industry: string }
  candles: KLineItem[]
}

export async function fetchKLine(code: string): Promise<KLineResponse> {
  const { data } = await http.get<KLineResponse>(`/kline/${code}`)
  return data
}

// ─── 报告 ─────────────────────────────────────────────────────────────────────

export interface StockSignal {
  code: string
  name: string
  section: string
  reason: string
  price?: number    // 今日收盘价
  up?: number       // 涨跌幅%（来自腾讯快照）
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

export interface ReportResponse {
  date: string
  signals: StockSignal[]
}

export async function fetchReport(): Promise<ReportResponse> {
  const { data } = await http.get<ReportResponse>('/report')
  return data
}

// ─── 三线红跟踪报表 ───────────────────────────────────────────────────────────

export interface ThreeLineRedItem {
  code: string
  name: string
  first_added_date: string
  consecutive_days: number
  cumulative_days: number
  entry_count: number
  last_added_date: string
  is_current: number
}

export async function fetchThreeLineRedTable(): Promise<ThreeLineRedItem[]> {
  const { data } = await http.get<{ data: ThreeLineRedItem[] }>('/three-line-red')
  return data.data
}

export interface KD1TableItem {
  code: string
  name: string
  first_date: string
  last_date: string
  consec_days: number
  total_days: number
  times: number
  status: string
  exit_date: string | null
}

export async function fetchKD1Table(): Promise<KD1TableItem[]> {
  const { data } = await http.get<{ data: KD1TableItem[] }>('/kd1-table')
  return data.data
}
