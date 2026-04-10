"""
通达信 .day 数据导入脚本 v2
- 解压 sh.zip / sz.zip
- 用 baostock 标准列表做过滤（只导入存在的股票）
- 批量插入 stock_daily 表
- 输出匹配结果
"""

import sys, os, struct, zipfile, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import baostock as bs

DB_PATH = "/root/ai-projects/stock-screener/data/stocks.db"
DAY_STRUCT = struct.Struct("IIIIIfII")


# ─── 1. 解析 .day 文件 ────────────────────────────────────────────

def parse_day_bytes(raw: bytes, code: str) -> list:
    records = []
    for i in range(0, len(raw), 32):
        try:
            date_int, o, h, l, c, _, vol, _ = DAY_STRUCT.unpack_from(raw, i)
            year = date_int // 10000
            month = (date_int % 10000) // 100
            day = date_int % 100
            if not (1990 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                continue
            records.append((
                code,
                f"{year:04d}-{month:02d}-{day:02d}",
                round(o / 100.0, 2),
                round(h / 100.0, 2),
                round(l / 100.0, 2),
                round(c / 100.0, 2),
                int(vol)
            ))
        except Exception:
            continue
    return records


# ─── 2. 解压并提取所有代码 ───────────────────────────────────────

def extract_codes_from_zip(zip_path: str) -> dict:
    """返回 {文件名: 纯数字代码}"""
    code_map = {}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for fname in zf.namelist():
            if not fname.endswith('.day'):
                continue
            basename = os.path.basename(fname)  # e.g. sh600000.day
            raw_code = basename.replace('sh', '').replace('sz', '').replace('.day', '')
            if raw_code.isdigit() and len(raw_code) == 6:
                code_map[fname] = raw_code
    return code_map


# ─── 3. 从 baostock 获取标准 A 股列表 ────────────────────────────

def get_baostock_codes() -> set:
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock login failed: {lg.error_msg}")
    rs = bs.query_all_stock()
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    codes = set()
    for row in data:
        raw = row[0]  # e.g. "sh.600000"
        pure = raw.replace('sh.', '').replace('sz.', '')
        codes.add(pure)
    return codes


# ─── 4. 初始化数据库 ─────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS stock_daily")
    conn.execute("DROP TABLE IF EXISTS stocks")
    conn.execute("""
        CREATE TABLE stocks (
            code TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            market TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE stock_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(code, date)
        )
    """)
    conn.execute("CREATE INDEX idx_sd_code ON stock_daily(code)")
    conn.execute("CREATE INDEX idx_sd_date ON stock_daily(date)")
    conn.commit()
    conn.close()
    print("[DB] 初始化完成")


# ─── 5. 批量写入 ─────────────────────────────────────────────────

def batch_insert(conn: sqlite3.Connection, records: list, batch_size: int = 50000):
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        conn.executemany(
            "INSERT OR IGNORE INTO stock_daily (code,date,open,high,low,close,volume) "
            "VALUES (?,?,?,?,?,?,?)",
            batch
        )
        conn.commit()
        total += len(batch)
        print(f"  已写入 {total:,} 条", flush=True)


# ─── 6. 主流程 ───────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("通达信 .day 数据导入 v2")
    print("=" * 55)

    # Step 1: 解压
    print("\n[1/5] 解压文件...")
    sh_codes = extract_codes_from_zip("/root/sh.zip")
    sz_codes = extract_codes_from_zip("/root/sz.zip")
    all_local = {**sh_codes, **sz_codes}
    print(f"  上海: {len(sh_codes)} 个 .day 文件")
    print(f"  深圳: {len(sz_codes)} 个 .day 文件")
    print(f"  合计: {len(all_local)} 个")

    # Step 2: baostock 标准列表
    print("\n[2/5] 从 baostock 获取 A 股标准列表...")
    bs_codes = get_baostock_codes()
    print(f"  baostock A 股: {len(bs_codes)} 只")

    # Step 3: 匹配
    matched = set(all_local.values()) & bs_codes
    print(f"\n[3/5] 匹配结果: {len(matched)} 只（在 baostock 列表中）")
    print(f"  本地有但 baostock 无: {len(set(all_local.values()) - bs_codes)} 只（跳过）")
    print(f"  baostock 有但本地无: {len(bs_codes - set(all_local.values()))} 只")

    # Step 4: 初始化 DB
    print("\n[4/5] 初始化数据库...")
    init_db()

    # Step 5: 解析 + 写入
    print("\n[5/5] 解析并导入...")
    conn = sqlite3.connect(DB_PATH)

    total_stocks = 0
    total_records = 0
    skip_count = 0
    batch = []

    all_matched_files = [(fname, code) for fname, code in all_local.items() if code in matched]
    sh_files = [(f, c) for f, c in all_matched_files if f.startswith('sh/')]
    sz_files = [(f, c) for f, c in all_matched_files if f.startswith('sz/')]

    for label, zip_path, files in ("上海", "/root/sh.zip", sh_files), ("深圳", "/root/sz.zip", sz_files):
        print(f"\n  ── {label} ({len(files)} 只) ──")
        stock_count = 0
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for i, (fname, code) in enumerate(files):
                try:
                    with zf.open(fname) as f:
                        raw = f.read()
                    records = parse_day_bytes(raw, code)
                    if records:
                        batch.extend(records)
                        stock_count += 1
                except Exception:
                    skip_count += 1

                if len(batch) >= 50000:
                    batch_insert(conn, batch)
                    total_records += len(batch)
                    total_stocks += stock_count
                    stock_count = 0
                    batch = []

                if (i + 1) % 1000 == 0:
                    print(f"  {label}: {i+1}/{len(files)} 文件已处理", flush=True)

        if batch:
            batch_insert(conn, batch)
            total_stocks += stock_count
            total_records += len(batch)
            batch = []

        print(f"  {label} 完成: {stock_count} 只股票")

    conn.close()

    # 验证
    print("\n[验证]")
    conn = sqlite3.connect(DB_PATH)
    sc = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    dc = conn.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]
    mc = conn.execute("SELECT COUNT(DISTINCT code) FROM stock_daily").fetchone()[0]
    rng = conn.execute("SELECT MIN(date), MAX(date) FROM stock_daily").fetchone()
    conn.close()
    print(f"  stocks 表: {sc} 只")
    print(f"  stock_daily: {dc:,} 条行情")
    print(f"  有行情的股票: {mc} 只")
    print(f"  日期范围: {rng[0]} ~ {rng[1]}")
    print(f"  跳过文件: {skip_count} 个")


if __name__ == "__main__":
    main()
