"""配置加载：内置默认值 + YAML 覆盖，并把「元」统一换算为「分」。"""
import os
from typing import Any, Dict

import yaml

from .utils.money import yuan_to_cents

DEFAULT_CONFIG: Dict[str, Any] = {
    "account_id": 0,
    "api": {
        "base_url": "https://api.e.qq.com",
        "version": "v3.0",
        "access_token_env": "TENCENT_ADS_ACCESS_TOKEN",
        "timeout": 30,
    },
    "targets": {
        "target_cpa_yuan": 80,     # 目标转化成本（元）
        "target_roas": 2.0,        # 目标 ROAS（收入/花费）
        "min_daily_budget_yuan": 50,  # 单计划日预算下限（元）
    },
    "strategies": {
        "loss_cutting": {
            "enabled": True,
            "min_observation_spend_yuan": 300,   # 花费不足此数不评判
            "min_observation_days": 3,
            "max_cpa_multiplier": 2.0,           # CPA 超过目标 2 倍即判定差
            "min_impressions": 1000,
            "min_ctr": 0.003,                     # 0.3%
            "max_pause_ratio": 0.5,               # 单轮最多暂停 50% 在投计划
        },
        "budget_reallocation": {
            "enabled": True,
            "min_observation_spend_yuan": 200,
            "shift_ratio": 0.2,                   # 从差计划抽 20% 预算
            "loser_roas_threshold": 0.8,          # ROAS < 0.8*目标 视为差
            "max_shift_yuan_per_campaign": 2000,
            "max_total_shift_ratio": 0.3,
        },
        "creative_optimization": {
            "enabled": True,
            "max_cpa_multiplier": 2.0,
            "min_impressions": 500,
        },
    },
    "safety": {
        "dry_run_default": True,
        "require_approval": False,
        "min_observation_days": 2,
    },
    "llm": {
        "enabled": False,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str = None) -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        cfg = _deep_merge(DEFAULT_CONFIG, user)

    # 元 -> 分 换算（策略内部统一用分）
    t = cfg["targets"]
    t["target_cpa_cents"] = yuan_to_cents(t["target_cpa_yuan"])
    t["min_daily_budget_cents"] = yuan_to_cents(t["min_daily_budget_yuan"])
    lc = cfg["strategies"]["loss_cutting"]
    lc["min_observation_spend_cents"] = yuan_to_cents(lc["min_observation_spend_yuan"])
    br = cfg["strategies"]["budget_reallocation"]
    br["min_observation_spend_cents"] = yuan_to_cents(br["min_observation_spend_yuan"])
    br["max_shift_cents_per_campaign"] = yuan_to_cents(br["max_shift_yuan_per_campaign"])
    return cfg
