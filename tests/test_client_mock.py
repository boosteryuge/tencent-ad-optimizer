def test_mock_counts(mock_client):
    ags = mock_client.get_adgroups(0)
    assert len(ags) == 5
    camps = mock_client.get_campaigns(0)
    assert len(camps) == 1


def test_mock_status_write(mock_client):
    r = mock_client.update_adgroup_status(0, 2003, "AD_STATUS_SUSPEND")
    assert r["status"] == "AD_STATUS_SUSPEND"
    ag = next(a for a in mock_client.get_adgroups(0) if a.adgroup_id == 2003)
    assert ag.configured_status == "AD_STATUS_SUSPEND"


def test_mock_budget_write(mock_client):
    r = mock_client.update_adgroup_budget(0, 2001, 60000)
    assert r["daily_budget"] == 60000
    ag = next(a for a in mock_client.get_adgroups(0) if a.adgroup_id == 2001)
    assert ag.daily_budget == 60000
