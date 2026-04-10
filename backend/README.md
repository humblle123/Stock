# 选股系统 (Stock Screener)

A股自动化选股系统，基于技术面指标（RPS/KDJ/月线反转）筛选强势股票，支持 Web 图表查看。

---

## 目录结构

```
stock-screener/
├── app.py                      # 🌐 Web 服务（FastAPI + Plotly）：K线图/简报API
├── engine.py                   # ⚙️  选股引擎：加载数据、调度策略、生成简报
├── config.py                   # 🔧  配置项：数据源、策略开关、推送时间
├── run.py                      # 🚀  入口脚本：运行全流程（策略→简报→跟踪表）
├── requirements.txt            # 📦  Python 依赖
│
├── data/
│   ├── sqlite_store.py         # 🗄️  SQLite 存储层（表结构/读写接口）
│   ├── data_fetcher.py         # 🌐  数据获取层（yfinance，备用）
│   └── stocks.db               # 💾  SQLite 数据库文件
│
├── strategies/
│   ├── base.py                 # 🧩  策略基类（抽象接口）
│   └── technical.py            # 📊  四种技术面策略实现
│
├── schemas/
│   └── models.py               # 📋  Pydantic 数据模型（StockSignal / DailyBriefing）
│
├── scripts/
│   ├── update_three_line_red.py   # 🔴  三线红跟踪表每日更新
│   ├── update_kd1_table.py         # 🟠  KD1 一线红跟踪表每日更新
│   ├── rebuild_db.py               # 🔨  重建数据库（清空重装）
│   ├── import_tdx_day.py          # 📁  导入通达信 .day 文件
│   ├── fetch_industry.py          # 🏭  抓取行业分类
│   └── download_all_history.py   # ⬇️  批量下载全市场历史数据
│
└── logs/                          # 📝  各环节运行日志
```

---

## 核心文件说明

### `run.py` — 入口
执行完整选股流程，调用顺序：

1. `engine.run()` — 执行选股策略
2. 生成 `latest_report.json` — 供前端读取
3. `update_three_line_red()` — 更新三线红跟踪表
4. `update_kd1_table()` — 更新 KD1 跟踪表

```bash
python run.py
```

### `engine.py` — 选股引擎

- 预计算全市场 RPS 相对排名矩阵（一次性计算，多策略共享）
- 过滤 ST 股、债转股
- 按策略分发筛选任务

**数据流向：**
```
SQLite → engine 预计算 RPS → 各策略 screen() → DailyBriefing → latest_report.json
```

### `app.py` — Web 服务（端口 8765）

提供以下 API：

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/report` | GET | 今日选股简报（扁平化 JSON） |
| `/api/kline/{code}` | GET | 单只股票原始 K 线数据 |
| `/api/three-line-red` | GET | 三线红跟踪报表 |
| `/api/kd1-table` | GET | KD1 一线红跟踪报表 |

启动：
```bash
python app.py
```

### `strategies/technical.py` — 四种技术面策略

| 策略 | 代码 | 核心条件 |
|------|------|----------|
| **b1 强势突破** | `technical` | J < 18 且收盘 > 多空线 且 多头线 > 空头线 |
| **s2 月线反转** | `s2` | 站上年线 + 30日内50日新高 + RPS50 ≥ 85 |
| **s3 RPS三线红** | `s3` | RPS50>90 AND RPS120>93 AND RPS250>95，距250日高点<15% |
| **kd1 一线红** | `kd1` | 任一RPS>95 且 距250日高点<40% |

> RPS = 相对价格强度（0~100），由 engine 预计算全市场排名

### `data/sqlite_store.py` — 存储层

- **stocks 表**：`code / name / market`
- **stock_daily 表**：`code / date / open / high / low / close / volume / up`
- **three_line_red 表**：三线红跟踪（连续天数/累计天数/重入次数）
- **kd1_table 表**：KD1 跟踪（状态/退出日期）

---

## 前端（React）

前端为独立项目，位于 `/root/ai-projects/stock-board/`，构建后部署在 `http://43.133.250.116:8765/app/`

---

## 数据更新频率

| 数据 | 更新方式 |
|------|----------|
| 日线行情 | akshare 白名单增量每日更新 |
| 三线红/KD1 跟踪表 | 随 `run.py` 每日收盘后更新 |
| 选股简报 | 收盘后运行 `run.py` 生成 |

---

## 已知限制

- 约 9 只停牌股数据更新失败，已接受为可接受的技术局限
- 进程偶发被系统 kill，建议在非交易时段（10:00 前后）运行
