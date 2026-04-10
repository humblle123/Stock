#!/bin/bash
# 股票数据下载进度检查脚本
# 用法: bash check_progress.sh

DB_PATH="/root/ai-projects/stock-screener/data/stocks.db"
LOG_PATH="/root/ai-projects/stock-screener/download.log"

echo "=== 股票数据下载进度 ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ 数据库不存在"
    exit 1
fi

STOCK_COUNT=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()
count = cur.execute('SELECT COUNT(*) FROM stocks').fetchone()[0]
print(count)
conn.close()
")

PRICE_COUNT=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()
count = cur.execute('SELECT COUNT(*) FROM daily_price').fetchone()[0]
print(count)
conn.close()
")

LATEST=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()
latest = cur.execute('SELECT MAX(date) FROM daily_price').fetchone()[0]
print(latest)
conn.close()
")

echo "股票数量: $STOCK_COUNT"
echo "行情记录: $PRICE_COUNT"
echo "最新日期: $LATEST"
echo "--- 最近日志 ---"
tail -5 "$LOG_PATH" 2>/dev/null | grep -E "Failed|成功|完成|Error" | tail -3
