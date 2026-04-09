"""
A 股历史行情下载器 — yfinance 批量版
yfinance 优点：速度快，批量下载
缺点：部分早期股票可能无数据

运行方式:
  python scripts/download_all_history.py --test      # 测试5只
  python scripts/download_all_history.py --limit 200  # 先下200只
  python scripts/download_all_history.py              # 全量（约5000只）
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import time
import sqlite3
from data.sqlite_store import init_db, upsert_stock, get_all_codes, count_records, get_conn, DB_PATH


# A 股全量代码范围（纯数字，存进 SQLite 用）
_UNIVERSE = []
for c in range(600000, 605001):  _UNIVERSE.append((str(c), "SH"))
for c in range(601000, 602001):  _UNIVERSE.append((str(c), "SH"))
for c in range(688000, 689001):  _UNIVERSE.append((str(c), "SH"))
for c in range(0, 3001):         _UNIVERSE.append((str(c).zfill(6), "SZ"))
for c in range(300000, 303001):  _UNIVERSE.append((str(c), "SZ"))


def _yf_code(pure_code: str, market: str) -> str:
    suffix = ".SS" if market == "SH" else ".SZ"
    return f"{pure_code.zfill(6)}{suffix}"


def download_one(pure_code: str, market: str) -> pd.DataFrame:
    """下载单只股票全部历史日线（前复权）"""
    ticker_str = _yf_code(pure_code, market)
    try:
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period="max", auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    # 整理字段
    result_rows = []
    for dt, row in df.iterrows():
        try:
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, 'strftime') else str(dt)[:10]
            result_rows.append({
                "code": pure_code,
                "date": date_str,
                "open": round(float(row["Open"]), 2) if pd.notna(row["Open"]) else 0,
                "high": round(float(row["High"]), 2) if pd.notna(row["High"]) else 0,
                "low": round(float(row["Low"]), 2) if pd.notna(row["Low"]) else 0,
                "close": round(float(row["Close"]), 2) if pd.notna(row["Close"]) else 0,
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
            })
        except Exception:
            continue

    return pd.DataFrame(result_rows)


def save_to_sqlite(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    conn = get_conn()
    rows = [
        (r["code"], r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
        for _, r in df.iterrows()
    ]
    if not rows:
        return 0
    conn.executemany("""
        INSERT INTO daily_price (code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, date) DO UPDATE SET
            open=excluded.open, high=excluded.high,
            low=excluded.low, close=excluded.close, volume=excluded.volume
    """, rows)
    conn.commit()
    conn.close()
    return len(rows)


def run(test: bool = False, limit: int = 0):
    init_db()
    universe = _UNIVERSE

    if test:
        universe = universe[:5]
    elif limit > 0:
        universe = universe[:limit]

    tag = f"测试({len(universe)}只)" if test else (f"限速({limit}只)" if limit else f"全量({len(universe)}只)")
    print(f"[yfinance] {tag} 开始下载...")

    total = len(universe)
    success = fail = total_records = 0

    # 批量下载（每批20只，yfinance支持）
    batch_size = 20
    for batch_start in range(0, total, batch_size):
        batch = universe[batch_start:batch_start + batch_size]
        yf_codes = [_yf_code(c, m) for c, m in batch]

        try:
            data = yf.download(
                yf_codes,
                period="max",
                group_by="Ticker",
                auto_adjust=False,
                progress=False,
                timeout=15
            )
        except Exception as e:
            print(f"  批次 {batch_start} 下载失败: {e}")
            time.sleep(3)
            continue

        for pure_code, market in batch:
            yf_code = _yf_code(pure_code, market)
            try:
                if len(batch) == 1:
                    df = data
                else:
                    df = data[yf_code] if yf_code in data.columns else pd.DataFrame()

                if df is None or df.empty:
                    fail += 1
                    continue

                df = df.reset_index()
                if "Date" not in df.columns:
                    fail += 1
                    continue

                # 整理数据
                rows = []
                for _, r in df.iterrows():
                    try:
                        dt = r["Date"]
                        date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, 'strftime') else str(dt)[:10]
                        rows.append((
                            pure_code, date_str,
                            round(float(r["Open"]), 2) if pd.notna(r["Open"]) else 0,
                            round(float(r["High"]), 2) if pd.notna(r["High"]) else 0,
                            round(float(r["Low"]), 2) if pd.notna(r["Low"]) else 0,
                            round(float(r["Close"]), 2) if pd.notna(r["Close"]) else 0,
                            int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
                        ))
                    except Exception:
                        continue

                if not rows:
                    fail += 1
                    continue

                conn = get_conn()
                conn.executemany("""
                    INSERT INTO daily_price (code, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, date) DO UPDATE SET
                        open=excluded.open, high=excluded.high,
                        low=excluded.low, close=excluded.close, volume=excluded.volume
                """, rows)
                conn.commit()
                conn.close()

                upsert_stock(pure_code, "", market)
                success += 1
                total_records += len(rows)

            except Exception as e:
                fail += 1
                print(f"  {pure_code} 处理失败: {e}")

        if (batch_start + batch_size) % 40 == 0 or (batch_start + batch_size) >= total:
            stats = count_records()
            done = min(batch_start + batch_size, total)
            print(f"  进度 {done}/{total} | 成功 {success} | 失败 {fail} | DB: {stats['stocks']}只 {stats['prices']}条")

        time.sleep(1)  # 避免被限

    stats = count_records()
    print(f"\n✅ 完成！成功 {success} 只股票，新增 {total_records} 条行情")
    print(f"   DB: {stats['stocks']}只股票, {stats['prices']}条行情 → {DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    run(**vars(parser.parse_args()))
