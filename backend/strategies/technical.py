"""
技术面选股策略

b1  — 强势突破（KDJ超卖 + 多空线）
s2  — 月线反转（欧奈尔体系：年线突破 + 50日新高 + RPS强度）
s3  — RPS三线红（RPS50/120/250 四组三组合均>90，接近250日高点）
"""

import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from schemas.models import StockSignal

# 全局 RPS 矩阵（在 engine.run() 时预计算，所有策略共享）
_rps_matrix: pd.DataFrame | None = None


def set_rps_matrix(df: pd.DataFrame):
    """由 engine 调用，注入预计算的相对排名 RPS 矩阵"""
    global _rps_matrix
    _rps_matrix = df


def _get_rps(code: str, period: int) -> float | None:
    """从预计算矩阵读取某股票的某周期 RPS 相对排名（0~100）"""
    if _rps_matrix is None:
        return None
    try:
        col = f"rps{period}"
        val = _rps_matrix.loc[code, col]
        if pd.isna(val):
            return None
        return float(val)
    except (KeyError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
class TechnicalStrategy(BaseStrategy):
    """
    b1 — 强势突破
    条件：J<18 AND C>ZXDKX AND ZXDQ>ZXDKX
    RPS 取自预计算相对排名（0~100）
    """
    name = "technical"
    description = "技术面筛选 — 强势突破信号"

    def screen(self, market_data: dict) -> list[StockSignal]:
        results = []
        stock_list = market_data.get("stock_list")
        if stock_list is None or stock_list.empty:
            return results
        for _, row in stock_list.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            df   = market_data.get("daily_data", {}).get(code)
            if df is None or len(df) < 120:
                continue
            try:
                signal = self._b1_check(df, code, name)
                if signal:
                    results.append(signal)
            except Exception as e:
                print(f"[{self.name}] {code} 失败: {e}")
        return results

    def _b1_check(self, df: pd.DataFrame, code: str, name: str) -> StockSignal | None:
        N, M1, M2, M3, M4 = 9, 14, 28, 57, 114
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        low   = df["low"].values.astype(float)
        n     = len(close)

        # KDJ
        rsv = np.full(n, np.nan)
        for i in range(N - 1, n):
            ll = low[i - N + 1:i + 1].min()
            hh = high[i - N + 1:i + 1].max()
            rsv[i] = 50 if hh == ll else (close[i] - ll) / (hh - ll) * 100

        def _sma(arr, period):
            result = np.full_like(arr, np.nan)
            w = 1.0 / period
            for i in range(len(arr)):
                if np.isnan(result[i - 1]):
                    result[i] = arr[i]
                else:
                    result[i] = arr[i] * w + result[i - 1] * (1 - w)
            return result

        def _ema(arr, period):
            result = np.full_like(arr, np.nan)
            w = 2.0 / (period + 1)
            for i in range(len(arr)):
                if np.isnan(result[i - 1]):
                    result[i] = arr[i]
                else:
                    result[i] = arr[i] * w + result[i - 1] * (1 - w)
            return result

        def _ma(arr, period):
            result = np.full_like(arr, np.nan)
            for i in range(period - 1, len(arr)):
                result[i] = arr[i - period + 1:i + 1].mean()
            return result

        K     = _sma(rsv, 3)
        D     = _sma(K, 3)
        J     = 3 * K - 2 * D
        ZXDQ  = _ema(_ema(close, 10), 10)
        ZXDKX = (_ma(close, M1) + _ma(close, M2) + _ma(close, M3) + _ma(close, M4)) / 4

        idx = -1
        if np.isnan(J[idx]) or np.isnan(ZXDQ[idx]) or np.isnan(ZXDKX[idx]):
            return None
        J_val = J[idx]
        if not (J_val < 18 and close[idx] > ZXDKX[idx] and ZXDQ[idx] > ZXDKX[idx]):
            return None

        change_pct = float(df["up"].iloc[-1]) if "up" in df.columns else 0.0
        # 相对排名 RPS
        rps50  = _get_rps(code, 50)
        rps120 = _get_rps(code, 120)
        rps250 = _get_rps(code, 250)

        return StockSignal(
            code=code, name=name, signal_type="technical",
            reason=f"b1：J={J_val:.1f}<18, C>{ZXDKX[idx]:.2f}",
            metadata={
                "J":          round(J_val, 2),
                "change_pct": round(change_pct, 2),
                "RPS50":  round(rps50, 2)  if rps50  else None,
                "RPS120": round(rps120, 2) if rps120 else None,
                "RPS250": round(rps250, 2) if rps250 else None,
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
class MonthlyReversalStrategy(BaseStrategy):
    """
    s2 — 月线反转（欧奈尔体系）
    RPS50 ≥ 85（相对排名），其余条件同通达信原公式
    """
    name = "monthly_reversal"
    description = "月线反转 — 欧奈尔年线突破信号"
    RPS_THRESHOLD = 85   # Top 15%

    def screen(self, market_data: dict) -> list[StockSignal]:
        results = []
        stock_list = market_data.get("stock_list")
        if stock_list is None or stock_list.empty:
            return results
        for _, row in stock_list.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            df   = market_data.get("daily_data", {}).get(code)
            if df is None or len(df) < 260:
                continue
            try:
                signal = self._s2_check(df, code, name)
                if signal:
                    results.append(signal)
            except Exception as e:
                print(f"[{self.name}] {code} 失败: {e}")
        return results

    def _s2_check(self, df: pd.DataFrame, code: str, name: str) -> StockSignal | None:
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        n     = len(close)

        ma250  = self._ma(close, 250)
        hhv50  = self._hhv(high, 50)
        hhv100 = self._hhv(high, 100)

        # A：站上年线
        ma250_val = ma250[-1]
        A = not np.isnan(ma250_val) and close[-1] / ma250_val > 1

        # B：30日内创50日新高次数
        B = 0
        for i in range(n - 30, n):
            if np.isnan(hhv50[i]):
                continue
            if high[i] >= hhv50[i]:
                B += 1

        # RPS50（相对排名）
        rps50 = _get_rps(code, 50)
        D = rps50 is not None and rps50 >= self.RPS_THRESHOLD

        # AA：30日内站上年线天数
        AA = 0
        for i in range(n - 30, n):
            if np.isnan(ma250[i]):
                continue
            if close[i] > ma250[i]:
                AA += 1

        # AB：距100日高价<10%
        hhv100_val = hhv100[-1]
        AB = (not np.isnan(hhv100_val) and hhv100_val > 0
              and close[-1] / hhv100_val > 0.9)

        if not (A and B > 0 and D and (AA > 2) and (AA < 30) and AB):
            return None

        change_pct = float(df["up"].iloc[-1]) if "up" in df.columns else 0.0
        rps120 = _get_rps(code, 120)
        rps250 = _get_rps(code, 250)

        return StockSignal(
            code=code, name=name, signal_type="monthly_reversal",
            reason=f"月线反转：A股站年线{B}日新高，RPS50={rps50:.0f}，年线上{AA}天",
            metadata={
                "change_pct": round(change_pct, 2),
                "RPS50":  round(rps50, 2)  if rps50  else None,
                "RPS120": round(rps120, 2) if rps120 else None,
                "RPS250": round(rps250, 2) if rps250 else None,
                "A":  round(close[-1] / ma250_val, 4) if A else None,
                "B":  B,
                "AA": AA,
                "AB": round(close[-1] / hhv100_val, 4) if hhv100_val else None,
            }
        )

    def _ma(self, arr: np.ndarray, period: int) -> np.ndarray:
        result = np.full_like(arr, np.nan)
        for i in range(period - 1, len(arr)):
            result[i] = arr[i - period + 1:i + 1].mean()
        return result

    def _hhv(self, arr: np.ndarray, period: int) -> np.ndarray:
        result = np.full_like(arr, np.nan)
        for i in range(period - 1, len(arr)):
            result[i] = arr[i - period + 1:i + 1].max()
        return result


# ─────────────────────────────────────────────────────────────────────────────
class KD1Strategy(BaseStrategy):
    """
    kd1 — KD1战法（RPS三线红变体）
    条件：RPS50>95 OR RPS120>95 OR RPS250>95
          AND  今收 > HHV(250日最高) * 0.6
    """
    name = "kd1"
    description = "KD1战法 — 任一RPS>95 且距250日高点<40%"

    def screen(self, market_data: dict) -> list[StockSignal]:
        results = []
        stock_list = market_data.get("stock_list")
        if stock_list is None or stock_list.empty:
            return results
        for _, row in stock_list.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            df   = market_data.get("daily_data", {}).get(code)
            if df is None or len(df) < 250:
                continue
            try:
                signal = self._kd1_check(df, code, name)
                if signal:
                    results.append(signal)
            except Exception as e:
                print(f"[{self.name}] {code} 失败: {e}")
        return results

    def _kd1_check(self, df: pd.DataFrame, code: str, name: str) -> StockSignal | None:
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        n     = len(close)

        rps50  = _get_rps(code, 50)
        rps120 = _get_rps(code, 120)
        rps250 = _get_rps(code, 250)

        if None in (rps50, rps120, rps250):
            return None

        # 任一RPS > 95
        if not (rps50 > 95 or rps120 > 95 or rps250 > 95):
            return None

        # H/HHV(HIGH, 250) > 0.6
        hhv250 = self._hhv(high, 250)
        hhv250_val = hhv250[-1]
        if np.isnan(hhv250_val) or hhv250_val <= 0:
            return None
        if close[-1] / hhv250_val <= 0.6:
            return None

        change_pct = float(df["up"].iloc[-1]) if "up" in df.columns else 0.0

        return StockSignal(
            code=code, name=name, signal_type="kd1",
            reason=(f"KD1: RPS50={rps50:.1f} RPS120={rps120:.1f} RPS250={rps250:.1f}，"
                    f"250日高点距={close[-1]/hhv250_val:.1%}"),
            metadata={
                "change_pct":    round(change_pct, 2),
                "RPS50":  round(rps50, 2),
                "RPS120": round(rps120, 2),
                "RPS250": round(rps250, 2),
                "near_250hhm":   round(close[-1] / hhv250_val, 4),
            }
        )

    def _hhv(self, arr: np.ndarray, period: int) -> np.ndarray:
        result = np.full_like(arr, np.nan)
        for i in range(period - 1, len(arr)):
            result[i] = arr[i - period + 1:i + 1].max()
        return result


# ─────────────────────────────────────────────────────────────────────────────
class RPSTripleRedStrategy(BaseStrategy):
    """
    s3 — RPS三线红（通达信原公式）

    条件：4种组合任一满足即为信号
    BKH1 = (RPS50>90)  AND (RPS120>90)  AND (RPS250>90)
    BKH2 = (RPS50>90)  AND (RPS120>90)  AND (RPS250≤90)
    BKH3 = (RPS120>90) AND (RPS250>90)  AND (RPS50≤90)
    BKH4 = (RPS50>90)  AND (RPS250>90)  AND (RPS120≤90)

    PLUS: CLOSE / HHV(HIGH, 250) > 0.85
    """
    name = "rps_triple_red"
    description = "RPS三线红 — RPS50>90 AND RPS120>93 AND RPS250>95"
    RPS_THRESHOLD = 90

    def screen(self, market_data: dict) -> list[StockSignal]:
        results = []
        stock_list = market_data.get("stock_list")
        if stock_list is None or stock_list.empty:
            return results
        for _, row in stock_list.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            df   = market_data.get("daily_data", {}).get(code)
            if df is None or len(df) < 260:
                continue
            try:
                signal = self._s3_check(df, code, name)
                if signal:
                    results.append(signal)
            except Exception as e:
                print(f"[{self.name}] {code} 失败: {e}")
        return results

    def _s3_check(self, df: pd.DataFrame, code: str, name: str) -> StockSignal | None:
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)

        # RPS 相对排名（0~100）
        rps50  = _get_rps(code, 50)
        rps120 = _get_rps(code, 120)
        rps250 = _get_rps(code, 250)

        if None in (rps50, rps120, rps250):
            return None

        # 三线红阈值
        THRESH50  = 90
        THRESH120 = 93
        THRESH250 = 95

        # 三线红: RPS50>90 AND RPS120>93 AND RPS250>95
        bkh1 = (rps50 > THRESH50) and (rps120 > THRESH120) and (rps250 > THRESH250)

        if not bkh1:
            return None

        # 距250日高点<15%（HHV250）
        n = len(close)
        hhv250_vals = self._hhv(high, 250)
        hhv250 = hhv250_vals[-1]
        if np.isnan(hhv250) or hhv250 <= 0:
            return None
        if close[-1] / hhv250 <= 0.85:
            return None

        change_pct = float(df["up"].iloc[-1]) if "up" in df.columns else 0.0

        return StockSignal(
            code=code, name=name, signal_type="rps_triple_red",
            reason=(f"RPS三线红: RPS50={rps50:.1f} RPS120={rps120:.1f} RPS250={rps250:.1f}，"
                    f"250日高点距={close[-1]/hhv250:.1%}"),
            metadata={
                "change_pct": round(change_pct, 2),
                "RPS50":  round(rps50, 2),
                "RPS120": round(rps120, 2),
                "RPS250": round(rps250, 2),
                "near_250hhm": round(close[-1] / hhv250, 4),
                "BKH": ("BKH1" if bkh1 else "BKH2" if bkh2 else "BKH3" if bkh3 else "BKH4"),
            }
        )

    def _hhv(self, arr: np.ndarray, period: int) -> np.ndarray:
        result = np.full_like(arr, np.nan)
        for i in range(period - 1, len(arr)):
            result[i] = arr[i - period + 1:i + 1].max()
        return result
