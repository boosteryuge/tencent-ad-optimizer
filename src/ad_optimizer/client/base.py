"""广告平台客户端抽象接口。

所有具体平台（腾讯广告、未来可扩展字节/阿里妈妈）都实现该接口，
优化策略与 Agent 只依赖该抽象，不关心底层 API 细节。
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Campaign, AdGroup, AdCreative, PerformanceReport


class AdPlatformClient(ABC):
    @abstractmethod
    def get_campaigns(self, account_id: int) -> List[Campaign]: ...

    @abstractmethod
    def get_adgroups(self, account_id: int, campaign_id: Optional[int] = None) -> List[AdGroup]: ...

    @abstractmethod
    def get_adcreatives(self, account_id: int, adgroup_id: Optional[int] = None) -> List[AdCreative]: ...

    @abstractmethod
    def get_daily_report(
        self,
        account_id: int,
        level: str,
        start_date: str,
        end_date: str,
        fields: Optional[list] = None,
        filtering: Optional[list] = None,
    ) -> List[PerformanceReport]: ...

    @abstractmethod
    def update_adgroup_status(self, account_id: int, adgroup_id: int, status: str) -> dict: ...

    @abstractmethod
    def update_adgroup_budget(self, account_id: int, adgroup_id: int, daily_budget_cents: int) -> dict: ...
