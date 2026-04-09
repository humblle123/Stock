"""
StockScreener — 每日选股简报生成器
运行方式: python run.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import ScreeningEngine
from config import DEFAULT_STRATEGIES
from scripts.update_three_line_red import update_three_line_red


def main():
    print("=" * 40)
    print("StockScreener 选股系统启动")
    print("=" * 40)

    # 初始化引擎
    engine = ScreeningEngine(strategies=DEFAULT_STRATEGIES)

    # 执行筛选
    print("\n[1/2] 执行选股策略...")
    briefing = engine.run()

    # 生成简报
    print("[2/2] 生成简报...")
    report = engine.format_briefing(briefing)

    print("\n" + "=" * 40)
    print("简报内容:")
    print("=" * 40)
    print(report)
    print("=" * 40)

    # 保存 JSON（供 Web 图表服务读取）
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    report_path = os.path.join(os.path.dirname(__file__), "data", "latest_report.json")
    import json
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(briefing.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    print(f"[简报] 已保存至 {report_path}")

    # 更新三线红跟踪表
    print("[三线红] 更新跟踪表...")
    update_three_line_red()

    # 更新 KD1 一线红跟踪表
    print("[KD1] 更新跟踪表...")
    from scripts.update_kd1_table import update_kd1_table, init_table
    init_table()
    update_kd1_table()

    # 返回简报内容（供 cron job 读取）
    return report


if __name__ == "__main__":
    main()
