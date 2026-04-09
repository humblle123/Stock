"""
KD1 一线红跟踪表每日更新脚本
从 latest_report.json 读取 kd1 信号，逻辑与 update_three_line_red.py 完全一致
"""
import sqlite3, json, os
from datetime import datetime

DB_PATH   = os.path.join(os.path.dirname(__file__), '..', 'data', 'stocks.db')
TABLE     = "kd1_table"
REPORT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'latest_report.json')

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def init_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            code TEXT PRIMARY KEY, name TEXT,
            first_date TEXT, last_date TEXT,
            consec_days INTEGER DEFAULT 1, total_days INTEGER DEFAULT 1,
            times INTEGER DEFAULT 1, status TEXT DEFAULT 'active', exit_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def update_kd1_table():
    today = get_today()

    with open(REPORT_PATH, encoding='utf-8') as f:
        report = json.load(f)

    kd1_signals = report.get('kd1', [])
    today_codes = {s['code'] for s in kd1_signals}
    code_name_map = {s['code']: s.get('name', '') for s in kd1_signals}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 之前在榜但今天不在 → 退出
    cur.execute(f"SELECT code FROM {TABLE} WHERE status='active'")
    previously_active = {row[0] for row in cur.fetchall()}
    exited = previously_active - today_codes
    if exited:
        placeholders = ','.join('?' * len(exited))
        cur.execute(
            f"UPDATE {TABLE} SET status='exit', exit_date=?, consec_days=0 WHERE code IN ({placeholders})",
            [today] + list(exited)
        )
        print(f"[KD1] 退出 {len(exited)} 只")

    # 今日在榜股票
    for code in today_codes:
        name = code_name_map.get(code, '')
        cur.execute(f"SELECT * FROM {TABLE} WHERE code=?", (code,))
        row = cur.fetchone()

        if row is None:
            cur.execute(f"""
                INSERT INTO {TABLE} (code,name,first_date,last_date,consec_days,total_days,times,status)
                VALUES (?,?,?,?,1,1,1,'active')
            """, (code, name, today, today))
            print(f"[KD1] 新加入 {code} {name}")

        elif row[7] == 'exit':  # 重入
            cur.execute(f"""
                UPDATE {TABLE} SET name=?, first_date=?, last_date=?, consec_days=1,
                    total_days=total_days+1, times=times+1, status='active', exit_date=NULL
                WHERE code=?
            """, (name, today, today, code))
            print(f"[KD1] 重入 {code} {name} (第{row[6]+1}次)")

        else:  # 继续在榜
            cur.execute(f"""
                UPDATE {TABLE} SET name=?, last_date=?, consec_days=consec_days+1,
                    total_days=total_days+1, status='active'
                WHERE code=?
            """, (name, today, code))

    conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE status='active'")
    current_count = cur.fetchone()[0]
    print(f"[KD1] 更新完成，当前在榜 {current_count} 只 ({today})")
    conn.close()

if __name__ == '__main__':
    init_table()
    update_kd1_table()
