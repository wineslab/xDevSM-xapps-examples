import json
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import ReportedStructure, ntp_to_unix_s
from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import nr_cell_id_of
from xdevsm.sm_framework.py_oran.ccc.constants import (
    ACTION_DEF_FORMAT_CELL_LEVEL,
    ACTION_DEF_FORMAT_NODE_LEVEL,
    CHANGE_TYPE_MODIFICATION,
    CHANGE_TYPE_NONE,
    EVENT_TRIGGER_FORMAT_CELL_CHANGE,
    EVENT_TRIGGER_FORMAT_NODE_CHANGE,
    EVENT_TRIGGER_FORMAT_PERIODIC,
    EVENT_TRIGGER_STYLE_CFG_CHANGE,
    EVENT_TRIGGER_STYLE_PERIODIC,
    IND_HDR_FORMAT_1,
    IND_MSG_FORMAT_CELL_LEVEL,
    IND_MSG_FORMAT_NODE_LEVEL,
    IND_REASON_PERIODIC,
    IND_REASON_UPON_CHANGE,
    IND_REASON_UPON_SUBSCRIPTION,
    REPORT_STYLE_CELL_LEVEL,
    REPORT_STYLE_NODE_LEVEL,
    REPORT_TYPE_ALL,
    CONTROL_STYLE_CELL_LEVEL,
    SM_CCC_NAME,
    SM_CCC_OID_OCUDU,
    STRUCT_O_RRM_POLICY_RATIO,
)

from ccc_test.journal import AckKind, Indication, Outcome
from ccc_test.plan import Expect, Level, Spec
from ccc_test.report import CheckResult, check
from ccc_test.structures import (
    ATTRIBUTE_NAMES,
    CELL_STRUCTURES,
    NODE_STRUCTURES,
    count_problems,
    instance_key,
    value_problems,
)

# (NR Cell Identity or None for the node, structure name) -> instance key -> attribute values.
State = Dict[Tuple[Optional[int], str], Dict[str, dict]]
# (NR Cell Identity, structure name, instance key) -> attribute values before the change.
Changes = Dict[Tuple[Optional[int], str, str], dict]

MAX_DETAIL_ITEMS = 2
CADENCE_TOLERANCE = (0.5, 1.5)


@dataclass(frozen=True)
class ControlStep:
    """One O-RRMPolicyRatio control: the member instances it changes, with their values before and after."""

    name: str
    nci: int
    old: Dict[str, dict]
    new: Dict[str, dict]
    sent_s: float
    before: State = field(default_factory=dict)
    reacting: Tuple[Spec, ...] = ()

    def changes(self) -> Changes:
        return {(self.nci, STRUCT_O_RRM_POLICY_RATIO, key): values for key, values in self.old.items()}

    def apply(self, state: State) -> State:
        out = {k: dict(v) for k, v in state.items()}
        out[(self.nci, STRUCT_O_RRM_POLICY_RATIO)].update(self.new)
        return out


@dataclass
class Context:
    """What the checks compare the indications with."""

    cells: List[dict]
    state: State = field(default_factory=dict)
    period_s: float = 1.0

    @property
    def cell_ids(self) -> List[int]:
        return [nci for nci in map(nr_cell_id_of, self.cells) if nci is not None]


# ---------------------------------------------------------------- RAN Function Definition


def _styles(services: dict, path: Sequence[str]) -> list:
    node = services
    for name in path:
        node = (node or {}).get(name) or {}
    return node if isinstance(node, list) else []


def _service_problems(where: str, services: dict, style: int, formats: Tuple[int, int], change_format: int):
    """Problems of the supportedServices of one attribute, for the REPORT style of its level."""
    problems = []
    triggers = {(s.get("eventTriggerStyleType"), s.get("eventTriggerFormatType"))
                for s in _styles(services, ("eventTrigger", "listOfSupportedEventTriggerStyles"))}
    for expected in ((EVENT_TRIGGER_STYLE_CFG_CHANGE, change_format),
                     (EVENT_TRIGGER_STYLE_PERIODIC, EVENT_TRIGGER_FORMAT_PERIODIC)):
        if expected not in triggers:
            problems.append("{} lacks event trigger style {} with format {}".format(where, *expected))
    reports = [s for s in _styles(services, ("reportService", "listOfSupportedReportStyles"))
               if s.get("reportServiceStyleType") == style]
    wanted = (formats[0], IND_HDR_FORMAT_1, formats[1])
    if not any((s.get("reportServiceActionDefinitionFormatType"), s.get("reportServiceIndicationHeaderFormatType"),
                s.get("reportServiceIndicationMessageFormatType")) == wanted for s in reports):
        problems.append("{} lacks REPORT style {} with formats {}".format(where, style, wanted))
    return problems


def _structures_problems(where: str, structures: list, names: Sequence[str], style: int, formats, change_format):
    problems = []
    by_name = {s.get("ranConfigurationStructureName"): s for s in structures or []}
    for name in names:
        if name not in by_name:
            problems.append("{} lacks {}".format(where, name))
            continue
        attributes = by_name[name].get("listOfSupportedAttributes") or []
        listed = {a.get("attributeName") for a in attributes}
        if listed != ATTRIBUTE_NAMES[name]:
            problems.append("{} {} lists {}".format(where, name, sorted(listed)))
        for a in attributes:
            problems += _service_problems("{} {}.{}".format(where, name, a.get("attributeName")),
                                          a.get("supportedServices") or {}, style, formats, change_format)
    return problems


def _control_problems(cells: list) -> List[str]:
    problems = []
    for cell in cells:
        for s in cell.get("listOfSupportedCellLevelRANConfigurationStructures") or []:
            for a in s.get("listOfSupportedAttributes") or []:
                styles = [c.get("controlServiceStyleType")
                          for c in _styles(a.get("supportedServices"), ("controlService", "listOfSupportedControlStyles"))]
                controllable = s.get("ranConfigurationStructureName") == STRUCT_O_RRM_POLICY_RATIO
                if (CONTROL_STYLE_CELL_LEVEL in styles) != controllable:
                    problems.append("{}.{} CONTROL styles {}".format(
                        s.get("ranConfigurationStructureName"), a.get("attributeName"), styles))
    return problems


def check_ran_function_def(definition: dict) -> List[CheckResult]:
    name = definition.get("ranFunctionName") or {}
    cells = definition.get("listOfCellsForRANFunctionDefinition") or []
    node_formats = (ACTION_DEF_FORMAT_NODE_LEVEL, IND_MSG_FORMAT_NODE_LEVEL)
    cell_formats = (ACTION_DEF_FORMAT_CELL_LEVEL, IND_MSG_FORMAT_CELL_LEVEL)
    cell_problems = [] if cells else ["no cell"]
    for cell in cells:
        cell_problems += _structures_problems(
            "cell {}".format((cell.get("cellGlobalID") or {}).get("nRCellIdentity")),
            cell.get("listOfSupportedCellLevelRANConfigurationStructures") or [], CELL_STRUCTURES,
            REPORT_STYLE_CELL_LEVEL, cell_formats, EVENT_TRIGGER_FORMAT_CELL_CHANGE)
    return [
        check("RAN function definition names E2SM-CCC with the OCUDU OID",
              [] if (name.get("ranFunctionShortName"), name.get("ranFunctionServiceModelOID")) ==
              (SM_CCC_NAME, SM_CCC_OID_OCUDU) else ["ranFunctionName {}".format(name)]),
        check("RAN function definition: node-level REPORT Style 1 with Event Trigger Formats 1 and 3",
              _structures_problems("node", definition.get("listOfSupportedNodeLevelConfigurationStructures") or [],
                                   NODE_STRUCTURES, REPORT_STYLE_NODE_LEVEL, node_formats,
                                   EVENT_TRIGGER_FORMAT_NODE_CHANGE)),
        check("RAN function definition: cell-level REPORT Style 2 with Event Trigger Formats 2 and 3", cell_problems,
              "{} cells".format(len(cells))),
        check("RAN function definition: CONTROL Style 2 for O-RRMPolicyRatio only", _control_problems(cells)),
    ]


def ran_function_cells(definition: dict) -> List[dict]:
    """Cell Global IDs of the RAN Function Definition that hold an NR Cell Identity."""
    cells = [c.get("cellGlobalID") or {} for c in definition.get("listOfCellsForRANFunctionDefinition") or []]
    return [c for c in cells if nr_cell_id_of(c) is not None]


# ---------------------------------------------------------------- Expected indication content


def _entry(nci, structure, change_type, values, old_values) -> str:
    return json.dumps([nci, structure, change_type, values, old_values], sort_keys=True)


def _actual_entries(ind: Indication) -> Counter:
    return Counter(_entry(r.nr_cell_id, r.ran_cfg_structure_name, r.change_type, r.values, r.old_values)
                   for r in ind.reported)


def _project(values: Optional[dict], attributes: Sequence[str]) -> Optional[dict]:
    if values is None or not attributes:
        return values
    return {k: v for k, v in values.items() if k in attributes}


def spec_structures(spec: Spec, nci: Optional[int]) -> List[str]:
    """Structures that the action definition of ``spec`` reports for a cell. A cell entry has priority."""
    if not spec.cell_structures:
        return [spec.structure]
    by_cell = {None if cell is None else nr_cell_id_of(cell): names for cell, names in spec.cell_structures}
    return list(by_cell.get(nci, by_cell.get(None, ())))


def spec_scope(spec: Spec, ctx: Context) -> Sequence[Optional[int]]:
    if spec.level is Level.NODE:
        return [None]
    if spec.cells:
        return [nr_cell_id_of(c) for c in spec.cells]
    return list(ctx.cell_ids)


def expected_entries(spec: Spec, ctx: Context, state: State, reason: str, changes: Optional[Changes] = None):
    """The structures that OCUDU reports for ``spec``, as per its README: uponSubscription reports every instance
    with no change, report type all reports every instance, and report type change only the changed ones."""
    changes = changes or {}
    out = Counter()
    for nci in spec_scope(spec, ctx):
        for structure in spec_structures(spec, nci):
            for key, values in sorted(state.get((nci, structure), {}).items()):
                old = changes.get((nci, structure, key)) if reason != IND_REASON_UPON_SUBSCRIPTION else None
                old = _project(old, spec.attributes)
                new = _project(values, spec.attributes)
                if old is not None and old != new:
                    out[_entry(nci, structure, CHANGE_TYPE_MODIFICATION, new, old)] += 1
                elif spec.report_type == REPORT_TYPE_ALL or reason == IND_REASON_UPON_SUBSCRIPTION:
                    out[_entry(nci, structure, CHANGE_TYPE_NONE, new, None)] += 1
    return out


def _describe(entries: Iterable[str]) -> str:
    items = sorted(entries)
    text = ", ".join(items[:MAX_DETAIL_ITEMS])
    return text + (" and {} more".format(len(items) - MAX_DETAIL_ITEMS) if len(items) > MAX_DETAIL_ITEMS else "")


def content_problems(ind: Indication, expected: Counter) -> List[str]:
    actual = _actual_entries(ind)
    missing = expected - actual
    unexpected = actual - expected
    problems = []
    if missing:
        problems.append("missing {}".format(_describe(missing.elements())))
    if unexpected:
        problems.append("unexpected {}".format(_describe(unexpected.elements())))
    return problems


def header_problems(spec: Spec, ind: Indication, reason: str) -> List[str]:
    problems = []
    if ind.reason != reason:
        problems.append("indicationReason {!r} instead of {!r}".format(ind.reason, reason))
    if ind.format != spec.message_format:
        problems.append("Indication Message Format {} instead of {}".format(ind.format, spec.message_format))
    if ind.event_time_ntp is None:
        problems.append("eventTime {!r} is not 16 hexadecimal digits".format(ind.event_time))
    return problems


def indication_problems(spec: Spec, ind: Indication, ctx: Context, state: State, reason: str,
                        changes: Optional[Changes] = None) -> List[str]:
    return header_problems(spec, ind, reason) + content_problems(ind, expected_entries(
        spec, ctx, state, reason, changes))


# ---------------------------------------------------------------- Checks


def check_admission(spec: Spec, outcome: Outcome, cause: Optional[str]) -> CheckResult:
    if spec.expect is Expect.REJECTED:
        return check("{} is rejected".format(spec.key),
                     [] if outcome is Outcome.REJECTED else ["subscription {}".format(outcome.value)],
                     "cause {}".format(cause))
    problems = [] if outcome is Outcome.ADMITTED else ["subscription {} (cause {})".format(outcome.value, cause)]
    return check("{} is admitted".format(spec.key), problems)


def layout_from(spec: Spec, ind: Optional[Indication], ctx: Context) -> Tuple[State, List[str]]:
    """The instances of the uponSubscription of a subscription that reports every attribute, and their problems."""
    if ind is None:
        return {}, ["no uponSubscription indication"]
    state: State = {}
    problems = header_problems(spec, ind, IND_REASON_UPON_SUBSCRIPTION)
    for r in ind.reported:
        problems += _layout_entry_problems(spec, r, state)
    scope = spec_scope(spec, ctx)
    for nci in scope:
        for structure in spec_structures(spec, nci):
            instances = state.setdefault((nci, structure), {})
            problems += ["{}: {}".format(_where(nci), p) for p in count_problems(structure, instances)]
    stray = sorted({nci for nci, _ in state} - set(scope), key=str)
    if stray:
        problems.append("cells {} are not in the RAN function definition".format(stray))
    return state, problems


def _layout_entry_problems(spec: Spec, r: ReportedStructure, state: State) -> List[str]:
    where = _where(r.nr_cell_id)
    structure = r.ran_cfg_structure_name
    problems = []
    if structure not in spec_structures(spec, r.nr_cell_id):
        return ["{}: unexpected structure {}".format(where, structure)]
    if r.change_type != CHANGE_TYPE_NONE or r.old_values is not None:
        problems.append("{}: changeType {} upon subscription".format(where, r.change_type))
    problems += ["{}: {}".format(where, p) for p in value_problems(structure, r.values)]
    instances = state.setdefault((r.nr_cell_id, structure), {})
    key = instance_key(structure, r.values)
    if key in instances:
        problems.append("{}: instance {} reported twice".format(where, key))
    instances[key] = r.values
    return problems


def _where(nci: Optional[int]) -> str:
    return "node" if nci is None else "cell {:09X}".format(nci)


def check_upon_subscription(spec: Spec, inds: List[Indication], ctx: Context) -> CheckResult:
    name = "{} uponSubscription".format(spec.key)
    if not inds:
        return check(name, ["no indication"])
    problems = indication_problems(spec, inds[0], ctx, ctx.state, IND_REASON_UPON_SUBSCRIPTION)
    if spec.attributes:
        for r in inds[0].reported:
            problems += value_problems(r.ran_cfg_structure_name, r.values, spec.attributes)
    return check(name, problems, "{} structures".format(len(inds[0].reported)))


def check_periodic_baseline(spec: Spec, inds: List[Indication], ctx: Context, count: int,
                            name: Optional[str] = None) -> CheckResult:
    name = name or "{} periodic without change".format(spec.key)
    problems = [] if len(inds) >= count else ["{} periodic indications instead of {}".format(len(inds), count)]
    for i, ind in enumerate(inds):
        problems += ["indication {}: {}".format(i, p)
                     for p in indication_problems(spec, ind, ctx, ctx.state, IND_REASON_PERIODIC)]
    return check(name, problems, "{} indications".format(len(inds)))


def check_silent(name: str, inds: List[Indication], reasons: Optional[Sequence[str]] = None) -> CheckResult:
    """PASS if no indication (of one of ``reasons``) arrived."""
    found = [i.reason for i in inds if reasons is None or i.reason in reasons]
    return check(name, ["{} indications: {}".format(len(found), sorted(set(map(str, found))))] if found else [])


def check_change_report(spec: Spec, ind: Optional[Indication], ctx: Context, step: ControlStep, reason: str,
                        before: State) -> CheckResult:
    name = "{} {} after the {}".format(spec.key, reason, step.name)
    if ind is None:
        return check(name, ["no {} indication".format(reason)])
    after = step.apply(before)
    return check(name, indication_problems(spec, ind, ctx, after, reason, step.changes()))


def check_periodic_sequence(spec: Spec, inds: List[Indication], ctx: Context, step: ControlStep,
                            before: State) -> CheckResult:
    """Report type all: periodic indications with the old values, then one with the change, then the new values."""
    name = "{} periodic reports the {} once".format(spec.key, step.name)
    after = step.apply(before)
    kinds = []
    for ind in inds:
        if not indication_problems(spec, ind, ctx, after, IND_REASON_PERIODIC, step.changes()):
            kinds.append("change")
        elif not indication_problems(spec, ind, ctx, after, IND_REASON_PERIODIC):
            kinds.append("new")
        elif not indication_problems(spec, ind, ctx, before, IND_REASON_PERIODIC):
            kinds.append("old")
        else:
            kinds.append("other")
    pattern = "".join(k[0] for k in kinds)
    stripped = pattern.lstrip("o")
    if kinds.count("change") == 1 and stripped.startswith("c") and set(stripped[1:]) <= {"n"}:
        return check(name, [], "sequence {}".format(pattern))
    problems = ["sequence {} (o: old values, c: change, n: new values, other: unexpected)".format(pattern)]
    for ind, kind in zip(inds, kinds):
        if kind == "other":
            problems += indication_problems(spec, ind, ctx, after, IND_REASON_PERIODIC, step.changes())[:1]
            break
    return check(name, problems)


def first_with_change(spec: Spec, inds: List[Indication], ctx: Context, step: ControlStep,
                      before: State) -> Optional[Indication]:
    after = step.apply(before)
    for ind in inds:
        if not content_problems(ind, expected_entries(spec, ctx, after, IND_REASON_PERIODIC, step.changes())):
            return ind
    return None


def check_cadence(spec: Spec, inds: List[Indication], period_s: float) -> CheckResult:
    times = [ntp_to_unix_s(i.event_time_ntp) for i in inds if i.event_time_ntp is not None]
    name = "{} periodic indications every {:g} s".format(spec.key, period_s)
    if len(times) < 2:
        return check(name, ["{} periodic indications".format(len(times))])
    median = statistics.median(b - a for a, b in zip(times, times[1:]))
    low, high = (period_s * f for f in CADENCE_TOLERANCE)
    return check(name, [] if low <= median <= high else ["median interval {:.3f} s".format(median)],
                 "median interval {:.3f} s".format(median))


def check_reasons(spec: Spec, inds: List[Indication], upon_change: int) -> CheckResult:
    """Change trigger: one uponSubscription first, then ``upon_change`` uponChange. Periodic trigger: periodic only."""
    reasons = [i.reason for i in inds]
    if spec.is_change_trigger:
        expected = Counter({IND_REASON_UPON_SUBSCRIPTION: 1, IND_REASON_UPON_CHANGE: upon_change})
        problems = [] if Counter(reasons) == +expected and reasons[:1] == [IND_REASON_UPON_SUBSCRIPTION] else [
            "reasons {}".format(dict(Counter(reasons)))]
        return check("{} sends uponSubscription first and {} uponChange".format(spec.key, upon_change), problems)
    problems = [] if set(reasons) <= {IND_REASON_PERIODIC} else ["reasons {}".format(dict(Counter(reasons)))]
    return check("{} sends periodic indications only".format(spec.key), problems)


def check_acks(acks: List[AckKind], expected: int) -> CheckResult:
    problems = [] if acks == [AckKind.ACK] * expected else ["{}".format([a.value for a in acks])]
    return check("RIC Control Acknowledge for each of the {} controls".format(expected), problems)
