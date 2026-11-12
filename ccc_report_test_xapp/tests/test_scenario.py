import dataclasses

import ocudu_json as oj
from ccc_test.config import RunConfig
from ccc_test.journal import Journal
from ccc_test.scenario import Scenario
from fake_ocudu import Fault, FakeOcudu

FAST = RunConfig(period_ms=50, periodic_count=2, e2_node_timeout_s=1, subscription_timeout_s=1,
                 indication_timeout_s=1, control_ack_timeout_s=1)


def _run(fault=Fault.NONE, cfg=FAST, **kw):
    journal = Journal()
    fake = FakeOcudu(journal, fault=fault, **kw)
    fake.period_ms = cfg.period_ms
    try:
        report = Scenario(fake, journal, cfg).run()
    finally:
        fake.close()
    return report, fake


def _failed(report):
    return {r.name: r.detail for r in report.failed}


def test_every_check_passes_against_an_ocudu_like_e2_node():
    report, fake = _run()
    assert _failed(report) == {}
    assert report.exit_code() == 0
    assert len(report.results) > 80
    member = oj.member(1)
    assert fake.controls == [("00066C000", member, 0, 50), ("00066C000", member, 0, 100)]


def test_two_cells_and_a_configured_member():
    other = dict(oj.OTHER_CELL)
    cfg = dataclasses.replace(FAST, nci=0x00066C001, sst=3, control_max_ratio=30)
    report, fake = _run(cfg=cfg, cells=(oj.TEST_CELL, other))
    assert _failed(report) == {}
    assert fake.controls[0] == ("00066C001", oj.member(3), 0, 30)


def test_missing_old_values_fail_the_change_checks():
    report, _ = _run(Fault.NO_OLD_VALUES)
    failed = _failed(report)
    assert "S2-F2-O-RRMPolicyRatio-all uponChange after the control" in failed
    assert "S2-F3-O-RRMPolicyRatio-change periodic after the restore" in failed
    assert report.exit_code() == 1


def test_upon_subscription_for_a_periodic_trigger_fails():
    report, _ = _run(Fault.UPON_SUBSCRIPTION_FOR_PERIODIC)
    failed = _failed(report)
    assert "S1-F3-O-GNBDUFunction-all sends periodic indications only" in failed
    assert "S2-F3-O-NRCellDU-change sends nothing before the control" in failed


def test_e2_node_without_ocudu_ccc_stops_the_run():
    info = oj.e2mgr_info()
    info["gnb"]["ranFunctions"][1]["ranFunctionOid"] = "1.3.6.1.4.1.53148.1.1.2.4"
    report, fake = _run(node_info=info)
    assert [r.name for r in report.results] == ["E2 node is connected",
                                                "E2 node announces E2SM-CCC with the OCUDU OID 1.3.6.1.4.1.53148.1.6.2.4"]
    assert report.exit_code() == 1
    assert fake.controls == []


def test_abort_after_the_control_restores_the_ratio():
    journal = Journal()
    fake = FakeOcudu(journal)
    fake.period_ms = FAST.period_ms
    original = fake.send_control

    def send_and_abort(cell, member, min_ratio, max_ratio):
        original(cell, member, min_ratio, max_ratio)
        if len(fake.controls) == 1:
            journal.abort()

    fake.send_control = send_and_abort
    try:
        report = Scenario(fake, journal, FAST).run()
    finally:
        fake.close()
    assert _failed(report)["run completes"] == "aborted by a signal"
    assert fake.controls == [("00066C000", oj.member(1), 0, 50), ("00066C000", oj.member(1), 0, 100)]
    ratios = fake.cfg["cells"]["00066C000"]["O-RRMPolicyRatio"].values()
    assert {r["rRMPolicyMaxRatio"] for r in ratios} == {100}


def test_requantized_min_ratio_fires_the_min_ratio_trigger_once():
    report, fake = _run(nof_prbs=100, min_ratio=29)
    assert _failed(report) == {}
    ratios = fake.cfg["cells"]["00066C000"]["O-RRMPolicyRatio"].values()
    assert {r["rRMPolicyMinRatio"] for r in ratios if r["rRMPolicyMemberList"] == [oj.member(1)]} == {28}


def test_member_already_at_the_control_ratio_uses_another_ratio():
    report, fake = _run(cfg=dataclasses.replace(FAST, control_max_ratio=100))
    assert _failed(report) == {}
    assert fake.controls[0][3] == 50
