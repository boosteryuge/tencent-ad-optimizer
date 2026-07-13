"""腾讯广告实体数据模型（dataclass，零三方依赖）。

层级关系：推广计划 Campaign -> 广告组/广告计划 AdGroup -> 广告创意 AdCreative。
报表 PerformanceReport 可从 API 原始字典解析，也可由多日数据聚合得到。
金额单位统一为「分」。
"""
from dataclasses import dataclass


@dataclass
class Campaign:
    """推广计划（campaign）。"""
    campaign_id: int
    campaign_name: str = ""
    campaign_type: str = ""
    objective: str = ""

    @classmethod
    def from_api(cls, d: dict) -> "Campaign":
        return cls(
            campaign_id=int(d["campaign_id"]),
            campaign_name=d.get("campaign_name", "") or d.get("name", ""),
            campaign_type=d.get("campaign_type", ""),
            objective=d.get("objective_type", "") or d.get("objective", ""),
        )


@dataclass
class AdGroup:
    """广告组 / 广告计划（adgroup）。daily_budget 单位：分。"""
    adgroup_id: int
    campaign_id: int
    adgroup_name: str = ""
    configured_status: str = "AD_STATUS_NORMAL"   # 客户设置状态
    system_status: str = ""                         # 系统状态
    daily_budget: int = 0                           # 日预算（分）
    created_time: str = ""                          # 创建时间，用于观察期护栏

    @property
    def is_active(self) -> bool:
        return self.configured_status == "AD_STATUS_NORMAL"

    @classmethod
    def from_api(cls, d: dict) -> "AdGroup":
        return cls(
            adgroup_id=int(d["adgroup_id"]),
            campaign_id=int(d.get("campaign_id", 0)),
            adgroup_name=d.get("adgroup_name", "") or d.get("name", ""),
            configured_status=d.get("configured_status", "AD_STATUS_NORMAL"),
            system_status=d.get("system_status", ""),
            daily_budget=int(d.get("daily_budget", 0) or 0),
            created_time=d.get("created_time", "") or d.get("first_day_begin", ""),
        )


@dataclass
class AdCreative:
    """广告创意（creative）。"""
    creative_id: int
    adgroup_id: int
    title: str = ""
    description: str = ""
    image_url: str = ""
    video_url: str = ""
    configured_status: str = "AD_STATUS_NORMAL"

    @classmethod
    def from_api(cls, d: dict) -> "AdCreative":
        return cls(
            creative_id=int(d["creative_id"]),
            adgroup_id=int(d.get("adgroup_id", 0)),
            title=d.get("title", "") or "",
            description=d.get("description", "") or "",
            image_url=d.get("image_url", "") or d.get("image", "") or "",
            video_url=d.get("video_url", "") or d.get("video", "") or "",
            configured_status=d.get("configured_status", "AD_STATUS_NORMAL"),
        )


@dataclass
class PerformanceReport:
    """单实体（广告组 / 创意）在某日期的投放表现。金额单位：分。

    revenue（转化价值/收入）由广告主通过 CRM/归因系统外部回传，腾讯 API 不直接提供，
    用于计算 ROAS / ROI。
    """
    adgroup_id: int
    date: str = ""
    campaign_id: int = 0
    creative_id: int = 0
    cost: float = 0.0             # 花费（分）
    impression: int = 0           # 曝光
    click: int = 0                # 点击
    conversion: int = 0           # 转化
    ctr: float = 0.0
    cpc: float = 0.0              # 分
    cpm: float = 0.0              # 分
    conversion_cost: float = 0.0  # CPA（分）
    conversion_rate: float = 0.0  # CVR
    revenue: float = 0.0          # 转化价值（分），外部回传

    @classmethod
    def from_api(cls, d: dict, campaign_id: int = 0) -> "PerformanceReport":
        return cls(
            adgroup_id=int(d.get("adgroup_id", 0)),
            date=d.get("date", ""),
            campaign_id=int(d.get("campaign_id", campaign_id)),
            creative_id=int(d.get("creative_id", 0)),
            cost=float(d.get("cost", 0) or 0),
            impression=int(d.get("impression", 0) or 0),
            click=int(d.get("click", 0) or 0),
            conversion=int(d.get("conversion", 0) or 0),
            ctr=float(d.get("ctr", 0) or 0),
            cpc=float(d.get("cpc", 0) or 0),
            cpm=float(d.get("cpm", 0) or 0),
            conversion_cost=float(d.get("conversion_cost", 0) or 0),
            conversion_rate=float(d.get("conversion_rate", 0) or 0),
        )
