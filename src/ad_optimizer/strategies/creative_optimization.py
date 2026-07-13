"""策略三：创意素材优化（Creative Optimization）。

在广告计划内部对比创意表现：
- 同一计划下若有 ≥2 个创意且均有足够曝光，按 CPA 排序；
- 最差创意的 CPA 显著高于最优创意（超过 max_cpa_multiplier 倍）时，
  建议暂停最差创意、复用最优创意，提升整体转化效率；
- 单一创意或缺少创意层级数据时，给出「补充素材/文案变体」的建议。

文案变体生成由 LLMAdvisor 提供（无 LLM 时回退模板）。
"""
from .base import Strategy, Action, ActionType
from ..utils.money import cents_to_yuan


class CreativeOptimizationStrategy(Strategy):
    name = "creative_optimization"

    def analyze(self, ctx):
        if not self.enabled:
            return []
        cfg = ctx.config["strategies"]["creative_optimization"]
        max_cpa_mult = cfg["max_cpa_multiplier"]
        min_impr = cfg["min_impressions"]

        actions = []
        for ag in ctx.adgroups:
            if not ag.is_active:
                continue
            crs = [c for c in ctx.creatives if c.adgroup_id == ag.adgroup_id]
            if len(crs) < 2:
                actions.append(Action(
                    ActionType.ALERT, ag.adgroup_id, campaign_id=ag.campaign_id,
                    params={"suggestion": "补充创意变体/文案"},
                    rationale="仅有一个创意，建议增加素材变体以探索更优表现", severity="low",
                ))
                continue

            perfs = [(c, ctx.creative_reports_by_id.get(c.creative_id)) for c in crs]
            valid = [(c, p) for c, p in perfs if p and p.impression >= min_impr]
            if len(valid) < 2:
                actions.append(Action(
                    ActionType.ALERT, ag.adgroup_id, campaign_id=ag.campaign_id,
                    params={"suggestion": "补充创意层级数据/素材"},
                    rationale="缺少足够创意层级数据，建议更新素材并开启创意报表", severity="low",
                ))
                continue

            valid.sort(key=lambda x: (x[1].conversion_cost if x[1].conversion > 0 else float("inf")))
            best_c, best_p = valid[0]       # 最低 CPA = 最优
            worst_c, worst_p = valid[-1]    # 最高 CPA = 最差
            if worst_p.conversion > 0 and best_p.conversion > 0:
                if worst_p.conversion_cost > best_p.conversion_cost * max_cpa_mult:
                    actions.append(Action(
                        ActionType.ROTATE_CREATIVE, worst_c.creative_id, campaign_id=ag.campaign_id,
                        params={"action": "pause_creative", "best_creative_id": best_c.creative_id,
                                "worst_cpa_cents": worst_p.conversion_cost,
                                "best_cpa_cents": best_p.conversion_cost},
                        rationale=(f"创意 CPA ¥{cents_to_yuan(worst_p.conversion_cost):.0f} 远高于同组最优 "
                                   f"¥{cents_to_yuan(best_p.conversion_cost):.0f}，建议暂停并复用优质创意"),
                        severity="medium",
                    ))
        return actions
