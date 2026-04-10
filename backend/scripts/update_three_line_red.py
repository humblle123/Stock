"""
三线红跟踪表每日更新脚本
每日 run.py 执行完后调用一次
"""
import sqlite3, json, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stocks.db')
REPORT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'latest_report.json')

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def update_three_line_red():
    today = get_today()

    # 读取今日三线红列表
    with open(REPORT_PATH, encoding='utf-8') as f:
        report = json.load(f)

    s3_signals = report.get('s3', [])
    today_codes = {s['code'] for s in s3_signals}
    code_name_map = {s['code']: s.get('name', '') for s in s3_signals}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 把之前在榜但今天不在的 → is_current=0, consecutive_days=0
    cur.execute("SELECT code FROM three_line_red WHERE is_current=1")
    previously_current = {row[0] for row in cur.fetchall()}
    exited = previously_current - today_codes
    if exited:
        cur.execute(
            "UPDATE three_line_red SET is_current=0, consecutive_days=0, last_updated_date=? WHERE code IN ({})".format(
                ','.join('?' * len(exited))),
            [today] + list(exited)
        )
        print(f"[三线红] 今日退出 {len(exited)} 只: {sorted(exited)[:5]}...")

    # 2. 处理今日在榜的股票
    for code in today_codes:
        name = code_name_map.get(code, '')
        cur.execute("SELECT * FROM three_line_red WHERE code=?", (code,))
        row = cur.fetchone()

        if row is None:
            # 新加入：首次加入
            cur.execute("""
                INSERT INTO three_line_red
                    (code, name, first_added_date, consecutive_days, cumulative_days,
                     entry_count, last_added_date, last_updated_date, is_current)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, today, 1, 1, 1, today, today, 1))
            print(f"[三线红] 新加入 {code} {name}")

        elif row[8] == 0:  # is_current == 0，之前退出过再进入
            # 重入：进入次数+1，连续天数重置，累计天数累加
            old_cumulative = row[3]  # cumulative_days
            old_entry_count = row[4]  # entry_count
            cur.execute("""
                UPDATE three_line_red SET
                    name=?,
                    consecutive_days=1,
                    cumulative_days=cumulative_days+1,
                    entry_count=entry_count+1,
                    last_added_date=?,
                    last_updated_date=?,
                    is_current=1
                WHERE code=?
            """, (name, today, today, code))
            print(f"[三线红] 重入 {code} {name} (第{old_entry_count+1}次)")

        else:
            # 继续在榜：连续天数+1，累计天数+1
            cur.execute("""
                UPDATE three_line_red SET
                    name=?,
                    consecutive_days=consecutive_days+1,
                    cumulative_days=cumulative_days+1,
                    last_updated_date=?,
                    is_current=1
                WHERE code=?
            """, (name, today, code))

    conn.commit()

    # 验证
    cur.execute("SELECT COUNT(*) FROM three_line_red WHERE is_current=1")
    current_count = cur.fetchone()[0]
    print(f"[三线红] 更新完成，当前在榜 {current_count} 只 ({today})")
    conn.close()

if __name__ == '__main__':
    update_three_line_red()
