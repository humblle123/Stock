"""
选股引擎
数据来源：本地 SQLite（TDX .day 文件 + akshare 白名单）
"""

import datetime
import sqlite3
import pandas as pd
import numpy as np
from data.sqlite_store import get_conn
from schemas.models import DailyBriefing, StockSignal
from strategies.technical import (
    TechnicalStrategy,
    MonthlyReversalStrategy,
    RPSTripleRedStrategy,
    KD1Strategy,
    set_rps_matrix,
)


class ScreeningEngine:
    def __init__(self, strategies: list[str] = None, max_stocks: int = 6000):
        self.strategies = strategies or ["technical", "s2", "s3"]
        self.max_stocks = max_stocks
        self._init_strategies()

    def _init_strategies(self):
        self.strategy_map = {
            "technical": TechnicalStrategy(),
            "s2": MonthlyReversalStrategy(),
            "s3": RPSTripleRedStrategy(),
            "kd1": KD1Strategy(),
        }

    def _get_excluded_codes(self) -> set:
        excluded = set()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT code FROM stocks WHERE name LIKE '%ST%' OR name LIKE '%*ST%'"
            " OR name LIKE '%转债%' OR name LIKE '%债%'"
        )
        for (code,) in cur.fetchall():
            excluded.add(code)
        conn.close()
        print(f"[Engine] 排除 {len(excluded)} 只（ST/转债）")
        return excluded

    def _precompute_rps_matrix(self, daily_data: dict) -> pd.DataFrame:
        """
        一次性计算全市场各周期收益率相对排名（RPS 0~100）。
        周期：5, 10, 15, 20, 50, 120, 250
        """
        print("[Engine] 预计算 RPS 相对排名矩阵...")
        rows = []
        for code, df in daily_data.items():
            if len(df) < 260:
                continue
            close = df["close"].values.astype(float)
            row = {"code": code}
            for p in [5, 10, 15, 20, 50, 120, 250]:
                if len(close) <= p + 1:
                    row[f"rps{p}"] = np.nan
                    continue
                old = close[-(p + 1)]
                curr = close[-1]
                row[f"rps{p}"] = np.nan if old <= 0 else (curr / old - 1) * 100
            rows.append(row)

        ret_df = pd.DataFrame(rows).set_index("code")
        rps_df = pd.DataFrame(index=ret_df.index)
        for p in [5, 10, 15, 20, 50, 120, 250]:
            col = f"rps{p}"
            if col in ret_df.columns:
                rps_df[col] = ret_df[col].rank(pct=True) * 100

        print(f"[Engine] RPS矩阵: {len(rps_df)} 只股票")
        return rps_df

    def run(self) -> DailyBriefing:
        date = datetime.date.today().strftime("%Y-%m-%d")
        briefing = DailyBriefing(date=date)
        excluded = self._get_excluded_codes()

        conn = get_conn()
        stock_df = pd.read_sql("""
            SELECT DISTINCT s.code, s.name
            FROM stocks s
            JOIN stock_daily d ON s.code = d.code
            WHERE s.code NOT IN (SELECT code FROM stocks WHERE name LIKE '%ST%' OR name LIKE '%转债%')
            ORDER BY s.code
        """, conn)
        conn.close()

        if stock_df.empty:
            print("[Engine] 数据库为空")
            return briefing

        stock_df = stock_df[~stock_df["code"].isin(excluded)]
        codes = stock_df["code"].tolist()[:self.max_stocks]
        print(f"[Engine] 扫描 {len(codes)} 只股票...")

        conn = get_conn()
        daily_df = pd.read_sql(f"""
            SELECT code, date, open, high, low, close, volume, up
            FROM stock_daily
            WHERE code IN ({','.join('?' * len(codes))})
              AND date >= date('now', '-600 days')
        """, conn, params=codes)
        conn.close()

        daily_data = {
            code: grp.drop(columns="code").reset_index(drop=True)
            for code, grp in daily_df.groupby("code")
        }
        loaded = len(daily_data)
        print(f"[Engine] 加载了 {loaded} 只股票近600日数据")

        # 预计算全市场 RPS 相对排名矩阵，注入各策略
        rps_df = self._precompute_rps_matrix(daily_data)
        set_rps_matrix(rps_df)

        market_data = {
            "stock_list": stock_df,
            "daily_data": daily_data,
            "rps_df": rps_df,
        }

        for strategy_name in self.strategies:
            strategy = self.strategy_map.get(strategy_name)
            if not strategy:
                continue
            print(f"[Engine] 执行策略: {strategy.name}")
            try:
                signals = strategy.screen(market_data)
                signals = [
                    s for s in signals
                    if "ST" not in s.name and "转债" not in s.name and "债" not in s.name
                ]
                if strategy_name == "technical":
                    briefing.technical = signals
                elif strategy_name == "s2":
                    briefing.s2 = signals
                elif strategy_name == "s3":
                    briefing.s3 = signals
                elif strategy_name == "kd1":
                    briefing.kd1 = signals
                print(f"[Engine] {strategy.name} 筛选出 {len(signals)} 只")
            except Exception as e:
                import traceback
                print(f"[Engine] 策略失败: {e}")
                traceback.print_exc()

        return briefing

    def format_briefing(self, briefing: DailyBriefing) -> str:
        def fmt(v):
            if isinstance(v, float) or isinstance(v, int):
                return f"{v:.1f}"
            return str(v) if v is not None else '-'

        def f_b1(signals):
            if not signals:
                return "暂无信号"
            lines = []
            for s in signals[:20]:
                lines.append(
                    f"• {s.name}({s.code}) | 今日{s.metadata.get('change_pct','N/A'):+.2f}% | "
                    f"J={s.metadata.get('J','N/A')} | "
                    f"RPS50={fmt(s.metadata.get('RPS50'))} "
                    f"RPS120={fmt(s.metadata.get('RPS120'))} "
                    f"RPS250={fmt(s.metadata.get('RPS250'))}"
                )
            return "\n".join(lines)

        def f_s2(signals):
            if not signals:
                return "暂无信号"
            lines = []
            for s in signals[:20]:
                lines.append(
                    f"• {s.name}({s.code}) | 今日{s.metadata.get('change_pct','N/A'):+.2f}% | "
                    f"RPS50={fmt(s.metadata.get('RPS50'))} "
                    f"RPS120={fmt(s.metadata.get('RPS120'))} "
                    f"RPS250={fmt(s.metadata.get('RPS250'))} | "
                    f"B={s.metadata.get('B','?')}日新高 AA={s.metadata.get('AA','?')}天"
                )
            return "\n".join(lines)

        def f_s3(signals):
            if not signals:
                return "暂无信号"
            lines = []
            for s in signals[:30]:
                lines.append(
                    f"• {s.name}({s.code}) | 今日{s.metadata.get('change_pct','N/A'):+.2f}% | "
                    f"RPS50={fmt(s.metadata.get('RPS50'))} "
                    f"RPS120={fmt(s.metadata.get('RPS120'))} "
                    f"RPS250={fmt(s.metadata.get('RPS250'))} "
                    f"[{s.metadata.get('BKH','?')}] | "
                    f"250日高点距={s.metadata.get('near_250hhm',0):.1%}"
                )
            return "\n".join(lines)

        return f"""📊 今日选股简报 — {briefing.date}

【强势突破】(b1 — KDJ超卖+多空线)
{f_b1(briefing.technical)}

【月线反转】(s2 — 欧奈尔年线突破)
{f_s2(briefing.s2)}

【RPS三线红】(s3 — RPS50/120/250 四组三组合)
{f_s3(briefing.s3)}

⚠️ 仅供参考，不构成投资建议"""
