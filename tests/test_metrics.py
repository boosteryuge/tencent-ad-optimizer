from ad_optimizer.analysis.metrics import compute_metrics, aggregate_reports, evaluate
from ad_optimizer.client.models import PerformanceReport


def test_compute_metrics_basic():
    m = compute_metrics(10000, 1000, 100, 10, revenue=40000)  # 花费¥100, 转化10, 收入¥400
    assert abs(m.ctr - 0.1) < 1e-9
    assert abs(m.cpc - 100.0) < 1e-9
    assert abs(m.cvr - 0.1) < 1e-9
    assert abs(m.cpa - 1000.0) < 1e-9
    assert abs(m.roas - 4.0) < 1e-9


def test_div_by_zero_safe():
    m = compute_metrics(0, 0, 0, 0, 0)
    assert m.ctr == 0
    assert m.cpa == float("inf")
    assert m.roas == 0


def test_aggregate():
    rs = [
        PerformanceReport(adgroup_id=1, cost=100, impression=10, click=2, conversion=1, date="2026-07-01"),
        PerformanceReport(adgroup_id=1, cost=100, impression=10, click=2, conversion=1, date="2026-07-02"),
    ]
    out = aggregate_reports(rs, {1: 400})
    assert len(out) == 1
    assert out[1].cost == 200
    assert out[1].conversion == 2
    assert out[1].revenue == 400


def test_evaluate():
    good = compute_metrics(10000, 1000, 100, 20, 40000)  # cpa ¥5, roas 4
    assert evaluate(good, target_cpa_cents=8000, target_roas=2.0) == "good"
    poor = compute_metrics(10000, 1000, 100, 1, 0)  # roas 0
    assert evaluate(poor, target_cpa_cents=8000, target_roas=2.0) == "poor"
