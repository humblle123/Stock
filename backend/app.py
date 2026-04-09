"""
Stock Chart Web Service (按需缓存优化版)
运行: python app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import json, jinja2
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR   = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES  = BASE_DIR / "templates"
DIST_DIR   = Path(BASE_DIR.parent) / "stock-board" / "dist"   # React build
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES.mkdir(exist_ok=True)

app = FastAPI(title="Stock Charts")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# React 前端 build
# - StaticFiles 精确挂载到 /app/assets（仅资源文件）
# - 非资源路径统一返回 index.html（SPA 路由由前端接管）
DIST_DIR = Path(BASE_DIR.parent) / "stock-board" / "dist"
if DIST_DIR.exists():
    app.mount("/app/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="dist-assets")
    print(f"[前端] React build 已挂载到 /app/assets")

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES)),
    autoescape=jinja2.select_autoescape(['html', 'xml']),
)

DB_PATH = os.path.join(BASE_DIR, "data", "stocks.db")

# ─── 缓存 ─────────────────────────────────────────────────────────────────────
_cache_lock  = Lock()
_chart_cache = {}   # code → computed indicators dict
_rps_cache   = {}   # code → {rps5, rps10, ...}


def _vector_rps(close: np.ndarray, period: int) -> float | None:
    """向量化的单股 RPS：O(n) 利用 pandas shift"""
    if len(close) <= period + 1:
        return None
    try:
        s = pd.Series(close)
        rets = (s / s.shift(period) - 1).dropna() * 100
        if rets.empty:
            return None
        curr = float(rets.iloc[-1])
        pct  = float((rets < curr).sum() / len(rets) * 100)
        return round(pct, 2)
    except Exception:
        return None


def _get_indicators(code: str) -> dict:
    """有缓存用缓存，否则计算并缓存"""
    with _cache_lock:
        if code in _chart_cache:
            return _chart_cache[code]

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT date, open, high, low, close, volume, up
        FROM stock_daily
        WHERE code=? AND date >= date('now', '-600 days')
        ORDER BY date ASC
    """, conn, params=(code,))
    conn.close()

    if df.empty or len(df) < 120:
        raise HTTPException(404, "数据不足")

    df["date"] = pd.to_datetime(df["date"])
    close = df["close"].values.astype(float)
    high  = df["high"].values.astype(float)
    low   = df["low"].values.astype(float)
    n     = len(close)

    # ── MA ──────────────────────────────────────────────────────────────────
    def ma(p):
        r = np.full(n, np.nan)
        for i in range(p - 1, n):
            r[i] = close[i - p + 1:i + 1].mean()
        return r

    ma5, ma20, ma60, ma120, ma250 = ma(5), ma(20), ma(60), ma(120), ma(250)

    # ── KDJ ─────────────────────────────────────────────────────────────────
    N = 9
    rsv = np.full(n, np.nan)
    for i in range(N - 1, n):
        ll = low[i - N + 1:i + 1].min()
        hh = high[i - N + 1:i + 1].max()
        rsv[i] = 50 if hh == ll else (close[i] - ll) / (hh - ll) * 100

    K = np.full(n, np.nan)
    D = np.full(n, np.nan)
    w = 1.0 / 3
    K[N - 1] = D[N - 1] = 50
    for i in range(N, n):
        K[i] = rsv[i] * w + K[i - 1] * (1 - w)
        D[i] = K[i] * w + D[i - 1] * (1 - w)
    J = 3 * K - 2 * D

    # ── RPS（按需计算，不预热）──────────────────────────────────────────────
    rps = {}
    for p in [5, 10, 15, 20, 50, 120, 250]:
        with _cache_lock:
            if code not in _rps_cache:
                _rps_cache[code] = {}
        val = _vector_rps(close, p)
        with _cache_lock:
            _rps_cache[code][f"rps{p}"] = val
        rps[f"rps{p}"] = val

    result = dict(
        close=close, high=high, low=low,
        up=df["up"].values.astype(float),
        volume=df["volume"].values.astype(float),
        dates=df["date"].dt.strftime("%Y-%m-%d").tolist(),
        ma5=ma5, ma20=ma20, ma60=ma60, ma120=ma120, ma250=ma250,
        K=K, D=D, J=J,
        rps=rps,
        df=df,
    )

    with _cache_lock:
        _chart_cache[code] = result
    return result


def _get_info(code: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT code, name, market, industry FROM stocks WHERE code=?", (code,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"code": row[0], "name": row[1], "market": row[2], "industry": row[3] or "未知"}


def _build_chart_json(code: str) -> str:
    d = _get_indicators(code)
    info = _get_info(code)

    close  = d["close"]
    high   = d["high"]
    low    = d["low"]
    up     = d["up"]
    volume = d["volume"]
    dates  = d["dates"]
    ma5, ma20, ma60, ma120, ma250 = d["ma5"], d["ma20"], d["ma60"], d["ma120"], d["ma250"]
    K, D, J = d["K"], d["D"], d["J"]
    rps     = d["rps"]

    colors = ["#ef5350" if u > 0 else "#26a69a" if u < 0 else "#9e9e9e" for u in up]

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.50, 0.20, 0.20, 0.10],
        subplot_titles=("", "KDJ", "RPS排名", "成交量"),
    )

    # K线
    fig.add_trace(go.Candlestick(
        x=dates, open=d["df"]["open"].values,
        high=high, low=low, close=close,
        name="OHLC",
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        increasing_fillcolor="#ef5350",  decreasing_fillcolor="#26a69a",
    ), row=1, col=1)

    # 均线
    for ma_arr, name, color in [
        (ma5,   "MA5",   "#f5d300"),
        (ma20,  "MA20",  "#ff7800"),
        (ma60,  "MA60",  "#e91e63"),
        (ma120, "MA120", "#9c27b0"),
        (ma250, "MA250", "#3f51b5"),
    ]:
        fig.add_trace(go.Scatter(x=dates, y=ma_arr, mode="lines",
            name=name, line=dict(width=1.2, color=color), hoverinfo="skip",
        ), row=1, col=1)

    # KDJ
    fig.add_trace(go.Scatter(x=dates, y=K, name="K", hoverinfo="y+name",
        line=dict(color="#9c27b0", width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=dates, y=D, name="D", hoverinfo="y+name",
        line=dict(color="#ff9800", width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=dates, y=J, name="J", hoverinfo="y+name",
        line=dict(color="#2196f3", width=1.2),
        fill="tozeroy", fillcolor="rgba(33,150,243,0.08)"), row=2, col=1)
    fig.add_hline(y=80, line_dash="dash", line_color="rgba(255,50,50,0.4)", row=2, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="rgba(50,200,50,0.4)", row=2, col=1)

    # RPS（只看最后值，节省渲染开销）
    for period, name, color in [
        (50,  "RPS50",  "#e91e63"),
        (120, "RPS120", "#ff9800"),
        (250, "RPS250", "#2196f3"),
    ]:
        val = rps.get(f"rps{period}")
        if val and not np.isnan(val):
            y_arr = np.full(len(dates), np.nan)
            y_arr[-1] = val
            fig.add_trace(go.Scatter(x=dates, y=y_arr, name=f"{name}={val:.0f}",
                hoverinfo="name", line=dict(color=color, width=2.5),
            ), row=3, col=1)
        else:
            fig.add_trace(go.Scatter(x=dates, y=[np.nan]*len(dates), name=name,
                hoverinfo="name", line=dict(color=color, width=1, dash="dot"),
                mode="lines"), row=3, col=1)
    fig.add_hline(y=90, line_dash="dash", line_color="rgba(255,50,50,0.4)", row=3, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="rgba(100,100,100,0.3)", row=3, col=1)

    # 成交量
    fig.add_trace(go.Bar(x=dates, y=volume, name="成交量",
        marker_color=colors, hoverinfo="y+name"), row=4, col=1)

    last_close = float(close[-1])
    last_up    = float(up[-1])
    pct_str    = f"+{last_up:.2f}%" if last_up >= 0 else f"{last_up:.2f}%"
    price_color = "#ef5350" if last_up >= 0 else "#26a69a"

    fig.update_layout(
        title=dict(
            text=f"<b>{info['name']}</b>({code})  "
                 f"<span style='color:{price_color}'>{last_close:.2f}</span>  "
                 f"<span style='color:{price_color}'>{pct_str}</span>  "
                 f"<span style='font-size:12px;color:#888'>{info.get('industry','')}</span>",
            x=0.5, xanchor="center", font=dict(size=15),
        ),
        template="plotly_dark", height=860,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e",
        font=dict(color="#cccccc"),
    )
    for r in [1, 2, 3, 4]:
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", row=r, col=1)
    fig.update_xaxes(showticklabels=True, gridcolor="rgba(255,255,255,0.05)", row=4, col=1)

    return fig.to_json()


# ─── 路由 ─────────────────────────────────────────────────────────────────────
def render(name: str, **ctx):
    def to_dict(v):
        if hasattr(v, 'model_dump'):
            return to_dict(v.model_dump())
        elif isinstance(v, (list, tuple)):
            return [to_dict(i) for i in v]
        elif isinstance(v, dict):
            return {k: to_dict(val) for k, val in v.items()}
        return v
    return jinja_env.get_template(name).render(**{k: to_dict(v) for k, v in ctx.items()})


def get_signals() -> list[dict]:
    p = BASE_DIR / "data" / "latest_report.json"
    if not p.exists():
        return []
    try:
        with open(p) as f:
            data = json.load(f)
        out = []
        for sec in ["technical", "s2", "s3", "kd1"]:
            for s in data.get(sec, []):
                s = dict(s); s["section"] = sec
                out.append(s)
        return out
    except Exception:
        return []








@app.get("/api/report")
async def api_report():
    """选股简报扁平化 JSON（供 React 前端，含今日收盘价）"""
    p = BASE_DIR / "data" / "latest_report.json"
    if not p.exists():
        return JSONResponse({"date": "", "signals": []})
    with open(p) as f:
        raw = json.load(f)

    # 批量读取今日收盘价
    all_codes = set()
    for sec in ["technical", "s2", "s3", "kd1"]:
        for s in raw.get(sec, []):
            all_codes.add(str(s.get("code", "")))
    if all_codes:
        conn = sqlite3.connect(DB_PATH)
        placeholders = ",".join(["?"] * len(all_codes))
        today_max = conn.execute(
            "SELECT MAX(date) FROM stock_daily"
        ).fetchone()[0] or ""
        rows = conn.execute(
            f"SELECT code, close, up FROM stock_daily "
            f"WHERE code IN ({placeholders}) AND date = ?",
            list(all_codes) + [today_max]
        ).fetchall()
        price_map = {code: {"price": close_, "up": up_}
                     for code, close_, up_ in rows}
        conn.close()
    else:
        price_map = {}

    flat = []
    for sec in ["technical", "s2", "s3", "kd1"]:
        for s in raw.get(sec, []):
            s2 = dict(s)
            s2["section"] = sec
            code = str(s2.get("code", ""))
            if code in price_map:
                s2["price"] = price_map[code]["price"]
                s2["up"]    = price_map[code]["up"]
            flat.append(s2)
    return JSONResponse({"date": raw.get("date", ""), "signals": flat})







@app.get("/api/kline/{code}")
async def api_kline(code: str):
    """原始 K 线数据（供 React ECharts 渲染）"""
    info = _get_info(code)
    if not info:
        return JSONResponse({"error": "not found"}, status_code=404)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume, up
           FROM stock_daily
           WHERE code=? AND date >= date('now', '-600 days')
           ORDER BY date ASC""",
        (code,)
    ).fetchall()
    conn.close()
    candles = [
        {
            "date":   r[0],
            "open":   float(r[1]),
            "high":   float(r[2]),
            "low":    float(r[3]),
            "close":  float(r[4]),
            "volume": float(r[5]),
            "up":     float(r[6]) if r[6] is not None else 0.0,
        }
        for r in rows
    ]
    return JSONResponse({"code": code, "info": info, "candles": candles})


@app.get("/api/three-line-red")
def three_line_red_report():
    """三线红跟踪报表"""
    import sqlite3
    conn = sqlite3.connect(str(Path(__file__).parent / "data" / "stocks.db"))
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, first_added_date, consecutive_days,
               cumulative_days, entry_count, last_added_date, is_current
        FROM three_line_red
        ORDER BY consecutive_days DESC, cumulative_days DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = [
        {
            "code":            r[0],
            "name":            r[1],
            "first_added_date": r[2],
            "consecutive_days": r[3],
            "cumulative_days":  r[4],
            "entry_count":      r[5],
            "last_added_date":  r[6],
            "is_current":       r[7],
        }
        for r in rows
    ]
    return JSONResponse({"data": data})


@app.get("/api/kd1-table")
def kd1_table_report():
    """KD1 一线红跟踪报表"""
    import sqlite3
    conn = sqlite3.connect(str(Path(__file__).parent / "data" / "stocks.db"))
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, first_date, last_date,
               consec_days, total_days, times, status, exit_date
        FROM kd1_table
        ORDER BY status='active' DESC, consec_days DESC, total_days DESC
    """)
    rows = cur.fetchall()
    conn.close()
    data = [
        {
            "code":         r[0],
            "name":         r[1],
            "first_date":   r[2],
            "last_date":    r[3],
            "consec_days":  r[4],
            "total_days":   r[5],
            "times":        r[6],
            "status":       r[7],
            "exit_date":    r[8],
        }
        for r in rows
    ]
    return JSONResponse({"data": data})


# ── SPA 兜底：所有未匹配路径都返回 index.html（交给 React Router） ───────────
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """非 API 路径 → 返回 React index.html，实现客户端路由"""
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        html = index_path.read_text()
        # 注入 <base href="/app/">，让相对路径资源从 /app/assets 加载
        if '<base' not in html:
            base_tag = '<base href="/app/">\n'
        else:
            base_tag = ''
        body_close = html.find('</body>')
        if body_close != -1 and base_tag:
            html = html[:body_close] + base_tag + html[body_close:]
        return HTMLResponse(html)
    raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("📈 Stock Charts 启动 (按需缓存版)")
    print("   http://localhost:8765")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)
