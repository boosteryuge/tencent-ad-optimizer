"""可选的 LLM 顾问：生成自然语言总结与文案变体。

无 API Key 或 llm.enabled=false 时自动回退到模板，保证离线可用。
兼容 OpenAI 接口（可指向任意 OpenAI 兼容网关）。
"""
import os
from typing import List, Optional

from ..agent.optimizer_agent import OptimizationReport
from ..strategies.base import OptimizationContext


class LLMAdvisor:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.base_url = self.config.get("base_url", "https://api.openai.com/v1")
        self.model = self.config.get("model", "gpt-4o-mini")
        self.api_key = os.environ.get(self.config.get("api_key_env", "OPENAI_API_KEY"), "")

    def explain(self, report: OptimizationReport, ctx: OptimizationContext) -> str:
        if not self.enabled or not self.api_key:
            return report.summary_text or "（LLM 未启用，使用模板总结）"
        try:
            from openai import OpenAI
        except ImportError:
            return report.summary_text
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        prompt = (
            "你是一名资深广告投放优化师。以下是本轮广告账户优化建议，"
            "请用中文给广告主一段简洁、专业、可执行的总结（不超过200字）：\n"
            + "\n".join(report.to_dict().get("actions", []))
        )
        try:
            resp = client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception:
            return report.summary_text

    def suggest_copy(self, title: str, description: str) -> List[str]:
        variants = [f"{title}｜限时优惠", f"🔥{title}", f"{title}，错过等一年", f"{description} 立即抢购"]
        if self.enabled and self.api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                r = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content":
                        f"为广告标题「{title}」和文案「{description}」生成3条更吸引人的信息流广告文案变体，简短。"}],
                    temperature=0.8,
                )
                out = [c.strip() for c in r.choices[0].message.content.split("\n") if c.strip()][:3]
                if out:
                    return out
            except Exception:
                pass
        return variants
