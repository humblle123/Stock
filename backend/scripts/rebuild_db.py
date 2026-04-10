"""
重建股票数据库
- 白名单：akshare stock_info_a_code_name()（5498只A股）
- 数据源：TDX .day 文件（sh.zip / sz.zip）
- code 格式：纯6位数字字符串，如 '600000'、'000001'
- 字段：code, up, date, open, high, low, close, volume
- 批量插入
"""

import sys, os, struct, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import akshare as ak
import time

DB_PATH = "/root/ai-projects/stock-screener/data/stocks.db"
DAY_STRUCT = struct.Struct("IIIIIfII")


# ---------------------------------------------------------------
# 1. 获取 A 股白名单（akshare，格式：'000001' / '600000'）
# ---------------------------------------------------------------
def get_a_stock_white_list() -> set[str]:
    print("  连接 akshare...")
    for attempt in range(3):
        try:
            df = ak.stock_info_a_code_name()
            codes = set(df["code"].astype(str).tolist())
            print(f"  akshare 返回 {len(codes)} 只 A 股")
            return codes
        except Exception as e:
            print(f"  第{attempt+1}次失败: {e}")
            time.sleep(3)
    print("  akshare 全部失败")
    return set()


# ---------------------------------------------------------------
# 2. 提取 TDX 代码（纯6位数字）
# ---------------------------------------------------------------
def extract_tdx_codes(zip_path: str) -> dict[str, str]:
    """
    返回 {fname_in_zip: pure_code}
    pure_code: '600000' / '000001'（6位纯数字）
    """
    code_map = {}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for fname in zf.namelist():
            if not fname.endswith('.day'):
                continue
            base = os.path.basename(fname)        # 'sh600000.day' 或 'sz000001.day'
            code = base.replace('.day', '')[2:]   # 去掉 'sh' 或 'sz'，得 '600000'
            if code.isdigit() and len(code) == 6:
                code_map[fname] = code
    return code_map


# ---------------------------------------------------------------
# 3. 解析 .day 文件
# ---------------------------------------------------------------
def parse_day(raw: bytes) -> list[tuple]:
    """
    返回 [(code, up, date, open, high, low, close, volume)]
    - date: 'YYYY-MM-DD'
    - up: 涨幅%（今日收盘/昨收-1）×100
    - prices: 美分÷100
    """
    records = []
    prev_close = None
    for i in range(0, len(raw), 32):
        try:
            date_int, o, h, l, c, _, vol, _ = DAY_STRUCT.unpack_from(raw, i)
            year  = date_int // 10000
            month = (date_int % 10000) // 100
            day   = date_int % 100
            if not (1990 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                continue
            date_str  = f"{year:04d}-{month:02d}-{day:02d}"
            open_p  = round(o / 100.0, 2)
            high_p  = round(h / 100.0, 2)
            low_p   = round(l / 100.0, 2)
            close_p = round(c / 100.0, 2)
            volume  = int(vol)

            if prev_close is not None and prev_close > 0:
                up = round((close_p / prev_close - 1) * 100, 4)
            else:
                up = 0.0
            prev_close = close_p

            records.append((date_str, open_p, high_p, low_p, close_p, up, volume))
        except Exception:
            continue
    return records


# ---------------------------------------------------------------
# 4. 主流程
# ---------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS stock_daily")
    conn.execute("DROP TABLE IF EXISTS stocks")
    conn.execute("""
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,   -- '600000'
            name TEXT DEFAULT '',
            market TEXT DEFAULT ''    -- 'SH' / 'SZ'
        )
    """)
    conn.execute("""
        CREATE TABLE stock_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code  TEXT NOT NULL,
            up    REAL DEFAULT 0,
            date  TEXT NOT NULL,
            open  REAL,
            high  REAL,
            low   REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(code, date)
        )
    """)
    conn.execute("CREATE INDEX idx_sd_code ON stock_daily(code)")
    conn.execute("CREATE INDEX idx_sd_date ON stock_daily(date)")
    conn.commit()
    conn.close()
    print(f"[DB] 初始化完成: {DB_PATH}")


def main():
    print("=" * 55)
    print("重建股票数据库（akshare 白名单 + TDX 行情）")
    print("=" * 55)

    # Step 1: 白名单
    print("\n[1/5] 获取 A 股白名单（akshare）...")
    white_list = get_a_stock_white_list()
    if not white_list:
        print("❌ 无法获取白名单，退出")
        return
    print(f"  白名单合计: {len(white_list)} 只")

    # Step 2: 扫描 TDX 文件
    print("\n[2/5] 扫描 TDX 文件...")
    sh_map = extract_tdx_codes("/root/sh.zip")
    sz_map = extract_tdx_codes("/root/sz.zip")
    print(f"  上海: {len(sh_map)} 文件")
    print(f"  深圳: {len(sz_map)} 文件")

    # Step 3: 初始化 DB
    print("\n[3/5] 初始化数据库...")
    init_db()

    # Step 4: 匹配 + 导入
    print("\n[4/5] 匹配并导入行情...")
    conn = sqlite3.connect(DB_PATH)

    total_stocks  = 0
    total_records = 0
    batch         = []
    BATCH_SIZE    = 100_000

    for label, zip_path, file_map in [
        ("上海", "/root/sh.zip", sh_map),
        ("深圳", "/root/sz.zip", sz_map),
    ]:
        print(f"  === {label} ===")
        matched = skipped = 0

        with zipfile.ZipFile(zip_path, 'r') as zf:
            items = list(file_map.items())
            for i, (fname, code) in enumerate(items):
                # 白名单过滤
                if code not in white_list:
                    skipped += 1
                    continue

                try:
                    with zf.open(fname) as f:
                        raw = f.read()
                    records = parse_day(raw)
                    if not records:
                        continue

                    # stocks 表
                    market = 'SH' if fname.startswith('sh/') else 'SZ'
                    conn.execute(
                        "INSERT OR IGNORE INTO stocks (code, market) VALUES (?, ?)",
                        (code, market)
                    )

                    # 批量
                    for r in records:
                        batch.append((code, r[5], r[0], r[1], r[2], r[3], r[4], r[6]))
                    matched += 1
                    total_stocks += 1

                except Exception:
                    pass

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        "INSERT OR IGNORE INTO stock_daily "
                        "(code,up,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?,?)",
                        batch
                    )
                    total_records += len(batch)
                    conn.commit()
                    batch = []

                if (i + 1) % 2000 == 0:
                    print(f"    {i+1}/{len(items)} | 匹配 {matched} | 写入 {total_records:,} 条")

        print(f"    {label}: 匹配 {matched} 只，跳过 {skipped} 只（不在白名单）")

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO stock_daily "
            "(code,up,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?,?)",
            batch
        )
        total_records += len(batch)
        conn.commit()

    conn.close()

    # Step 5: 验证
    print("\n[5/5] 验证结果...")
    conn = sqlite3.connect(DB_PATH)
    sc  = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    dc  = conn.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
    mc  = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_daily").fetchone()[0]
    rng = conn.execute("SELECT MIN(date), MAX(date) FROM stock_daily").fetchone()
    top5 = conn.execute(
        "SELECT code, date, close, up FROM stock_daily ORDER BY date DESC, code LIMIT 5"
    ).fetchall()
    conn.close()

    print(f"\n{'=' * 55}")
    print(f"✅ 导入完成")
    print(f"   stocks 表:    {sc} 只")
    print(f"   stock_daily:  {dc:,} 条（{mc} 只有行情）")
    print(f"   日期范围:     {rng[0]} ~ {rng[1]}")
    print(f"   最新记录样本:")
    for row in top5:
        print(f"     {row}")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
