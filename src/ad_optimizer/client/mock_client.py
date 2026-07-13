"""内置 Mock 客户端：无需任何凭证即可演示/测试全流程。

覆盖典型场景：
- 2001 优质计划（高 ROAS，预算应上调）
- 2002 低效但非零转化（预算应下调）
- 2003 烧钱零转化（应止损暂停）
- 2004 新建计划（花费不足，观察期护栏跳过）
- 2005 CTR 极低（应止损暂停）
创意层级：2001 下 9001（优）/ 9002（差）-> 触发创意轮换建议。
收入（转化价值）由外部回传，用于 ROAS 计算。
"""
import random
from datetime import datetime, timedelta
from typing import List, Optional

from .base import AdPlatformClient
from .models import Campaign, AdGroup, AdCreative, PerformanceReport

# 广告主外部回传收入（元）。key=adgroup_id
DEFAULT_REVENUE_YUAN = {
    2001: 2400.0,
    2002: 300.0,
    2003: 0.0,
    2004: 0.0,
    2005: 0.0,
}

# 广告组原始表现：(花费元, 曝光, 点击, 转化)
_AG_RAW = {
    2001: (600, 120000, 3000, 40),
    2002: (600, 80000, 1500, 5),
    2003: (400, 60000, 800, 0),
    2004: (50, 5000, 60, 1),
    2005: (400, 200000, 100, 3),
}

# 创意原始表现（仅 2001 提供创意层级数据）：(花费元, 曝光, 点击, 转化)
_CR_RAW = {
    9001: (300, 60000, 1800, 28),
    9002: (300, 60000, 1200, 12),
}


class MockAdClient(AdPlatformClient):
    def __init__(self, revenue_yuan: Optional[dict] = None, seed: int = 42):
        self.revenue_yuan = revenue_yuan or DEFAULT_REVENUE_YUAN
        self.rng = random.Random(seed)
        self._applied_status: dict = {}
        self._applied_budget: dict = {}
        self._build()

    # ---------- 内部构建 ----------
    @staticmethod
    def _split(total: int, n: int) -> List[int]:
        if n <= 0:
            return []
        base = total // n
        rem = total - base * n
        out = [base] * n
        for i in range(rem):
            out[i] += 1
        return out

    def _build(self):
        self.campaigns = [Campaign(1001, "618大促-电商引流", "CAMPAIGN_TYPE_NORMAL")]
        self.adgroups = [
            AdGroup(2001, 1001, "信息流-女装-计划A", "AD_STATUS_NORMAL", "", 50000, "2026-06-01"),
            AdGroup(2002, 1001, "信息流-男装-计划B", "AD_STATUS_NORMAL", "", 50000, "2026-06-01"),
            AdGroup(2003, 1001, "信息流-配件-计划C", "AD_STATUS_NORMAL", "", 30000, "2026-05-20"),
            AdGroup(2004, 1001, "信息流-新品-计划D", "AD_STATUS_NORMAL", "", 30000, "2026-07-12"),
            AdGroup(2005, 1001, "信息流-清仓-计划E", "AD_STATUS_NORMAL", "", 40000, "2026-05-25"),
        ]
        self.creatives = [
            AdCreative(9001, 2001, "夏日穿搭女装", "清凉一夏，限时折扣"),
            AdCreative(9002, 2001, "女装平价好物", "平价也能美美的"),
            AdCreative(9003, 2002, "男士T恤", "男士清爽T恤"),
            AdCreative(9004, 2003, "配件专场", "配件低至9.9"),
            AdCreative(9005, 2005, "清仓甩卖", "全场清仓"),
        ]

    # ---------- AdPlatformClient 接口 ----------
    def get_campaigns(self, account_id: int) -> List[Campaign]:
        return list(self.campaigns)

    def get_adgroups(self, account_id: int, campaign_id: Optional[int] = None) -> List[AdGroup]:
        ags = list(self.adgroups)
        if campaign_id:
            ags = [a for a in ags if a.campaign_id == campaign_id]
        return ags

    def get_adcreatives(self, account_id: int, adgroup_id: Optional[int] = None) -> List[AdCreative]:
        cs = list(self.creatives)
        if adgroup_id:
            cs = [c for c in cs if c.adgroup_id == adgroup_id]
        return cs

    def _rows(self, raw: dict, campaign_id: int, n: int, start: str) -> List[PerformanceReport]:
        rows = []
        for eid, (cost_y, imp, clk, conv) in raw.items():
            costs = self._split(int(cost_y * 100), n)
            imps = self._split(imp, n)
            clks = self._split(clk, n)
            convs = self._split(conv, n)
            for i in range(n):
                d = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
                rows.append(PerformanceReport(
                    adgroup_id=eid, campaign_id=campaign_id, date=d,
                    cost=costs[i], impression=imps[i], click=clks[i], conversion=convs[i],
                ))
        return rows

    def get_daily_report(self, account_id, level, start_date, end_date, fields=None, filtering=None):
        n = max((datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1, 1)
        if level == "REPORT_LEVEL_ADCREATIVE":
            rows = []
            for cid, (cost_y, imp, clk, conv) in _CR_RAW.items():
                adg = next((c.adgroup_id for c in self.creatives if c.creative_id == cid), 0)
                costs = self._split(int(cost_y * 100), n)
                imps = self._split(imp, n)
                clks = self._split(clk, n)
                convs = self._split(conv, n)
                for i in range(n):
                    d = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
                    rows.append(PerformanceReport(
                        adgroup_id=adg, creative_id=cid, campaign_id=1001, date=d,
                        cost=costs[i], impression=imps[i], click=clks[i], conversion=convs[i],
                    ))
            return rows
        return self._rows(_AG_RAW, 1001, n, start_date)

    def update_adgroup_status(self, account_id, adgroup_id, status):
        self._applied_status[adgroup_id] = status
        for a in self.adgroups:
            if a.adgroup_id == adgroup_id:
                a.configured_status = status
        return {"code": 0, "adgroup_id": adgroup_id, "status": status}

    def update_adgroup_budget(self, account_id, adgroup_id, daily_budget_cents):
        self._applied_budget[adgroup_id] = daily_budget_cents
        for a in self.adgroups:
            if a.adgroup_id == adgroup_id:
                a.daily_budget = daily_budget_cents
        return {"code": 0, "adgroup_id": adgroup_id, "daily_budget": daily_budget_cents}

    # ---------- 便捷 ----------
    def revenue_cents_map(self) -> dict:
        return {k: int(v * 100) for k, v in self.revenue_yuan.items()}
