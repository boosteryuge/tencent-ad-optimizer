"""命令行入口。"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from ad_optimizer.config import load_config
from ad_optimizer.client.mock_client import MockAdClient
from ad_optimizer.client.tencent_ads_client import TencentAdsClient
from ad_optimizer.agent.optimizer_agent import OptimizerAgent
from ad_optimizer.llm.advisor import LLMAdvisor
from ad_optimizer.utils.logging import get_logger


def main(argv=None):
    p = argparse.ArgumentParser(description="腾讯广告投放优化师 Agent")
    p.add_argument("--config", default=None, help="YAML 配置文件路径")
    p.add_argument("--account-id", type=int, default=None, help="广告主帐号 id")
    p.add_argument("--days", type=int, default=7, help="统计最近 N 天")
    p.add_argument("--start-date", default=None, help="起始日期 YYYY-MM-DD")
    p.add_argument("--end-date", default=None, help="结束日期 YYYY-MM-DD")
    p.add_argument("--mock", action="store_true", help="使用内置 Mock 数据（无需真实凭证）")
    p.add_argument("--execute", action="store_true", help="真正执行写操作（默认演练 dry-run）")
    p.add_argument("--interactive", action="store_true", help="每个动作交互确认")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--revenue-json", default=None, help="广告组收入映射 JSON，如 {\"2001\":2400.0}")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    if args.account_id:
        cfg["account_id"] = args.account_id
    account_id = cfg["account_id"]
    if not args.mock and not account_id:
        print("错误：未提供 account_id（用 --account-id 或在配置中设置，或加 --mock 用演示数据）", file=sys.stderr)
        sys.exit(2)

    end = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start = args.start_date or (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=args.days - 1)).strftime("%Y-%m-%d")

    revenue_map = {}
    if args.revenue_json:
        revenue_map = {int(k): float(v) * 100 for k, v in json.loads(args.revenue_json).items()}

    logger = get_logger()
    if args.mock:
        client = MockAdClient()
        revenue_map = revenue_map or client.revenue_cents_map()
    else:
        token = os.environ.get(cfg["api"]["access_token_env"], "")
        if not token:
            print(f"错误：环境变量 {cfg['api']['access_token_env']} 未设置", file=sys.stderr)
            sys.exit(2)
        client = TencentAdsClient(
            token, version=cfg["api"]["version"],
            base_url=cfg["api"]["base_url"], timeout=cfg["api"]["timeout"],
            account_id=account_id,
        )

    advisor = LLMAdvisor(cfg.get("llm", {}))
    agent = OptimizerAgent(client, cfg, advisor=advisor, logger=logger)
    dry_run = not args.execute
    report = agent.run(account_id, start, end, revenue_map=revenue_map, dry_run=dry_run, interactive=args.interactive)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(report.summary_text)
        print("=" * 60)
        print(f"模式: {'演练(未真正修改账户)' if dry_run else '执行(已写入)'}")


if __name__ == "__main__":
    main()
