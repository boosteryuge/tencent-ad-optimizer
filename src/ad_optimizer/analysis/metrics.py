"""指标计算与效果评估。

所有金额输入为「分」，输出指标：
- CTR  = 点击 / 曝光
- CPC  = 花费 / 点击（分）
- CVR  = 转化 / 点击
- CPA  = 花费 / 转化（分），无转化时为 inf
- ROAS = 收入 / 花费
- ROI  = (收入 - 花费) / 花费
"""
from dataclasses import dataclass
from typing import Dict, List

from ..client.models import PerformanceReport


@dataclass
class DerivedMetrics:
    ctr: float = 0.0
    cpc: float = 0.0          # 分
    cvr: float = 0.0
    cpa: float = 0.0          # 分
    roas: float = 0.0
    roi: float = 0.0
    has_conversion: bool = False

    @property
    def is_profitable(self) -> bool:
        return self.roas >= 1.0


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_metrics(cost, impression, click, conversion, revenue: float = 0.0) -> DerivedMetrics:
    ctr = safe_div(click, impression)
    cpc = safe_div(cost, click)
    cvr = safe_div(conversion, click)
    cpa = safe_div(cost, conversion) if conversion > 0 else float("inf")
    roas = safe_div(revenue, cost)
    roi = (revenue - cost) / cost if cost else 0.0
    return DerivedMetrics(ctr=ctr, cpc=cpc, cvr=cvr, cpa=cpa, roas=roas, roi=roi, has_conversion=conversion > 0)


def aggregate_reports(
    reports: List[PerformanceReport], revenue_map: Dict[int, float] = None
) -> Dict[int, PerformanceReport]:
    """按广告组聚合多日报表为单条。revenue_map: adgroup_id -> 收入(分)。"""
    revenue_map = revenue_map or {}
    agg: Dict[int, dict] = {}
    for r in reports:
        if r.adgroup_id not in agg:
            agg[r.adgroup_id] = {"cost": 0.0, "impression": 0, "click": 0, "conversion": 0,
                                 "campaign_id": r.campaign_id}
        a = agg[r.adgroup_id]
        a["cost"] += r.cost
        a["impression"] += r.impression
        a["click"] += r.click
        a["conversion"] += r.conversion
        a["campaign_id"] = r.campaign_id
    out: Dict[int, PerformanceReport] = {}
    for agid, a in agg.items():
        m = compute_metrics(a["cost"], a["impression"], a["click"], a["conversion"],
                            revenue_map.get(agid, 0.0))
        out[agid] = PerformanceReport(
            adgroup_id=agid, campaign_id=a["campaign_id"],
            cost=a["cost"], impression=a["impression"], click=a["click"], conversion=a["conversion"],
            ctr=m.ctr, cpc=m.cpc, conversion_cost=m.cpa if m.has_conversion else 0.0,
            conversion_rate=m.cvr, revenue=revenue_map.get(agid, 0.0),
        )
    return out


def aggregate_creative_reports(
    reports: List[PerformanceReport], revenue_map: Dict[int, float] = None
) -> Dict[int, PerformanceReport]:
    """按创意聚合多日报表为单条（创意层级通常无收入回传）。"""
    agg: Dict[int, dict] = {}
    for r in reports:
        cid = r.creative_id
        if cid not in agg:
            agg[cid] = {"cost": 0.0, "impression": 0, "click": 0, "conversion": 0,
                        "adgroup_id": r.adgroup_id, "campaign_id": r.campaign_id}
        a = agg[cid]
        a["cost"] += r.cost
        a["impression"] += r.impression
        a["click"] += r.click
        a["conversion"] += r.conversion
        a["adgroup_id"] = r.adgroup_id
        a["campaign_id"] = r.campaign_id
    out: Dict[int, PerformanceReport] = {}
    for cid, a in agg.items():
        cpa = safe_div(a["cost"], a["conversion"]) if a["conversion"] > 0 else 0.0
        out[cid] = PerformanceReport(
            adgroup_id=a["adgroup_id"], campaign_id=a["campaign_id"], creative_id=cid,
            cost=a["cost"], impression=a["impression"], click=a["click"], conversion=a["conversion"],
            conversion_cost=cpa,
        )
    return out


def evaluate(m: DerivedMetrics, target_cpa_cents: float, target_roas: float) -> str:
    """健康度分级：good / average / poor。"""
    if not m.has_conversion:
        return "poor"
    if m.cpa <= target_cpa_cents and m.roas >= target_roas:
        return "good"
    if m.cpa > target_cpa_cents * 2 or m.roas < target_roas * 0.5:
        return "poor"
    return "average"
