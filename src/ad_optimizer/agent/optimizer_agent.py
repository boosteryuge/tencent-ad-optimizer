"""优化师 Agent：串联 观测 -> 分析 -> 决策 -> 执行 -> 报告。

默认 dry_run（演练，不真正修改账户），确保资金安全；加 --execute 才真正写操作。
可选交互审批（--interactive）。执行后产出结构化报告，并可调用 LLM 顾问生成自然语言总结。
"""
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..client.base import AdPlatformClient
from ..client.models import PerformanceReport
from ..analysis.metrics import aggregate_reports, aggregate_creative_reports, compute_metrics
from ..strategies.base import Strategy, Action, ActionType, OptimizationContext
from ..strategies.loss_cutting import LossCuttingStrategy
from ..strategies.budget_reallocation import BudgetReallocationStrategy
from ..strategies.creative_optimization import CreativeOptimizationStrategy
from ..utils.logging import get_logger
from ..utils.money import cents_to_yuan


@dataclass
class OptimizationReport:
    account_id: int
    total_adgroups: int
    active_adgroups: int
    actions: List[Action] = field(default_factory=list)
    executed: List[dict] = field(default_factory=list)
    dry_run: bool = True
    summary_text: str = ""
    estimated_saving_cents: float = 0.0

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "total_adgroups": self.total_adgroups,
            "active_adgroups": self.active_adgroups,
            "dry_run": self.dry_run,
            "estimated_saving_cents": self.estimated_saving_cents,
            "action_count": len(self.actions),
            "actions": [a.summary() for a in self.actions],
            "executed": self.executed,
            "summary_text": self.summary_text,
        }


class OptimizerAgent:
    def __init__(self, client: AdPlatformClient, config: dict, advisor=None, logger=None):
        self.client = client
        self.config = config
        self.advisor = advisor
        self.log = logger or get_logger()

    # ---------- 观测 ----------
    def _build_context(self, account_id, start_date, end_date, revenue_map):
        campaigns = self.client.get_campaigns(account_id)
        adgroups = self.client.get_adgroups(account_id)
        creatives = self.client.get_adcreatives(account_id)
        ag_reports = self.client.get_daily_report(account_id, "REPORT_LEVEL_ADGROUP", start_date, end_date)
        cr_reports = self.client.get_daily_report(account_id, "REPORT_LEVEL_ADCREATIVE", start_date, end_date)
        reports_by_ag = aggregate_reports(ag_reports, revenue_map)
        creative_reports_by_id = aggregate_creative_reports(cr_reports)
        return OptimizationContext(
            account_id=account_id, campaigns=campaigns, adgroups=adgroups,
            creatives=creatives, reports_by_ag=reports_by_ag,
            creative_reports_by_id=creative_reports_by_id, config=self.config,
        )

    # ---------- 护栏 ----------
    def _safeguard(self, actions: List[Action], ctx: OptimizationContext) -> List[Action]:
        # 1) 同一 target 只保留最高优先级动作（如暂停优先于预算下调）
        by_target: Dict[int, Action] = {}
        for a in actions:
            if a.target_id not in by_target or a.severity_rank() > by_target[a.target_id].severity_rank():
                by_target[a.target_id] = a
        actions = list(by_target.values())

        # 2) 暂停比例上限
        max_pause = ctx.config["strategies"]["loss_cutting"]["max_pause_ratio"]
        n_active = len(ctx.active_adgroups())
        pauses = [a for a in actions if a.action_type == ActionType.PAUSE_ADGROUP]
        cap = int(n_active * max_pause)
        if len(pauses) > cap:
            self.log.warning(f"暂停数 {len(pauses)} 超过上限 {cap}，仅保留节省最高的 {cap} 个")
            pauses.sort(key=lambda a: a.expected_saving_cents, reverse=True)
            keep = set(a.target_id for a in pauses[:cap])
            actions = [a for a in actions
                       if not (a.action_type == ActionType.PAUSE_ADGROUP and a.target_id not in keep)]

        # 3) 预算下限兜底
        min_b = ctx.config["targets"]["min_daily_budget_cents"]
        for a in actions:
            if a.action_type == ActionType.ADJUST_BUDGET:
                nb = a.params.get("new_budget_cents", 0)
                if nb < min_b:
                    a.params["new_budget_cents"] = min_b
        return actions

    # ---------- 执行 ----------
    def _execute(self, account_id, action: Action):
        if action.action_type == ActionType.PAUSE_ADGROUP:
            return self.client.update_adgroup_status(account_id, action.target_id, "AD_STATUS_SUSPEND")
        if action.action_type == ActionType.ADJUST_BUDGET:
            return self.client.update_adgroup_budget(account_id, action.target_id, int(action.params["new_budget_cents"]))
        return {"code": 0, "note": "no-op (advisory only)"}

    # ---------- 主流程 ----------
    def run(self, account_id, start_date, end_date,
            revenue_map: Optional[Dict[int, float]] = None,
            dry_run: bool = True, interactive: bool = False,
            approve_fn: Optional[Callable[[Action], bool]] = None) -> OptimizationReport:
        revenue_map = revenue_map or {}
        self.log.info(f"开始优化：account={account_id} {start_date}~{end_date} dry_run={dry_run}")
        ctx = self._build_context(account_id, start_date, end_date, revenue_map)

        strategies: List[Strategy] = [
            LossCuttingStrategy(self.config["strategies"]["loss_cutting"]["enabled"]),
            BudgetReallocationStrategy(self.config["strategies"]["budget_reallocation"]["enabled"]),
            CreativeOptimizationStrategy(self.config["strategies"]["creative_optimization"]["enabled"]),
        ]
        actions: List[Action] = []
        for s in strategies:
            acts = s.analyze(ctx)
            self.log.info(f"策略 {s.name}: 产出 {len(acts)} 条动作")
            actions.extend(acts)

        actions = self._safeguard(actions, ctx)
        actions.sort(key=lambda a: -a.severity_rank())

        report = OptimizationReport(
            account_id=account_id,
            total_adgroups=len(ctx.adgroups),
            active_adgroups=len(ctx.active_adgroups()),
            actions=actions, dry_run=dry_run,
        )
        report.estimated_saving_cents = sum(
            a.expected_saving_cents for a in actions if a.action_type == ActionType.PAUSE_ADGROUP
        )

        executed = []
        if not dry_run:
            for a in actions:
                if interactive and approve_fn and not approve_fn(a):
                    self.log.info(f"跳过（未批准）：{a.summary()}")
                    continue
                try:
                    res = self._execute(account_id, a)
                    executed.append({"action": a.summary(), "result": res})
                    self.log.info(f"已执行：{a.summary()}")
                except Exception as e:  # noqa: BLE001
                    self.log.error(f"执行失败：{a.summary()} -> {e}")
                    executed.append({"action": a.summary(), "error": str(e)})
        report.executed = executed

        report.summary_text = self._summarize(report)
        if self.advisor and self.config.get("llm", {}).get("enabled"):
            try:
                report.summary_text = self.advisor.explain(report, ctx)
            except Exception as e:  # noqa: BLE001
                self.log.warning(f"LLM 顾问失败，使用模板总结：{e}")
        return report

    def _summarize(self, report: OptimizationReport) -> str:
        lines = [
            f"账户 {report.account_id}：共 {report.total_adgroups} 个广告组，在投 {report.active_adgroups} 个。",
            f"本轮建议 {len(report.actions)} 项操作（{'演练' if report.dry_run else '已执行'}）。",
        ]
        for a in report.actions:
            lines.append(" - " + a.summary())
        if report.estimated_saving_cents > 0:
            lines.append(f"预计可避免的后续浪费约 ¥{cents_to_yuan(report.estimated_saving_cents):,.0f}。")
        return "\n".join(lines)
