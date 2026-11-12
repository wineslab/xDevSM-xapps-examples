import logging
from typing import Callable, Dict, List, NoReturn, Optional, Protocol, Set, Tuple

from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import decode_ran_function_def
from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import nr_cell_id_of
from xdevsm.sm_framework.py_oran.ccc.constants import (
    IND_REASON_PERIODIC,
    IND_REASON_UPON_CHANGE,
    IND_REASON_UPON_SUBSCRIPTION,
    REPORT_TYPE_ALL,
    REPORT_TYPE_CHANGE,
    SM_CCC_OID_OCUDU,
    STRUCT_O_BWP,
    STRUCT_O_RRM_POLICY_RATIO,
)

from ccc_test import checks
from ccc_test.checks import ControlStep, Context, State
from ccc_test.config import RunConfig
from ccc_test.journal import Indication, Journal, Outcome
from ccc_test.plan import Expect, Spec, Trigger, build_plan
from ccc_test.report import CheckResult, Report, check
from ccc_test.structures import (
    BWP_CONTEXT_DL,
    CELL_STRUCTURES,
    DEDICATED_RATIO,
    MAX_RATIO,
    MEMBER_LIST,
    MIN_RATIO,
    NODE_STRUCTURES,
    RESOURCE_TYPE,
    expected_ratio,
    instance_key,
)

logger = logging.getLogger(__name__)

# Max ratios that the control tries, after the configured one, until one changes the reported value.
FALLBACK_MAX_RATIOS = (50, 25, 75, 100, 10)
RUN_COMPLETES = "run completes"


class Port(Protocol):
    """What the scenario needs from the RIC."""

    def wait_for_node(self, deadline_s: float) -> Optional[dict]:
        """e2mgr information of the connected E2 node, or None at the deadline."""

    def set_function_id(self, function_id: int) -> None: ...

    def subscribe(self, spec: Spec) -> Optional[str]:
        """submgr SubscriptionId, or None if submgr did not answer."""

    def send_control(self, cell: dict, member: dict, min_ratio: int, max_ratio: int) -> None: ...

    def unsubscribe_all(self) -> None: ...


class _Stop(Exception):
    pass


class Scenario:
    def __init__(self, port: Port, journal: Journal, cfg: RunConfig):
        self.port = port
        self.journal = journal
        self.cfg = cfg
        self.report = Report()
        self.ctx = Context([], period_s=cfg.period_s)
        self.plan: List[Spec] = []
        self.admitted: List[Spec] = []
        self.steps: List[ControlStep] = []
        self.states_before: List[State] = []
        self.reacting: List[List[Spec]] = []
        self.sent_controls = 0
        self._restore: Optional[Tuple[dict, dict, int, int]] = None

    def run(self) -> Report:
        try:
            self._run()
        except _Stop:
            pass
        finally:
            self._restore_if_needed()
            self.port.unsubscribe_all()
        logger.info(self.report.summary())
        return self.report

    # ------------------------------------------------------------ helpers

    def _add(self, result: CheckResult) -> CheckResult:
        return self.report.add(result)

    def _fatal(self, name: str, detail: str) -> NoReturn:
        self._add(CheckResult(name, False, detail))
        raise _Stop()

    def _deadline(self, seconds: float) -> float:
        return self.journal.clock() + seconds

    def _wait(self, predicate: Callable[[], bool], deadline_s: float) -> bool:
        ok = self.journal.wait_until(predicate, deadline_s)
        if self.journal.aborted:
            self._fatal(RUN_COMPLETES, "aborted by a signal")
        return ok

    def _inds(self, spec: Spec, since_s: float = float("-inf"), until_s: float = float("inf")) -> List[Indication]:
        return [i for i in self.journal.indications(spec.key, since_s) if i.arrival_s < until_s]

    def _first(self, spec: Spec, since_s: float, reason: str) -> Optional[Indication]:
        return next((i for i in self._inds(spec, since_s) if i.reason == reason), None)

    def _of(self, structure: str, trigger: Trigger, report_type: str) -> Optional[Spec]:
        """The admitted subscription of the plain combination, without attribute or cell selection."""
        for spec in self.admitted:
            plain = not (spec.encoded or spec.attributes or spec.trigger_attributes or spec.cells)
            if plain and (spec.structure, spec.report_type, spec.trigger) == (structure, report_type, trigger):
                return spec
        return None

    def _layout_spec(self, structure: str) -> Spec:
        spec = self._of(structure, _change_trigger(structure), REPORT_TYPE_ALL)
        if spec is None:
            self._fatal("{} layout".format(structure), "its change subscription with report type all failed")
        return spec

    def _reaction_count(self, spec: Spec) -> int:
        return sum(1 for reacting in self.reacting if spec in reacting)

    # ------------------------------------------------------------ phases

    def _run(self) -> None:
        cells, target = self._discover()
        self.ctx = Context(cells, period_s=self.cfg.period_s)
        self.plan = build_plan(target)
        self._subscribe()
        self._baseline()
        self._control(target)
        self._final()

    def _discover(self) -> Tuple[List[dict], dict]:
        info = self.port.wait_for_node(self._deadline(self.cfg.e2_node_timeout_s))
        if self.journal.aborted:
            self._fatal(RUN_COMPLETES, "aborted by a signal")
        if not info:
            self._fatal("E2 node is connected", "no connected E2 node {} within {:g} s".format(
                self.cfg.gnb_target or "of any name", self.cfg.e2_node_timeout_s))
        self._add(check("E2 node is connected", [], info.get("ranName", "")))
        functions = ((info.get("gnb") or {}).get("ranFunctions")) or []
        oid_check = "E2 node announces E2SM-CCC with the OCUDU OID {}".format(SM_CCC_OID_OCUDU)
        ccc = [f for f in functions if f.get("ranFunctionOid") == SM_CCC_OID_OCUDU]
        if not ccc:
            self._fatal(oid_check, "OIDs {}".format([f.get("ranFunctionOid") for f in functions]))
        function_id = ccc[0]["ranFunctionId"]
        self._add(check(oid_check, [], "RAN function ID {}".format(function_id)))
        self.port.set_function_id(function_id)
        try:
            definition = decode_ran_function_def(info)
        except ValueError as e:
            self._fatal("RAN function definition is hex-encoded JSON", str(e))
        for result in checks.check_ran_function_def(definition):
            self._add(result)
        cells = checks.ran_function_cells(definition)
        if not cells:
            self._fatal("RAN function definition lists a cell", "no cell with an NR Cell Identity")
        targets = [c for c in cells if self.cfg.nci is None or nr_cell_id_of(c) == self.cfg.nci]
        if not targets:
            self._fatal("cell to control is in the RAN function definition", "NCI {:#x} not in {}".format(
                self.cfg.nci, [c.get("nRCellIdentity") for c in cells]))
        return cells, targets[0]

    def _subscribe(self) -> None:
        for spec in self.plan:
            self.journal.on_subscribed(spec.key, self.port.subscribe(spec))
        pending = lambda: [s for s in self.plan if self.journal.outcome(s.key) is Outcome.PENDING]
        self._wait(lambda: not pending(), self._deadline(self.cfg.subscription_timeout_s))
        for spec in self.plan:
            outcome = self.journal.outcome(spec.key)
            self._add(checks.check_admission(spec, outcome, self.journal.rejection_cause(spec.key)))
            if outcome is Outcome.ADMITTED and spec.expect is Expect.ADMITTED:
                self.admitted.append(spec)

    def _baseline(self) -> None:
        cfg = self.cfg
        change = [s for s in self.admitted if s.is_change_trigger]
        periodic_all = [s for s in self.admitted if not s.is_change_trigger and s.report_type == REPORT_TYPE_ALL]
        ready = lambda: all(self._inds(s) for s in change) and all(
            len(self._inds(s)) >= cfg.periodic_count for s in periodic_all)
        self._wait(ready, self._deadline(cfg.indication_timeout_s + (cfg.periodic_count + 1) * cfg.period_s))
        control_start = self.journal.clock()

        layouts = [self._layout_spec(structure) for structure in NODE_STRUCTURES + CELL_STRUCTURES]
        for spec in layouts:
            first = next(iter(self._inds(spec)), None)
            state, problems = checks.layout_from(spec, first, self.ctx)
            self.ctx.state.update(state)
            self._add(check("{} uponSubscription reports every instance and attribute".format(spec.key), problems,
                            "{} instances".format(sum(len(v) for v in state.values()))))
        for spec in self.admitted:
            inds = self._inds(spec, until_s=control_start)
            if spec.is_change_trigger and spec not in layouts:
                self._add(checks.check_upon_subscription(spec, inds, self.ctx))
            if spec.is_change_trigger:
                self._add(checks.check_silent("{} sends no uponChange before the control".format(spec.key), inds,
                                              (IND_REASON_UPON_CHANGE,)))
            elif spec.report_type == REPORT_TYPE_CHANGE:
                self._add(checks.check_silent("{} sends nothing before the control".format(spec.key), inds))
            elif spec.structure == STRUCT_O_RRM_POLICY_RATIO:
                self._add(checks.check_periodic_baseline(spec, inds, self.ctx, cfg.periodic_count))

    def _control(self, target: dict) -> None:
        nci = nr_cell_id_of(target)
        if nci is None:
            self._fatal("cell to control has an NR Cell Identity", "{}".format(target))
        member, original = self._member(target, nci)
        nof_prbs = self._nof_prbs(nci)
        orig_min = original[0][1][MIN_RATIO]
        orig_max = original[0][1][MAX_RATIO]
        max_ratio = self._pick_max_ratio(orig_min, orig_max, nof_prbs)
        if max_ratio is None:
            self._fatal("a control can change the rRMPolicyMaxRatio of the member",
                        "min ratio {}, max ratio {}".format(orig_min, orig_max))
        logger.info("controlling cell %09X member %s: rRMPolicyMaxRatio %d -> %d (cell of %s PRBs)",
                    nci, member["snssai"], orig_max, max_ratio, nof_prbs)
        self._restore = (target, member, orig_min, orig_max)
        old = dict(original)
        new = {k: _after_control(v, orig_min, max_ratio, nof_prbs) for k, v in original}
        self._step("control", target, nci, member, (orig_min, max_ratio), old, new)
        restored = {k: _after_control(v, orig_min, orig_max, nof_prbs) for k, v in original}
        self._step("restore", target, nci, member, (orig_min, orig_max), new, restored)
        if restored != old:
            logger.warning("the DU cannot restore the member exactly: %s instead of %s", restored, old)
        final = self._layout_spec(STRUCT_O_RRM_POLICY_RATIO)
        last = next(iter(reversed(self._inds(final, self.steps[-1].sent_s))), None)
        reported = {} if last is None else {k: r.values for k in old for r in last.structures(nci)
                                            if r.ran_cfg_structure_name == STRUCT_O_RRM_POLICY_RATIO
                                            and _key_of(r.values) == k}
        problems = [] if reported == restored else ["reported {} instead of {}".format(reported, restored)]
        self._add(check("O-RRMPolicyRatio of the member has its restored values", problems,
                        "equal to the uponSubscription values" if restored == old else "the DU re-quantized them"))

    def _member(self, target: dict, nci: int) -> Tuple[dict, List[Tuple[str, dict]]]:
        """The member to control and its PRB_DL and PRB_UL instances, as (instance key, values)."""
        instances = self.ctx.state.get((nci, STRUCT_O_RRM_POLICY_RATIO), {})
        plmn = target.get("plmnIdentity")
        for _, values in sorted(instances.items()):
            member = (values.get(MEMBER_LIST) or [{}])[0]
            snssai = member.get("snssai") or {}
            if member.get("plmnId") != plmn or values.get(RESOURCE_TYPE) != self.cfg.resource_type:
                continue
            if self.cfg.sst is not None and snssai.get("sst") != self.cfg.sst:
                continue
            if self.cfg.sd is not None and str(snssai.get("sd", "")).upper() != self.cfg.sd.upper():
                continue
            both = [(k, v) for k, v in sorted(instances.items()) if v.get(MEMBER_LIST) == [member]]
            return member, both
        self._fatal("cell has an RRM policy member to control",
                    "no {} O-RRMPolicyRatio of PLMN {} with sst {} sd {}".format(
                        self.cfg.resource_type, plmn, self.cfg.sst, self.cfg.sd))

    def _nof_prbs(self, nci: int) -> Optional[int]:
        for values in self.ctx.state.get((nci, STRUCT_O_BWP), {}).values():
            if values.get("bwpContext") == BWP_CONTEXT_DL:
                return values.get("numberOfRBs")
        return None

    def _pick_max_ratio(self, orig_min: int, orig_max: int, nof_prbs: Optional[int]) -> Optional[int]:
        for ratio in (self.cfg.control_max_ratio,) + FALLBACK_MAX_RATIOS:
            if ratio >= max(orig_min, 1) and expected_ratio(ratio, nof_prbs) != orig_max:
                return ratio
        return None

    def _step(self, name: str, target: dict, nci: int, member: dict, ratios: Tuple[int, int],
              old: Dict[str, dict], new: Dict[str, dict]) -> None:
        cfg = self.cfg
        before: State = self.ctx.state
        acks_before = len(self.journal.acks())
        step = ControlStep(name, nci, old, new, self.journal.clock())
        reacting = [s for s in self.admitted if s.reacts_to(_changed_attributes(old, new))]
        self.steps.append(step)
        self.states_before.append(before)
        self.reacting.append(reacting)
        self.port.send_control(target, member, *ratios)
        self.sent_controls += 1
        self._wait(lambda: len(self.journal.acks()) > acks_before, self._deadline(cfg.control_ack_timeout_s))

        changes = [s for s in reacting if s.is_change_trigger]
        per_change = [s for s in reacting if not s.is_change_trigger and s.report_type == REPORT_TYPE_CHANGE]
        per_all = [s for s in reacting if not s.is_change_trigger and s.report_type == REPORT_TYPE_ALL]
        since = step.sent_s
        done = lambda: (all(self._first(s, since, IND_REASON_UPON_CHANGE) for s in changes)
                        and all(self._inds(s, since) for s in per_change)
                        and all(checks.first_with_change(s, self._inds(s, since), self.ctx, step, before)
                                for s in per_all))
        self._wait(done, self._deadline(cfg.indication_timeout_s + 2 * cfg.period_s))

        upon_change = {s.key: self._first(s, since, IND_REASON_UPON_CHANGE) for s in changes}
        for spec in changes:
            self._add(checks.check_change_report(spec, upon_change[spec.key], self.ctx, step,
                                                 IND_REASON_UPON_CHANGE, before))
            subscription = self._first(spec, float("-inf"), IND_REASON_UPON_SUBSCRIPTION)
            self._add(checks.check_not_before("{} uponChange of the {} is after its uponSubscription".format(
                spec.key, name), upon_change[spec.key], subscription))
        self._add(checks.check_same_event_time(
            "uponChange of the {} has one eventTime in every subscription".format(name), upon_change))
        reference = next(iter(upon_change.values()), None)
        for spec in per_change:
            ind = next(iter(self._inds(spec, since)), None)
            self._add(checks.check_change_report(spec, ind, self.ctx, step, IND_REASON_PERIODIC, before))
            self._add(checks.check_not_before("{} periodic change of the {} is not before its uponChange".format(
                spec.key, name), ind, reference))
        for spec in per_all:
            ind = checks.first_with_change(spec, self._inds(spec, since), self.ctx, step, before)
            self._add(checks.check_not_before("{} periodic change of the {} is not before its uponChange".format(
                spec.key, name), ind, reference))
        if len(self.steps) > 1 and changes:
            previous = self._first(changes[0], self.steps[-2].sent_s, IND_REASON_UPON_CHANGE)
            self._add(checks.check_not_before("uponChange of the {} is after the one of the {}".format(
                name, self.steps[-2].name), reference, previous))
        self.ctx.state = step.apply(before)

    def _final(self) -> None:
        cfg = self.cfg
        self._wait(lambda: False, self._deadline(2 * cfg.period_s))
        bounds = [s.sent_s for s in self.steps] + [float("inf")]
        for spec in self.admitted:
            inds = self._inds(spec)
            reactions = self._reaction_count(spec)
            self._add(checks.check_reasons(spec, inds, reactions if spec.is_change_trigger else 0))
            self._add(checks.check_event_time_order(spec, inds))
            if spec.is_change_trigger:
                continue
            if spec.report_type == REPORT_TYPE_ALL:
                self._add(checks.check_cadence(spec, inds, cfg.period_s))
            if spec.report_type == REPORT_TYPE_CHANGE:
                self._add(check("{} sends one periodic indication per change".format(spec.key),
                                [] if len(inds) == reactions else ["{} indications for {} changes".format(
                                    len(inds), reactions)]))
                continue
            if not reactions:
                self._add(checks.check_periodic_baseline(spec, inds, self.ctx, cfg.periodic_count))
                continue
            for i, step in enumerate(self.steps):
                if spec in self.reacting[i]:
                    window = self._inds(spec, step.sent_s, bounds[i + 1])
                    self._add(checks.check_periodic_sequence(spec, window, self.ctx, step, self.states_before[i]))
        for spec in self.plan:
            if spec.expect is Expect.REJECTED:
                self._add(checks.check_silent("{} sends nothing".format(spec.key), self.journal.indications(spec.key)))
        self._add(checks.check_acks(self.journal.acks(), len(self.steps)))
        unknown = self.journal.unknown_instances()
        if unknown:
            logger.warning("indications of E2EventInstanceIds %s that this run did not subscribe", unknown)

    def _restore_if_needed(self) -> None:
        if self._restore is None or self.sent_controls != 1:
            return
        target, member, orig_min, orig_max = self._restore
        logger.warning("restoring rRMPolicyMinRatio %d and rRMPolicyMaxRatio %d after an interrupted run",
                       orig_min, orig_max)
        try:
            self.port.send_control(target, member, orig_min, orig_max)
        except Exception:
            logger.exception("restore control not sent")


def _change_trigger(structure: str) -> Trigger:
    return Trigger.NODE_CHANGE if structure in NODE_STRUCTURES else Trigger.CELL_CHANGE


def _key_of(values: dict) -> str:
    return instance_key(STRUCT_O_RRM_POLICY_RATIO, values)


def _changed_attributes(old: Dict[str, dict], new: Dict[str, dict]) -> Set[str]:
    return {k for key in old for k in set(old[key]) | set(new[key]) if old[key].get(k) != new[key].get(k)}


def _after_control(values: dict, min_ratio: int, max_ratio: int, nof_prbs: Optional[int]) -> dict:
    """Values that OCUDU reports after a control: the DU keeps no dedicated PRBs."""
    out = dict(values)
    out[MIN_RATIO] = expected_ratio(min_ratio, nof_prbs)
    out[MAX_RATIO] = expected_ratio(max_ratio, nof_prbs)
    out[DEDICATED_RATIO] = 0
    return out
