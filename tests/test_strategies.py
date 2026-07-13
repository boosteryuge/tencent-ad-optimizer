from ad_optimizer.client.mock_client import MockAdClient
from ad_optimizer.analysis.metrics import aggregate_reports, aggregate_creative_reports
from ad_optimizer.config import load_config
from ad_optimizer.strategies.base import OptimizationContext, ActionType
from ad_optimizer.strategies.loss_cutting import LossCuttingStrategy
from ad_optimizer.strategies.budget_reallocation import BudgetReallocationStrategy
from ad_optimizer.strategies.creative_optimization import CreativeOptimizationStrategy


def _ctx(client, cfg, start="2026-07-01", end="2026-07-07"):
    ag_rep = client.get_daily_report(0, "REPORT_LEVEL_ADGROUP", start, end)
    cr_rep = client.get_daily_report(0, "REPORT_LEVEL_ADCREATIVE", start, end)
    rba = aggregate_reports(ag_rep, client.revenue_cents_map())
    crbi = aggregate_creative_reports(cr_rep)
    return OptimizationContext(
        account_id=0, campaigns=client.get_campaigns(0), adgroups=client.get_adgroups(0),
        creatives=client.get_adcreatives(0), reports_by_ag=rba,
        creative_reports_by_id=crbi, config=cfg,
    )


def test_loss_cutting_pauses_burners():
    c = MockAdClient()
    ctx = _ctx(c, load_config())
    acts = LossCuttingStrategy(True).analyze(ctx)
    ids = {a.target_id for a in acts}
    assert 2003 in ids   # 零转化
    assert 2005 in ids   # CTR 过低
    assert 2004 not in ids  # 新建、花费不足，被观察期护栏跳过


def test_budget_reallocation():
    c = MockAdClient()
    ctx = _ctx(c, load_config())
    acts = BudgetReallocationStrategy(True).analyze(ctx)
    adj = [a for a in acts if a.action_type == ActionType.ADJUST_BUDGET]
    downs = [a for a in adj if a.params.get("reason") == "loser"]
    ups = [a for a in adj if a.params.get("reason") == "winner"]
    assert downs and ups
    min_b = load_config()["targets"]["min_daily_budget_cents"]
    for a in downs:
        assert a.params["new_budget_cents"] >= min_b


def test_creative_optimization():
    c = MockAdClient()
    ctx = _ctx(c, load_config())
    acts = CreativeOptimizationStrategy(True).analyze(ctx)
    rot = [a for a in acts if a.action_type == ActionType.ROTATE_CREATIVE]
    assert rot  # 2001 下应触发
