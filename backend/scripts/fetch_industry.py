"""
用申万一级行业分类，给 stocks 表补充行业字段
31 个行业，逐个调 akshare stock_board_industry_cons_em
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import akshare as ak

DB = "/root/ai-projects/stock-screener/data/stocks.db"

SW_INDUSTRIES = [
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子",
    "汽车", "家用电器", "食品饮料", "纺织服饰", "轻工制造",
    "医药生物", "公用事业", "交通运输", "房地产", "商贸零售",
    "社会服务", "银行", "非银金融", "综合", "建筑材料",
    "建筑装饰", "电力设备", "机械设备", "国防军工", "计算机",
    "传媒", "通信", "煤炭", "石油石化", "环保", "美容护理"
]

def fetch_all_industry_mapping() -> dict[str, str]:
    """返回 {code: 行业名}"""
    mapping = {}
    total = len(SW_INDUSTRIES)
    for i, industry in enumerate(SW_INDUSTRIES):
        print(f"  [{i+1}/{total}] {industry}...", end=" ", flush=True)
        for attempt in range(3):
            try:
                time.sleep(0.5)
                cons = ak.stock_board_industry_cons_em(symbol=industry)
                if cons is not None and len(cons) > 0:
                    col_name = '代码' if '代码' in cons.columns else cons.columns[0]
                    for _, row in cons.iterrows():
                        raw = str(row[col_name])
                        code = raw.replace(".SH", "").replace(".SZ", "").replace("sh", "").replace("sz", "")
                        if code.isdigit() and len(code) == 6:
                            mapping[code] = industry
                    print(f"{len(cons)}只", end="")
                    break
            except Exception as e:
                if attempt == 2:
                    print(f"失败: {e}", end="")
                time.sleep(2)
        print()
    return mapping


def main():
    print("=" * 50)
    print("获取申万行业分类...")
    print("=" * 50)

    mapping = fetch_all_industry_mapping()
    print(f"\n获取到 {len(mapping)} 只股票的行业")

    # 写入 DB
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 新增 industry 字段（若无）
    cur.execute("PRAGMA table_info(stocks)")
    cols = [r[1] for r in cur.fetchall()]
    if "industry" not in cols:
        cur.execute("ALTER TABLE stocks ADD COLUMN industry TEXT DEFAULT ''")
        print("新增 industry 字段")

    # 批量更新
    updated = 0
    for code, industry in mapping.items():
        cur.execute("UPDATE stocks SET industry=? WHERE code=?", (industry, code))
        if cur.rowcount > 0:
            updated += 1
    conn.commit()

    # 验证
    filled = conn.execute("SELECT COUNT(*) FROM stocks WHERE industry != ''").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    samples = conn.execute(
        "SELECT code, name, industry FROM stocks WHERE industry != '' LIMIT 5"
    ).fetchall()
    conn.close()

    print(f"\n更新了 {updated} 条行业")
    print(f"stocks 表: {filled}/{total} 只有行业")
    print("样本:")
    for code, name, ind in samples:
        print(f"  {code} {name} → {ind}")


if __name__ == "__main__":
    main()
