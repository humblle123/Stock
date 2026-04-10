#!/bin/bash
# 股票下载进度推送脚本
# 通过 OpenClaw /tools/invoke 发送微信消息

DB="/root/ai-projects/stock-screener/data/stocks.db"
GATEWAY="http://127.0.0.1:32464"
TOKEN="9215af8b9e46b4ef2de9610514239443efb42ebe9b7e5dcc"
TARGET="o9cq805dEui_WCrWRM0ReFaLkJO8@im.wechat"

# 查询数据
RESULT=$(python3 -c "
import sqlite3, json
conn = sqlite3.connect('$DB')
cur = conn.cursor()
stocks = cur.execute('SELECT COUNT(*) FROM stocks').fetchone()[0]
prices = cur.execute('SELECT COUNT(*) FROM daily_price').fetchone()[0]
latest = cur.execute('SELECT MAX(date) FROM daily_price').fetchone()[0]
conn.close()
print(f'{stocks}|{prices}|{latest}')
")
STOCKS=$(echo $RESULT | cut -d'|' -f1)
PRICES=$(echo $RESULT | cut -d'|' -f2)
LATEST=$(echo $RESULT | cut -d'|' -f3)
NOW=$(date '+%H:%M')

MSG="📊 股票下载进度
⏰ $NOW
├─ 股票: $STOCKS 只
├─ 行情: $PRICES 条
└─ 最新: $LATEST"

# 发送消息
curl -sS "$GATEWAY/tools/invoke" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tool\": \"message\",
    \"action\": \"send\",
    \"args\": {
      \"action\": \"send\",
      \"channel\": \"openclaw-weixin\",
      \"target\": \"$TARGET\",
      \"message\": $(echo "$MSG" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")
    }
  }" | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('ok') else f'ERR: {d}')"
