"""策略二：预算再分配（Budget Reallocation）。

在同一个 campaign 内，将预算从「低效计划」抽调到「高效计划」：
- 以 ROAS 为准绳，ROAS ≥ 目标 视为 winner，ROAS < 目标×阈值 视为 loser；
- 从 loser 抽走 shift_ratio 比例的预算（受单 campaign 上限、总比例上限约束）；
- 抽出的预算按 winner 当前预算占比分配，放大优质流量；
- 每个计划预算不低于 min_daily_budget 下限。

护栏：已判定暂停的计划不参与再分配（由 Agent 去重兜底）。
"""
from .base import Strategy, Action, ActionType
from ..analysis.metrics import compute_metrics
from ..utils.money import cents_to_yuan


class BudgetReallocationStrategy(Strategy):
    name = "budget_reallocation"

    def analyze(self, ctx):
        if not self.enabled:
            return []
        cfg = ctx.config["strategies"]["budget_reallocation"]
        targets = ctx.config["targets"]
        min_spend = cfg["min_observation_spend_cents"]
        min_budget = targets["min_daily_budget_cents"]
        target_roas = targets["target_roas"]
        loser_roas_th = target_roas * cfg["loser_roas_threshold"]
        shift_ratio = cfg["shift_ratio"]
        max_shift = cfg["max_shift_cents_per_campaign"]

        actions = []
        for camp in ctx.campaigns:
            ags = [a for a in ctx.adgroups if a.campaign_id == camp.campaign_id and a.is_active]
            scored = []
            for ag in ags:
                rpt = ctx.reports_by_ag.get(ag.adgroup_id)
                if not rpt or rpt.cost < min_spend or rpt.conversion == 0:
                    scored.append((ag, None, "unknown"))
                    continue
                m = compute_metrics(rpt.cost, rpt.impression, rpt.click, rpt.conversion, rpt.revenue)
                if m.roas >= target_roas:
                    scored.append((ag, m, "winner"))
                elif m.roas < loser_roas_th:
                    scored.append((ag, m, "loser"))
                else:
                    scored.append((ag, m, "mid"))

            winners = [x for x in scored if x[2] == "winner"]
            losers = [x for x in scored if x[2] == "loser"]
            if not winners or not losers:
                continue

            total_budget = sum(ag.daily_budget for ag, _, _ in scored)
            loser_budget = sum(ag.daily_budget for ag, _, _ in losers)
            if loser_budget <= 0:
                continue
            shiftable = min(loser_budget * shift_ratio, max_shift, total_budget * cfg["max_total_shift_ratio"])
            if shiftable <= 0:
                continue

            # 1) 从 losers 抽预算，记录实际抽走额
            actual_shifted = 0
            for ag, m, _ in losers:
                reducible = ag.daily_budget - min_budget
                if reducible <= 0:
                    continue
                share = shiftable * (ag.daily_budget / loser_budget)
                reduction = min(reducible, int(share))
                if reduction <= 0:
                    continue
                new_b = ag.daily_budget - reduction
                actions.append(Action(
                    ActionType.ADJUST_BUDGET, ag.adgroup_id, campaign_id=ag.campaign_id,
                    params={"old_budget_cents": ag.daily_budget, "new_budget_cents": new_b, "reason": "loser"},
                    rationale=f"ROAS {m.roas:.2f} 低于目标 {target_roas:.1f}，下调预算集中给优质计划",
                    severity="medium", expected_saving_cents=reduction,
                ))
                actual_shifted += reduction

            # 2) 把实际抽走的预算分配给 winners
            if actual_shifted > 0 and winners:
                winner_budget = sum(ag.daily_budget for ag, _, _ in winners)
                if winner_budget > 0:
                    for ag, m, _ in winners:
                        add = int(actual_shifted * (ag.daily_budget / winner_budget))
                        if add <= 0:
                            continue
                        new_b = ag.daily_budget + add
                        actions.append(Action(
                            ActionType.ADJUST_BUDGET, ag.adgroup_id, campaign_id=ag.campaign_id,
                            params={"old_budget_cents": ag.daily_budget, "new_budget_cents": new_b, "reason": "winner"},
                            rationale=f"ROAS {m.roas:.2f} 优于目标，加预算放大优质流量",
                            severity="medium",
                        ))
        return actions
