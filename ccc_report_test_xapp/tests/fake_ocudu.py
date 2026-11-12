"""A Port that behaves like the E2SM-CCC REPORT service of OCUDU (lib/e2/e2sm/e2sm_ccc, feature/e2sm_ccc_report).

It encodes each subscription with the xDevSM encoders that the frame helpers use, decodes the JSON like
e2sm_ccc_report_codec.cpp, and builds the indications like e2sm_ccc_report_service_impl.cpp.
"""

import copy
import itertools
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import CccIndicationHeader, CccIndicationMessage
from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import (
    encode_action_definition_cell_level,
    encode_action_definition_node_level,
    encode_event_trigger_node_change,
    encode_event_trigger_periodic,
    encode_event_trigger_upon_change,
)

import ocudu_json as oj
from ccc_test.journal import AckKind, Journal, make_indication
from ccc_test.plan import Level, Spec, Trigger

NTP_UNIX_OFFSET_S = 2208988800
TICK_S = 0.005
LEVEL_OF = {"O-GNBDUFunction": "node", "O-NRCellDU": "cell", "O-BWP": "cell", "O-RRMPolicyRatio": "cell"}


class Fault(Enum):
    NONE = "none"
    NO_OLD_VALUES = "no old values"
    UPON_SUBSCRIPTION_FOR_PERIODIC = "uponSubscription for periodic triggers"


def ntp_now() -> int:
    now = time.time()
    return ((int(now) + NTP_UNIX_OFFSET_S) << 32) | int((now % 1) * (1 << 32))


def _json_key(structure: str, attribute: str) -> Optional[str]:
    for name, key in zip(oj.NAMES[structure], oj.KEYS[structure]):
        if attribute in (name, key):
            return key
    return None


def _key(structure: str, values: dict) -> str:
    if structure == "O-BWP":
        return "{}/{}".format(values["bwpContext"], values["isInitialBwp"])
    if structure == "O-RRMPolicyRatio":
        return "{}/{}".format(values["resourceType"], json.dumps(values["rRMPolicyMemberList"]))
    return ""


def _selection(entry: dict, attributes_key: str, level: str, as_objects: bool):
    """(structure, JSON keys, change only) of a trigger or action definition entry, or None if unsupported."""
    structure = entry["ranConfigurationStructureName"]
    if LEVEL_OF.get(structure) != level:
        return None
    keys = []
    for attribute in entry.get(attributes_key, []):
        name = attribute["attributeName"] if as_objects else attribute
        if not isinstance(name, str):
            return None
        key = _json_key(structure, name)
        if key is None:
            return None
        keys.append(key)
    report_type = entry.get("reportType")
    if as_objects and report_type not in ("all", "change"):
        return None
    return structure, keys, report_type == "change"


@dataclass
class _Sub:
    instance_id: int
    trigger: str
    period_s: float
    node_trigger: list
    cell_trigger: list
    level: str
    node_report: list
    cell_report: list
    last: dict
    pending_upon_subscription: bool
    next_period_s: float = 0.0
    sent: List[bytes] = field(default_factory=list)


class FakeOcudu:
    def __init__(self, journal: Journal, cells=(oj.TEST_CELL,), fault: Fault = Fault.NONE,
                 node_info: Optional[dict] = None, nof_prbs: int = oj.TEST_CELL_NOF_PRBS, min_ratio: int = 0):
        self.journal = journal
        self.fault = fault
        self.nof_prbs = nof_prbs
        self.min_ratio = min_ratio
        self.cells = list(cells)
        self.node_info = oj.e2mgr_info(oj.ran_function_definition(self.cells)) if node_info is None else node_info
        self.cfg = self._initial_cfg()
        self.change_time = ntp_now()
        self.function_id: Optional[int] = None
        self.period_ms = 1000
        self.controls: List[tuple] = []
        self._subs: Dict[str, _Sub] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _initial_cfg(self) -> dict:
        cells = {}
        bwps = [dict(oj.bwp(c), numberOfRBs=self.nof_prbs) for c in ("DL", "UL")]
        for i, cgi in enumerate(self.cells):
            structures = {"O-NRCellDU": {"": dict(oj.nr_cell_du(pci=i + 1), bwpList=bwps)},
                          "O-BWP": {_key("O-BWP", b): dict(b) for b in bwps},
                          "O-RRMPolicyRatio": {}}
            for rt in ("PRB_DL", "PRB_UL"):
                for sst in oj.SSTS:
                    values = oj.ratio(rt, sst, min_ratio=self.min_ratio)
                    structures["O-RRMPolicyRatio"][_key("O-RRMPolicyRatio", values)] = values
            cells[cgi["nRCellIdentity"]] = structures
        return {"node": {"O-GNBDUFunction": {"": dict(oj.NODE_VALUES)}}, "cells": cells}

    def close(self):
        self._stop.set()
        self._thread.join()

    # ------------------------------------------------------------ Port

    def wait_for_node(self, deadline_s: float) -> Optional[dict]:
        return self.node_info

    def set_function_id(self, function_id: int) -> None:
        self.function_id = function_id

    def subscribe(self, spec: Spec) -> Optional[str]:
        trigger_json, action_json = self._encode(spec)
        submgr_id = "sub-{}".format(spec.key)
        sub = self._admit(json.loads(trigger_json), json.loads(action_json))
        if sub is None:
            self.journal.on_rejected(submgr_id, "eventTriggerNotSupported")
            return submgr_id
        with self._lock:
            self._subs[submgr_id] = sub
        self.journal.on_resolved(submgr_id, sub.instance_id)
        return submgr_id

    def send_control(self, cell: dict, member: dict, min_ratio: int, max_ratio: int) -> None:
        self.controls.append((cell["nRCellIdentity"], member, min_ratio, max_ratio))
        nof_prbs = self.nof_prbs
        min_prb = int((1.0 * min_ratio / 100) * nof_prbs)
        max_prb = int((1.0 * max_ratio / 100) * nof_prbs)
        with self._lock:
            ratios = self.cfg["cells"][cell["nRCellIdentity"]]["O-RRMPolicyRatio"]
            for values in ratios.values():
                if values["rRMPolicyMemberList"] == [member]:
                    values["rRMPolicyMinRatio"] = min((min_prb * 100 + nof_prbs - 1) // nof_prbs, 100)
                    values["rRMPolicyMaxRatio"] = min((max_prb * 100 + nof_prbs - 1) // nof_prbs, 100)
                    values["rRMPolicyDedicatedRatio"] = 0
            self.change_time = ntp_now()
            for sub in self._subs.values():
                if sub.trigger != "periodic" and not sub.pending_upon_subscription:
                    self._evaluate_change(sub)
        self.journal.on_control_ack(AckKind.ACK)

    def unsubscribe_all(self) -> None:
        with self._lock:
            self._subs.clear()

    # ------------------------------------------------------------ encoding and admission

    def _encode(self, spec: Spec):
        if spec.encoded is not None:
            return spec.encoded
        attributes = list(spec.attributes)
        if spec.level is Level.NODE:
            trigger = encode_event_trigger_node_change(list(spec.trigger_attributes) or None, spec.structure) \
                if spec.trigger is Trigger.NODE_CHANGE else encode_event_trigger_periodic(self.period_ms)
            action = encode_action_definition_node_level(spec.structure, attributes, spec.report_type)
        else:
            trigger = encode_event_trigger_upon_change(list(spec.cells) or None, list(spec.trigger_attributes) or None,
                                                       spec.structure) \
                if spec.trigger is Trigger.CELL_CHANGE else encode_event_trigger_periodic(self.period_ms)
            cell = spec.cells[0] if len(spec.cells) == 1 else None
            action = encode_action_definition_cell_level(spec.structure, attributes, cell, spec.report_type)
        return trigger.to_bytes(), action.to_bytes()

    def _admit(self, trigger: dict, action: dict) -> Optional[_Sub]:
        fmt = trigger.get("eventTriggerDefinitionFormat") or {}
        node_trigger, cell_trigger, period_s = [], [], 0.1
        if "listOfNodeLevelConfigurationStructuresForEventTrigger" in fmt:
            kind = "node_change"
            node_trigger = [_selection(e, "listOfAttributes", "node", False)
                            for e in fmt["listOfNodeLevelConfigurationStructuresForEventTrigger"]]
            if not node_trigger or None in node_trigger:
                return None
        elif "listOfCellLevelConfigurationStructuresForEventTrigger" in fmt:
            kind = "cell_change"
            for entry in fmt["listOfCellLevelConfigurationStructuresForEventTrigger"]:
                selections = [_selection(e, "listOfAttributes", "cell", False)
                              for e in entry["listOfRANConfigurationStructuresForEventTrigger"]]
                if not selections or None in selections:
                    return None
                cell_trigger.append(((entry.get("cellGlobalId") or {}).get("nRCellIdentity"), selections))
            if not cell_trigger:
                return None
        elif fmt.get("period", 0) >= 10:
            kind, period_s = "periodic", fmt["period"] / 1000
        else:
            return None

        adf = action.get("actionDefinitionFormat") or {}
        node_report, cell_report = [], []
        if action.get("ricStyleType") == 1 and "listOfNodeLevelRANConfigurationStructuresForADF" in adf:
            level = "node"
            node_report = [_selection(e, "listOfAttributes", "node", True)
                           for e in adf["listOfNodeLevelRANConfigurationStructuresForADF"]]
            if not node_report or None in node_report:
                return None
        elif action.get("ricStyleType") == 2 and "listOfCellConfigurationsToBeReportedForADF" in adf:
            level = "cell"
            for entry in adf["listOfCellConfigurationsToBeReportedForADF"]:
                selections = [_selection(e, "listOfAttributes", "cell", True)
                              for e in entry["listOfCellLevelRANConfigurationStructuresForADF"]]
                if not selections or None in selections:
                    return None
                cell_report.append(((entry.get("cellGlobalId") or {}).get("nRCellIdentity"), selections))
        else:
            return None
        if (kind, level) in (("node_change", "cell"), ("cell_change", "node")):
            return None
        pending = kind != "periodic" or self.fault is Fault.UPON_SUBSCRIPTION_FOR_PERIODIC
        return _Sub(next(self._ids), kind, period_s, node_trigger, cell_trigger, level, node_report, cell_report,
                    copy.deepcopy(self.cfg), pending, time.monotonic() + period_s)

    # ------------------------------------------------------------ indications

    def _loop(self):
        while not self._stop.wait(TICK_S):
            with self._lock:
                for sub in self._subs.values():
                    self._collect(sub)

    def _collect(self, sub: _Sub):
        if sub.pending_upon_subscription:
            sub.pending_upon_subscription = False
            self._send(sub, "uponSubscription", ntp_now())
            return
        if sub.trigger == "periodic" and time.monotonic() >= sub.next_period_s:
            sub.next_period_s += sub.period_s
            self._send(sub, "periodic", ntp_now())

    def _evaluate_change(self, sub: _Sub):
        if self._triggered(sub):
            self._send(sub, "uponChange", self.change_time)
        else:
            sub.last = copy.deepcopy(self.cfg)

    def _triggered(self, sub: _Sub) -> bool:
        if sub.trigger == "node_change":
            return any(self._changed(sub.last["node"], self.cfg["node"], s) for s in sub.node_trigger)
        for nci, structures in self.cfg["cells"].items():
            for cell, selections in sub.cell_trigger:
                if cell is not None and int(cell, 16) != int(nci, 16):
                    continue
                if any(self._changed(sub.last["cells"][nci], structures, s) for s in selections):
                    return True
        return False

    @staticmethod
    def _select(values: dict, keys: list) -> dict:
        return dict(values) if not keys else {k: v for k, v in values.items() if k in keys}

    def _changed(self, old: dict, new: dict, selection) -> bool:
        structure, keys, _ = selection
        old_list, new_list = old.get(structure, {}), new.get(structure, {})
        if set(old_list) != set(new_list):
            return True
        return any(self._select(old_list[k], keys) != self._select(v, keys) for k, v in new_list.items())

    def _reported(self, old: dict, new: dict, selections, upon_subscription: bool) -> list:
        out = []
        for structure, keys, changes_only in selections:
            old_list = {} if upon_subscription else old.get(structure, {})
            for key, values in new.get(structure, {}).items():
                selected = self._select(values, keys)
                change, old_values = "none", None
                if not upon_subscription:
                    if key not in old_list:
                        change = "addition"
                    elif self._select(old_list[key], keys) != selected:
                        change, old_values = "modification", self._select(old_list[key], keys)
                if changes_only and change == "none" and not upon_subscription:
                    continue
                if self.fault is Fault.NO_OLD_VALUES:
                    old_values = None
                out.append(oj.structure(structure, selected, change, old_values))
            for key, values in old_list.items():
                if key not in new.get(structure, {}):
                    out.append(oj.structure(structure, self._select(values, keys), "deletion"))
        return out

    def _cell_selections(self, sub: _Sub, nci: str):
        all_cells = None
        for cell, selections in sub.cell_report:
            if cell is None:
                all_cells = all_cells or selections
            elif int(cell, 16) == int(nci, 16):
                return selections
        return all_cells

    def _send(self, sub: _Sub, reason: str, event_time: int):
        upon_subscription = reason == "uponSubscription"
        if sub.level == "node":
            structures = self._reported(sub.last["node"], self.cfg["node"], sub.node_report, upon_subscription)
            message = oj.node_message(structures) if structures else None
        else:
            cells = []
            for cgi in self.cells:
                nci = cgi["nRCellIdentity"]
                selections = self._cell_selections(sub, nci)
                if selections is None:
                    continue
                structures = self._reported(sub.last["cells"][nci], self.cfg["cells"][nci], selections,
                                            upon_subscription)
                if structures:
                    cells.append((cgi, structures))
            message = oj.cell_message(cells) if cells else None
        sub.last = copy.deepcopy(self.cfg)
        if message is None:
            return
        hdr = CccIndicationHeader(oj.header(reason, event_time))
        msg = CccIndicationMessage(message)
        self.journal.on_indication(sub.instance_id, make_indication(hdr, msg, self.journal.clock()))
