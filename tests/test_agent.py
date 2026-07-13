from ad_optimizer.client.mock_client import MockAdClient
from ad_optimizer.agent.optimizer_agent import OptimizerAgent
from ad_optimizer.config import load_config
from ad_optimizer.strategies.base import ActionType


def test_agent_dry_run():
    c = MockAdClient()
    agent = OptimizerAgent(c, load_config())
    rep = agent.run(0, "2026-07-01", "2026-07-07", revenue_map=c.revenue_cents_map(), dry_run=True)
    assert rep.dry_run
    assert len(rep.actions) > 0
    assert rep.executed == []


def test_agent_execute():
    c = MockAdClient()
    agent = OptimizerAgent(c, load_config())
    rep = agent.run(0, "2026-07-01", "2026-07-07", revenue_map=c.revenue_cents_map(), dry_run=False)
    pause_ids = [a.target_id for a in rep.actions if a.action_type.value == "PAUSE_ADGROUP"]
    for pid in pause_ids:
        ag = next(a for a in c.get_adgroups(0) if a.adgroup_id == pid)
        assert ag.configured_status == "AD_STATUS_SUSPEND"

    adj = [a for a in rep.actions if a.action_type.value == "ADJUST_BUDGET"]
    for a in adj:
        ag = next(x for x in c.get_adgroups(0) if x.adgroup_id == a.target_id)
        assert ag.daily_budget == a.params["new_budget_cents"]


def test_safeguard_pause_cap():
    c = MockAdClient()
    cfg = load_config()
    cfg["strategies"]["loss_cutting"]["max_pause_ratio"] = 0.0  # 不允许任何暂停
    agent = OptimizerAgent(c, cfg)
    rep = agent.run(0, "2026-07-01", "2026-07-07", revenue_map=c.revenue_cents_map(), dry_run=True)
    pauses = [a for a in rep.actions if a.action_type.value == "PAUSE_ADGROUP"]
    assert len(pauses) == 0
