"""金额工具：腾讯广告接口中金额单位为「分」(cents)，对外展示统一用「元」。"""

def yuan_to_cents(yuan: float) -> int:
    """元 -> 分（整数）。"""
    return int(round(yuan * 100))


def cents_to_yuan(cents: float) -> float:
    """分 -> 元（保留两位小数）。"""
    return round(cents / 100.0, 2)


def fmt_yuan(cents: float) -> str:
    """分 -> 带货币符号的字符串。"""
    return f"¥{cents_to_yuan(cents):,.2f}"
