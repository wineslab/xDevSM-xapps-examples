import json

from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import CccIndicationHeader, CccIndicationMessage

import ocudu_json as oj
from ccc_test import checks
from ccc_test.checks import Context, ControlStep
from ccc_test.journal import Indication, Outcome, make_indication
from ccc_test.plan import Level, Spec, Trigger, build_plan
from ccc_test.structures import expected_ratio, instance_key, value_problems

RRM = "O-RRMPolicyRatio"


def _ind(header: bytes, message: bytes, arrival_s: float = 0.0) -> Indication:
    return make_indication(CccIndicationHeader(header), CccIndicationMessage(message), arrival_s)


def _spec(key: str) -> Spec:
    return next(s for s in build_plan(oj.TEST_CELL) if s.key == key)


def _context() -> Context:
    ctx = Context([oj.TEST_CELL])
    upon_subscription = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([(oj.TEST_CELL,
                                                                                       oj.cell_structures())]))
    for structure in ("O-NRCellDU", "O-BWP", RRM):
        state, problems = checks.layout_from(_spec("S2-F2-{}-all".format(structure)), _filter(upon_subscription,
                                                                                             structure), ctx)
        assert problems == []
        ctx.state.update(state)
    node = _ind(oj.header("uponSubscription", 1 << 32),
                oj.node_message([oj.structure("O-GNBDUFunction", oj.NODE_VALUES)]))
    state, problems = checks.layout_from(_spec("S1-F1-O-GNBDUFunction-all"), node, ctx)
    assert problems == []
    ctx.state.update(state)
    return ctx


def _filter(ind: Indication, structure: str) -> Indication:
    return Indication(ind.arrival_s, ind.reason, ind.event_time, ind.event_time_ntp, ind.format,
                      tuple(r for r in ind.reported if r.ran_cfg_structure_name == structure), b"", b"")


def _step(sst: int, old_max: int, new_max: int) -> ControlStep:
    old, new = {}, {}
    for rt in ("PRB_DL", "PRB_UL"):
        key = instance_key(RRM, oj.ratio(rt, sst))
        old[key] = oj.ratio(rt, sst, max_ratio=old_max)
        new[key] = oj.ratio(rt, sst, max_ratio=new_max)
    return ControlStep("control", oj.TEST_NCI, old, new, 0.0)


def test_ocudu_ran_function_definition_passes():
    results = checks.check_ran_function_def(oj.ran_function_definition())
    assert [r for r in results if not r.passed] == []
    assert checks.ran_function_cells(oj.ran_function_definition()) == [oj.TEST_CELL]


def test_ran_function_definition_without_cell_level_style_fails():
    definition = oj.ran_function_definition()
    bwp = definition["listOfCellsForRANFunctionDefinition"][0]["listOfSupportedCellLevelRANConfigurationStructures"][1]
    bwp["listOfSupportedAttributes"][0]["supportedServices"]["reportService"]["listOfSupportedReportStyles"] = []
    failed = [r.name for r in checks.check_ran_function_def(definition) if not r.passed]
    assert failed == ["RAN function definition: cell-level REPORT Style 2 with Event Trigger Formats 2 and 3"]


def test_layout_of_the_ocudu_test_cell():
    ctx = _context()
    assert len(ctx.state[(oj.TEST_NCI, RRM)]) == 6
    assert len(ctx.state[(oj.TEST_NCI, "O-BWP")]) == 2
    assert ctx.state[(None, "O-GNBDUFunction")][""] == oj.NODE_VALUES


def test_layout_reports_a_missing_attribute_and_an_old_value():
    values = oj.nr_cell_du()
    del values["nrTac"]
    ind = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([(oj.TEST_CELL, [
        oj.structure("O-NRCellDU", values, old=values)])]))
    _, problems = checks.layout_from(_spec("S2-F2-O-NRCellDU-all"), ind, Context([oj.TEST_CELL]))
    assert any("misses attributes ['nrTac']" in p for p in problems)
    assert any("changeType none upon subscription" in p for p in problems)


def test_readme_upon_change_matches_the_max_ratio_selection():
    spec = _spec("S2-F2-O-RRMPolicyRatio-change-max-ratio-cell")
    ind = _ind(oj.README_HEADER.encode(), oj.README_MESSAGE.encode())
    result = checks.check_change_report(spec, ind, _context(), _step(2, 100, 50), "uponChange", _context().state)
    assert result.passed, result.detail


def test_upon_change_without_old_values_fails():
    spec = _spec("S2-F2-O-RRMPolicyRatio-change-max-ratio-cell")
    message = json.loads(oj.README_MESSAGE)
    for s in message["indicationMessageFormat"]["listOfCellsReported"][0]["listOfConfigurationStructuresReported"]:
        del s["oldValuesOfAttributes"]
    ind = _ind(oj.README_HEADER.encode(), json.dumps(message).encode())
    result = checks.check_change_report(spec, ind, _context(), _step(2, 100, 50), "uponChange", _context().state)
    assert not result.passed
    assert "missing" in result.detail


def test_report_type_all_reports_unchanged_instances_without_old_values():
    spec = _spec("S2-F2-O-RRMPolicyRatio-all")
    step = _step(2, 100, 50)
    structures = [oj.structure(RRM, oj.ratio(rt, sst)) for rt in ("PRB_DL", "PRB_UL") for sst in (1, 3)]
    structures += [oj.structure(RRM, oj.ratio(rt, 2, max_ratio=50), "modification", oj.ratio(rt, 2))
                   for rt in ("PRB_DL", "PRB_UL")]
    ind = _ind(oj.header("uponChange", 2 << 32), oj.cell_message([(oj.TEST_CELL, structures)]))
    ctx = _context()
    assert checks.check_change_report(spec, ind, ctx, step, "uponChange", ctx.state).passed
    change_spec = _spec("S2-F2-O-RRMPolicyRatio-change")
    assert not checks.check_change_report(change_spec, ind, ctx, step, "uponChange", ctx.state).passed


def test_upon_subscription_of_report_type_change_lists_every_instance():
    ctx = _context()
    ind = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([(oj.TEST_CELL, [
        oj.structure(RRM, {"rRMPolicyMaxRatio": 100}) for _ in range(6)])]))
    assert checks.check_upon_subscription(_spec("S2-F2-O-RRMPolicyRatio-change-max-ratio-cell"), [ind], ctx).passed
    assert not checks.check_upon_subscription(_spec("S2-F2-O-RRMPolicyRatio-change"), [ind], ctx).passed


def test_cell_priority_reports_only_o_bwp_for_the_cell():
    ctx = _context()
    spec = _spec("S2-F2-O-BWP-all-cell-priority")
    bwps = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([(oj.TEST_CELL, [
        oj.structure("O-BWP", oj.bwp("DL")), oj.structure("O-BWP", oj.bwp("UL"))])]))
    assert checks.check_upon_subscription(spec, [bwps], ctx).passed
    du = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([(oj.TEST_CELL, [
        oj.structure("O-NRCellDU", oj.nr_cell_du())])]))
    assert not checks.check_upon_subscription(spec, [du], ctx).passed


def test_node_level_periodic_with_wrong_format_fails():
    ctx = _context()
    spec = _spec("S1-F3-O-GNBDUFunction-all")
    good = _ind(oj.header("periodic", 1 << 32), oj.node_message([oj.structure("O-GNBDUFunction", oj.NODE_VALUES)]))
    wrong = _ind(oj.header("periodic", 2 << 32), oj.cell_message([(oj.TEST_CELL, [
        oj.structure("O-GNBDUFunction", oj.NODE_VALUES)])]))
    assert checks.check_periodic_baseline(spec, [good, good], ctx, 2).passed
    result = checks.check_periodic_baseline(spec, [good, wrong], ctx, 2)
    assert not result.passed
    assert "Indication Message Format 2 instead of 1" in result.detail


def test_periodic_sequence_needs_exactly_one_change():
    ctx = _context()
    spec = _spec("S2-F3-O-RRMPolicyRatio-all")
    step = _step(2, 100, 50)
    after = step.apply(ctx.state)

    def periodic(state, changes=None):
        entries = checks.expected_entries(spec, ctx, state, "periodic", changes)
        structures = []
        for entry in entries.elements():
            _, name, change, values, old = json.loads(entry)
            structures.append(oj.structure(name, values, change, old))
        return _ind(oj.header("periodic", 3 << 32), oj.cell_message([(oj.TEST_CELL, structures)]))

    old, change, new = periodic(ctx.state), periodic(after, step.changes()), periodic(after)
    assert checks.check_periodic_sequence(spec, [old, change, new], ctx, step, ctx.state).passed
    assert not checks.check_periodic_sequence(spec, [old, new], ctx, step, ctx.state).passed
    assert not checks.check_periodic_sequence(spec, [change, change], ctx, step, ctx.state).passed


def test_event_time_order_and_equality():
    spec = _spec("S2-F2-O-RRMPolicyRatio-all")
    a = _ind(oj.header("uponSubscription", 5 << 32), oj.cell_message([]))
    b = _ind(oj.header("uponChange", 4 << 32), oj.cell_message([]))
    assert not checks.check_event_time_order(spec, [a, b]).passed
    assert checks.check_event_time_order(spec, [b, a]).passed
    assert checks.check_same_event_time("same", {"x": b, "y": b}).passed
    assert not checks.check_same_event_time("same", {"x": a, "y": b}).passed
    assert checks.check_not_before("after", a, b).passed
    assert not checks.check_not_before("after", b, a).passed


def test_reasons_of_change_and_periodic_triggers():
    change = _spec("S2-F2-O-RRMPolicyRatio-all")
    periodic = _spec("S2-F3-O-RRMPolicyRatio-all")
    sub = _ind(oj.header("uponSubscription", 1 << 32), oj.cell_message([]))
    chg = _ind(oj.header("uponChange", 2 << 32), oj.cell_message([]))
    per = _ind(oj.header("periodic", 3 << 32), oj.cell_message([]))
    assert checks.check_reasons(change, [sub, chg, chg], 2).passed
    assert not checks.check_reasons(change, [chg, sub, chg], 2).passed
    assert not checks.check_reasons(change, [sub, chg], 2).passed
    assert checks.check_reasons(periodic, [per, per], 0).passed
    assert not checks.check_reasons(periodic, [sub, per], 0).passed


def test_values_with_listed_attributes_must_be_exactly_those():
    assert value_problems(RRM, {"rRMPolicyMaxRatio": 50}, ("rRMPolicyMaxRatio",)) == []
    assert value_problems(RRM, oj.ratio("PRB_DL", 1), ("rRMPolicyMaxRatio",)) != []
    assert value_problems(RRM, oj.ratio("PRB_DL", 1)) == []
    bad = oj.ratio("PRB_DL", 1, min_ratio=60, max_ratio=50)
    assert value_problems(RRM, bad) == ["ratios dedicated 0, min 60, max 50 are not ordered in 0..100"]


def test_expected_ratio_follows_the_du_prb_conversion():
    assert [expected_ratio(r, oj.TEST_CELL_NOF_PRBS) for r in (0, 29, 50, 100)] == [0, 29, 50, 100]
    assert expected_ratio(3, 51) == 2
    assert expected_ratio(50, None) == 50


def test_admission_of_the_inadmissible_subscriptions():
    reject = _spec("reject-S2-F1")
    assert checks.check_admission(reject, Outcome.REJECTED, "cause").passed
    assert not checks.check_admission(reject, Outcome.ADMITTED, None).passed
    assert reject.level is Level.CELL and reject.trigger is Trigger.NODE_CHANGE
