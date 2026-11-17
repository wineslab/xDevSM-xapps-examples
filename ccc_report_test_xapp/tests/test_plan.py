import json

import ocudu_json as oj
from ccc_test.plan import CELL_PRIORITY, Role, build_plan

PLAN = build_plan(oj.TEST_CELL)


def _by_key():
    return {s.key: s for s in PLAN}


def test_plan_has_one_subscription_per_report_feature():
    assert list(_by_key()) == [
        "S1-F1-O-GNBDUFunction-all", "S1-F3-O-GNBDUFunction-all", "S2-F2-O-RRMPolicyRatio-change-max-ratio-cell",
        "S2-F3-O-RRMPolicyRatio-all", "S2-F3-O-RRMPolicyRatio-change", "S2-F2-O-RRMPolicyRatio-all-on-min-ratio",
        "S2-F2-cell-priority",
        "reject-S2-F1", "reject-F2-unknown-attribute"]
    assert [s.key for s in PLAN if s.role is Role.LAYOUT] == [
        "S1-F1-O-GNBDUFunction-all", "S2-F2-O-RRMPolicyRatio-all-on-min-ratio", "S2-F2-cell-priority"]


def test_only_o_rrm_policy_ratio_subscriptions_react_to_the_control():
    assert sorted(s.key for s in PLAN if s.reacts_to({"rRMPolicyMaxRatio"})) == [
        "S2-F2-O-RRMPolicyRatio-change-max-ratio-cell", "S2-F3-O-RRMPolicyRatio-all", "S2-F3-O-RRMPolicyRatio-change"]


def test_min_ratio_trigger_reacts_only_to_a_min_ratio_change():
    keys = _by_key()
    on_min = keys["S2-F2-O-RRMPolicyRatio-all-on-min-ratio"]
    on_max = keys["S2-F2-O-RRMPolicyRatio-change-max-ratio-cell"]
    assert on_min.reacts_to({"rRMPolicyMinRatio"}) and not on_min.reacts_to({"rRMPolicyMaxRatio"})
    assert not on_max.reacts_to({"rRMPolicyMinRatio", "rRMPolicyDedicatedRatio"})
    assert keys["S2-F3-O-RRMPolicyRatio-all"].reacts_to({"rRMPolicyDedicatedRatio"})
    assert not keys["reject-S2-F1"].reacts_to({"rRMPolicyMaxRatio"})
    assert not keys["S2-F3-O-RRMPolicyRatio-all"].reacts_to(set())


def test_inadmissible_level_combination_uses_the_ocudu_json():
    encoded = _by_key()["reject-S2-F1"].encoded
    assert encoded is not None
    trigger, action = encoded
    assert json.loads(trigger) == json.loads(oj.NODE_TRIGGER)
    assert json.loads(action) == json.loads(oj.CELL_ACTION)


def test_cell_priority_action_has_an_entry_for_all_cells_and_one_for_the_cell():
    encoded = _by_key()[CELL_PRIORITY].encoded
    assert encoded is not None
    trigger, action = encoded
    entries = json.loads(action)["actionDefinitionFormat"]["listOfCellConfigurationsToBeReportedForADF"]
    assert entries == [
        {"listOfCellLevelRANConfigurationStructuresForADF": [
            {"reportType": "all", "ranConfigurationStructureName": "O-RRMPolicyRatio"}]},
        {"listOfCellLevelRANConfigurationStructuresForADF": [
            {"reportType": "all", "ranConfigurationStructureName": "O-NRCellDU"},
            {"reportType": "all", "ranConfigurationStructureName": "O-BWP"}], "cellGlobalId": oj.TEST_CELL},
    ]
    assert json.loads(trigger)["eventTriggerDefinitionFormat"]["listOfCellLevelConfigurationStructuresForEventTrigger"] \
        == [{"listOfRANConfigurationStructuresForEventTrigger": [{"ranConfigurationStructureName": "O-BWP"}]}]
