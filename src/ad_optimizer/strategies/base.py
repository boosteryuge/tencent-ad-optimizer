"""优化策略基础类与动作模型。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from ..client.models import Campaign, AdGroup, AdCreative, PerformanceReport


class ActionType(str, Enum):
    PAUSE_ADGROUP = "PAUSE_ADGROUP"       # 止损暂停
    ADJUST_BUDGET = "ADJUST_BUDGET"       # 预算调整
    ROTATE_CREATIVE = "ROTATE_CREATIVE"   # 创意轮换
    UPDATE_BID = "UPDATE_BID"             # 出价调整
    ALERT = "ALERT"                       # 仅建议


@dataclass
class Action:
    action_type: ActionType
    target_id: int                  # adgroup_id 或 creative_id
    campaign_id: int = 0
    params: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    severity: str = "medium"         # low | medium | high
    expected_saving_cents: float = 0.0
    expected_uplift: str = ""

    def severity_rank(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(self.severity, 2)

    def summary(self) -> str:
        if self.action_type == ActionType.PAUSE_ADGROUP:
            return f"[止损暂停] 广告组 {self.target_id}: {self.rationale}"
        if self.action_type == ActionType.ADJUST_BUDGET:
            old = self.params.get("old_budget_cents", 0)
            new = self.params.get("new_budget_cents", 0)
            return f"[预算调整] 广告组 {self.target_id}: ¥{old/100:.0f} → ¥{new/100:.0f} | {self.rationale}"
        if self.action_type == ActionType.ROTATE_CREATIVE:
            return f"[创意优化] 创意 {self.target_id}: {self.rationale}"
        if self.action_type == ActionType.UPDATE_BID:
            return f"[出价调整] 广告组 {self.target_id}: {self.rationale}"
        return f"[建议] 广告组 {self.target_id}: {self.rationale}"


@dataclass
class OptimizationContext:
    account_id: int
    campaigns: List[Campaign]
    adgroups: List[AdGroup]
    creatives: List[AdCreative]
    reports_by_ag: Dict[int, PerformanceReport]
    creative_reports_by_id: Dict[int, PerformanceReport] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def active_adgroups(self) -> List[AdGroup]:
        return [a for a in self.adgroups if a.is_active]


class Strategy(ABC):
    name: str = "base"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def analyze(self, ctx: OptimizationContext) -> List[Action]:
        ...
