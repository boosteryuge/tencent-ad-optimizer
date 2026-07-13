"""腾讯广告真实 API 客户端（Marketing API v3.0）。

鉴权：全局参数 access_token / timestamp(秒) / nonce 放在 query string。
参考：https://developers.e.qq.com/docs/api
金额单位：分。
"""
import time
import json
import uuid
from typing import List, Optional

from .base import AdPlatformClient
from .models import Campaign, AdGroup, AdCreative, PerformanceReport


class TencentAdsError(Exception):
    def __init__(self, code, message, message_cn=""):
        self.code = code
        self.message = message
        self.message_cn = message_cn
        super().__init__(f"[{code}] {message_cn or message}")


class TencentAdsClient(AdPlatformClient):
    def __init__(
        self,
        access_token: str,
        version: str = "v3.0",
        base_url: str = "https://api.e.qq.com",
        timeout: int = 30,
        account_id: Optional[int] = None,
    ):
        self.access_token = access_token
        self.version = version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_account_id = account_id
        self._session = None

    # ---------- 底层 HTTP ----------
    def _http(self):
        try:
            import requests
        except ImportError:
            raise RuntimeError("需要安装 requests：pip install requests")
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _call(self, method: str, interface: str, params: Optional[dict] = None, body: Optional[dict] = None):
        url = f"{self.base_url}/{self.version}/{interface}"
        ts = int(time.time())
        nonce = uuid.uuid4().hex[:16]
        global_params = {"access_token": self.access_token, "timestamp": ts, "nonce": nonce}
        s = self._http()
        if method.upper() == "GET":
            q = {**global_params, **(params or {})}
            resp = s.get(url, params=q, timeout=self.timeout)
        else:
            resp = s.request(method, url, params=global_params, json=body, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            raise TencentAdsError(-1, "响应非 JSON", resp.text[:200])
        if data.get("code", 0) != 0:
            raise TencentAdsError(data.get("code"), data.get("message", ""), data.get("message_cn", ""))
        return data.get("data", {})

    def _paginate(self, interface: str, params: dict, item_key: str = "list"):
        out = []
        page = 1
        page_size = 100
        while True:
            p = dict(params)
            p["page"] = page
            p["page_size"] = page_size
            d = self._call("GET", interface, params=p)
            items = d.get(item_key, []) or []
            out.extend(items)
            pi = d.get("page_info", {})
            if page >= pi.get("total_page", 1) or not items:
                break
            page += 1
        return out

    # ---------- 读取接口 ----------
    def get_campaigns(self, account_id: int) -> List[Campaign]:
        account_id = account_id or self.default_account_id
        raw = self._paginate(
            "campaigns/get",
            {"account_id": account_id,
             "fields": ["campaign_id", "campaign_name", "campaign_type", "objective_type"]},
        )
        return [Campaign.from_api(r) for r in raw]

    def get_adgroups(self, account_id: int, campaign_id: Optional[int] = None) -> List[AdGroup]:
        account_id = account_id or self.default_account_id
        params = {
            "account_id": account_id,
            "fields": ["adgroup_id", "campaign_id", "adgroup_name", "configured_status",
                       "system_status", "daily_budget", "created_time"],
        }
        if campaign_id:
            params["filtering"] = json.dumps(
                [{"field": "campaign_id", "operator": "EQUALS", "values": [campaign_id]}]
            )
        raw = self._paginate("adgroups/get", params)
        return [AdGroup.from_api(r) for r in raw]

    def get_adcreatives(self, account_id: int, adgroup_id: Optional[int] = None) -> List[AdCreative]:
        account_id = account_id or self.default_account_id
        params = {
            "account_id": account_id,
            "fields": ["creative_id", "adgroup_id", "title", "description",
                       "image_url", "video_url", "configured_status"],
        }
        if adgroup_id:
            params["filtering"] = json.dumps(
                [{"field": "adgroup_id", "operator": "EQUALS", "values": [adgroup_id]}]
            )
        raw = self._paginate("adcreatives/get", params)
        return [AdCreative.from_api(r) for r in raw]

    def get_daily_report(
        self, account_id: int, level: str, start_date: str, end_date: str,
        fields: Optional[list] = None, filtering: Optional[list] = None,
    ) -> List[PerformanceReport]:
        account_id = account_id or self.default_account_id
        fields = fields or [
            "date", "adgroup_id", "campaign_id", "creative_id", "cost", "impression",
            "click", "conversion", "ctr", "cpc", "cpm", "conversion_cost", "conversion_rate",
        ]
        params = {
            "account_id": account_id,
            "level": level,
            "date_range": json.dumps({"start_date": start_date, "end_date": end_date}),
            "fields": json.dumps(fields),
        }
        if filtering:
            params["filtering"] = json.dumps(filtering)
        out = []
        page = 1
        while True:
            p = dict(params)
            p["page"] = page
            p["page_size"] = 100
            d = self._call("GET", "daily_reports/get", params=p)
            items = d.get("list", []) or []
            out.extend([PerformanceReport.from_api(r) for r in items])
            pi = d.get("page_info", {})
            if page >= pi.get("total_page", 1) or not items:
                break
            page += 1
        return out

    # ---------- 写接口 ----------
    def update_adgroup_status(self, account_id: int, adgroup_id: int, status: str) -> dict:
        account_id = account_id or self.default_account_id
        body = {
            "account_id": account_id,
            "update_configured_status_spec": [
                {"adgroup_id": int(adgroup_id), "configured_status": status}
            ],
        }
        return self._call("POST", "adgroups/update_configured_status", body=body)

    def update_adgroup_budget(self, account_id: int, adgroup_id: int, daily_budget_cents: int) -> dict:
        account_id = account_id or self.default_account_id
        body = {
            "account_id": account_id,
            "update_daily_budget_spec": [
                {"adgroup_id": int(adgroup_id), "daily_budget": int(daily_budget_cents)}
            ],
        }
        return self._call("POST", "adgroups/update_daily_budget", body=body)
