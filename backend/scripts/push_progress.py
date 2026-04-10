#!/usr/bin/env python3
"""
股票下载进度推送到微信
"""
import sqlite3
import urllib.request
import json
from datetime import datetime

DB_PATH = "/root/ai-projects/stock-screener/data/stocks.db"
GATEWAY_URL = "http://127.0.0.1:32464"
GATEWAY_TOKEN = "9215af8b9e46b4ef2de9610514239443efb42ebe9b7e5dcc"

def get_progress():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    stocks = cur.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    prices = cur.execute("SELECT COUNT(*) FROM daily_price").fetchone()[0]
    latest = cur.execute("SELECT MAX(date) FROM daily_price").fetchone()[0]
    conn.close()
    return stocks, prices, latest

def push_message(text: str):
    """通过 OpenClaw gateway 发送微信消息"""
    payload = json.dumps({
        "action": "send",
        "channel": "openclaw-weixin",
        "message": text
    }).encode("utf-8")
    
    req = urllib.request.Request(
        f"{GATEWAY_URL}/m3kyg8/api/message",
        data=payload,
        headers={
            "Authorization": f"Bearer {GATEWAY_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")

if __name__ == "__main__":
    stocks, prices, latest = get_progress()
    now = datetime.now().strftime("%H:%M")
    msg = f"""📊 股票数据下载进度
⏰ {now}
├─ 股票数量: {stocks} 只
├─ 行情记录: {prices:,} 条
└─ 最新日期: {latest}"""
    
    code, body = push_message(msg)
    print(f"[{now}] 推送结果: {code} - {body}")
