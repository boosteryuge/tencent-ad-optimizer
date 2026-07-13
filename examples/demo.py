#!/usr/bin/env python3
"""零配置演示：用内置 Mock 数据跑通「观测 -> 分析 -> 决策 -> 报告」全流程。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ad_optimizer.config import load_config
from ad_optimizer.client.mock_client import MockAdClient
from ad_optimizer.agent.optimizer_agent import OptimizerAgent


def main():
    cfg = load_config()
    client = MockAdClient()
    agent = OptimizerAgent(client, cfg)

    print("# 腾讯广告投放优化师 Agent · 演示（Mock 数据，演练模式）\n")
    report = agent.run(
        account_id=0,
        start_date="2026-07-01",
        end_date="2026-07-07",
        revenue_map=client.revenue_cents_map(),
        dry_run=True,
    )
    print(report.summary_text)
    print("\n--- 动作清单 ---")
    for a in report.actions:
        print(" •", a.summary())
    print(f"\n（演练模式：未真正修改账户。加 --execute 才会写入。）")


if __name__ == "__main__":
    main()
