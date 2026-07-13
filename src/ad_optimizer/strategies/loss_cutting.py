"""策略一：止损暂停（Loss Cutting）。

对花费已达观察阈值但仍无正向回报的广告计划，及时暂停以避免持续烧钱：
1) 花费充足但转化数为 0；
2) CPA 超过目标 CPA 的 N 倍；
3) 曝光充足但 CTR 极低（素材/人群错配）。

护栏：花费不足 min_observation_spend 不评判（给计划学习期）。
"""
from .base import Strategy, Action, ActionType
from ..analysis.metrics import compute_metrics
from ..utils.money import cents_to_yuan


class LossCuttingStrategy(Strategy):
    name = "loss_cutting"

    def analyze(self, ctx):
        if not self.enabled:
            return []
        cfg = ctx.config["strategies"]["loss_cutting"]
        targets = ctx.config["targets"]
        min_spend = cfg["min_observation_spend_cents"]
        max_cpa = targets["target_cpa_cents"] * cfg["max_cpa_multiplier"]
        min_impr = cfg["min_impressions"]
        min_ctr = cfg["min_ctr"]

        actions = []
        for ag in ctx.adgroups:
            if not ag.is_active:
                continue
            rpt = ctx.reports_by_ag.get(ag.adgroup_id)
            if not rpt:
                continue
            if rpt.cost < min_spend:          # 观察期/花费不足，跳过
                continue
            m = compute_metrics(rpt.cost, rpt.impression, rpt.click, rpt.conversion, rpt.revenue)
            reasons = []
            if rpt.conversion == 0:
                reasons.append(f"花费 ¥{cents_to_yuan(rpt.cost):.0f} 但转化数为 0")
            elif m.cpa > max_cpa:
                reasons.append(
                    f"CPA ¥{cents_to_yuan(m.cpa):.0f} 超过目标 {cfg['max_cpa_multiplier']} 倍"
                    f"（目标 ¥{cents_to_yuan(targets['target_cpa_cents']):.0f}）"
                )
            if rpt.impression >= min_impr and m.ctr < min_ctr:
                reasons.append(f"CTR {m.ctr*100:.2f}% 低于阈值 {min_ctr*100:.2f}%（素材/人群错配）")
            if reasons:
                actions.append(Action(
                    action_type=ActionType.PAUSE_ADGROUP,
                    target_id=ag.adgroup_id,
                    campaign_id=ag.campaign_id,
                    rationale="；".join(reasons),
                    severity="high",
                    expected_saving_cents=rpt.cost,   # 估算可避免的后续浪费≈近期花费
                ))
        return actions
