# 腾讯广告投放优化师 Agent（tencent-ad-optimizer）

一个面向**腾讯广告（Marketing API）**的投放优化自动化 Agent：通过**止损暂停、预算再分配、创意素材优化**三类策略，在保障资金安全的前提下提升广告主 ROI。

> 设计原则：**默认演练（dry-run），不真正改账户**；所有写操作可一键 `--execute`，并内置暂停比例上限、预算下限、新计划观察期等多重护栏。

---

## 一、要解决的核心问题

| 痛点 | Agent 的应对 |
| --- | --- |
| 差计划持续烧钱，发现晚、止损慢 | **止损暂停**：花费达标但零转化 / CPA 超目标倍数 / CTR 极低 → 自动暂停 |
| 同一 campaign 内预算分配僵化，好计划吃不饱、差计划浪费 | **预算再分配**：把预算从低效计划抽调到高效计划 |
| 创意老化、素材同质化导致转化下滑 | **创意优化**：同组创意按 CPA 排序，淘汰最差、复用最优，并建议补充文案变体 |
| 改账户怕出错 | **安全护栏 + 演练模式 + 可选人工审批** |

---

## 二、系统架构

```
                         ┌─────────────────────────────┐
  广告主/运营 ──CLI──▶   │       OptimizerAgent         │
                         │  observe → analyze → decide  │
                         │            → act → report    │
                         └───────────────┬─────────────┘
                                         │ 依赖抽象接口
                         ┌───────────────┴───────────────┐
                         │       AdPlatformClient        │  ← 平台无关抽象
                         ├───────────────────────────────┤
                         │  TencentAdsClient (真实 API)   │
                         │  MockAdClient      (演示/测试) │
                         └───────────────┬───────────────┘
                                         │ HTTP/JSON
                               腾讯广告 Marketing API
                          (campaigns / adgroups / creatives / daily_reports)
```

决策流：`观测`（拉取计划/创意/报表）→ `分析`（聚合指标、计算 ROAS/CPA）→ `决策`（三类策略产出 Action）→ `护栏`（去重、暂停上限、预算下限）→ `执行`（dry-run 或真实写）→ `报告`（结构化 + 可选 LLM 自然语言总结）。

---

## 三、详细方案 / Plan（分阶段落地）

### 阶段 0 · 接入与数据底座
- 封装 `AdPlatformClient` 抽象，先实现 `TencentAdsClient`（鉴权 `access_token/timestamp/nonce`，报表/计划/创意读，暂停/预算写）。
- 统一金额单位为「分」，建立 `Campaign / AdGroup / AdCreative / PerformanceReport` 数据模型。
- **收入（ROAS 计算）外部回传**：腾讯不直接给收入，需广告主从 CRM/归因系统把 `adgroup_id → 转化价值` 传入（见 `--revenue-json`）。

### 阶段 1 · 指标计算与效果评估（已完成）
- `compute_metrics`：CTR / CPC / CVR / CPA / ROAS / ROI，含除零保护。
- `aggregate_reports`：多日报表按广告组聚合；`evaluate`：good/average/poor 健康度分级。

### 阶段 2 · 三类优化策略（已完成）
1. **LossCuttingStrategy（止损）**
   - 规则：① 花费 ≥ 观察阈值且转化=0；② CPA > 目标×倍数；③ 曝光充足但 CTR < 阈值。
   - 产出 `PAUSE_ADGROUP` 动作。
2. **BudgetReallocationStrategy（预算再分配）**
   - 同一 campaign 内按 ROAS 排名，winner/loser 二分；从 loser 抽 `shift_ratio` 预算给 winner；受单 campaign 上限、总比例上限、预算下限约束。
   - 产出 `ADJUST_BUDGET` 动作（一降一升成对出现）。
3. **CreativeOptimizationStrategy（创意优化）**
   - 同组 ≥2 创意且有足够曝光时按 CPA 排序；最差 CPA ≫ 最优 → 建议暂停最差、复用最优；单一创意 → 建议补充素材。
   - 产出 `ROTATE_CREATIVE` / `ALERT` 动作。

### 阶段 3 · Agent 编排与护栏（已完成）
- `OptimizerAgent.run()` 串起全流程；`dry_run` 默认开启。
- 护栏：同一对象只保留最高优先级动作（暂停优先于调预算）；暂停数不超过在投计划 `max_pause_ratio`；预算不低于下限；新计划观察期不评判。

### 阶段 4 · LLM 顾问（可选，已完成骨架）
- `LLMAdvisor`：无 API Key 时回退模板，保证离线可用；配置后生成自然语言总结与文案变体（OpenAI 兼容接口）。

### 阶段 5 · 工程化与可观测（进行中）
- CLI、YAML 配置、单元测试（metrics/策略/端到端）、演示脚本。
- 后续：定时调度（cron）、企业微信/飞书告警推送、A/B 实验化逐步放量、多账户批量、字节/阿里妈妈平台扩展（复用 `AdPlatformClient` 抽象）。

---

## 四、目录结构

```
tencent-ad-optimizer/
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/example_config.yaml
├── src/ad_optimizer/
│   ├── cli.py                  # 命令行入口
│   ├── config.py               # 配置加载 + 元→分换算
│   ├── client/                 # 平台客户端
│   │   ├── base.py             # AdPlatformClient 抽象
│   │   ├── models.py           # 数据模型
│   │   ├── tencent_ads_client.py
│   │   └── mock_client.py      # 演示/测试
│   ├── analysis/metrics.py     # 指标计算
│   ├── strategies/             # 三类策略 + base
│   ├── agent/optimizer_agent.py
│   └── llm/advisor.py
├── tests/                      # pytest
├── scripts/run_optimization.py
└── examples/demo.py            # 零配置演示
```

---

## 五、快速开始

### 0) 环境
```bash
cd tencent-ad-optimizer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 1) 零配置演示（无需任何凭证）
```bash
python examples/demo.py
# 或
python scripts/run_optimization.py --mock
```

### 2) 接入真实账户（演练，不修改）
```bash
export TENCENT_ADS_ACCESS_TOKEN="你的access_token"
python scripts/run_optimization.py --account-id 123456 --days 7
```

### 3) 真正执行（写操作）
```bash
# 先演练确认动作无误，再加 --execute；可加 --interactive 逐个确认
python scripts/run_optimization.py --account-id 123456 --days 7 --execute
```

### 4) 带入收入数据算 ROAS
```bash
python scripts/run_optimization.py --mock \
  --revenue-json '{"2001":2400.0,"2002":300.0}'
```

### 5) 输出 JSON（便于接入调度/告警）
```bash
python scripts/run_optimization.py --mock --json
```

---

## 六、配置说明（config/example_config.yaml）

| 配置项 | 含义 | 默认 |
| --- | --- | --- |
| `targets.target_cpa_yuan` | 目标转化成本（元） | 80 |
| `targets.target_roas` | 目标 ROAS（收入/花费） | 2.0 |
| `strategies.loss_cutting.max_cpa_multiplier` | CPA 超目标几倍判定差 | 2.0 |
| `strategies.loss_cutting.max_pause_ratio` | 单轮最多暂停比例 | 0.5 |
| `strategies.budget_reallocation.shift_ratio` | 从差计划抽预算比例 | 0.2 |
| `strategies.budget_reallocation.loser_roas_threshold` | ROAS < 目标×该值 视为差 | 0.8 |
| `safety.dry_run_default` | 默认演练 | true |
| `llm.enabled` | 启用 LLM 自然语言总结 | false |

所有「元」会在加载时自动换算为「分」，策略内部统一用分。

---

## 七、测试
```bash
pip install -r requirements.txt   # 含 pytest
pytest -q
```

---

## 八、安全与免责
- **默认演练**，写操作需显式 `--execute`。
- 内置暂停比例上限、预算下限、新计划观察期等多重护栏，避免「一刀切」误伤。
- 真实投放前请充分演练，并结合业务目标校准 `target_cpa / target_roas` 等阈值。
- 本项目为参考实现，调用真实 API 前请在**沙箱环境**验证，并遵守腾讯广告开放平台规范。

## 九、License
MIT · © 2026 boosteryuge
