import json
from dataclasses import dataclass
from enum import Enum
from typing import Collection, List, Optional, Tuple

from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import (
    encode_action_definition_cell_level,
    encode_event_trigger_node_change,
    encode_event_trigger_upon_change,
)
from xdevsm.sm_framework.py_oran.ccc.constants import (
    EVENT_TRIGGER_FORMAT_CELL_CHANGE,
    EVENT_TRIGGER_FORMAT_NODE_CHANGE,
    EVENT_TRIGGER_FORMAT_PERIODIC,
    IND_MSG_FORMAT_CELL_LEVEL,
    IND_MSG_FORMAT_NODE_LEVEL,
    REPORT_STYLE_CELL_LEVEL,
    REPORT_STYLE_NODE_LEVEL,
    REPORT_TYPE_ALL,
    REPORT_TYPE_CHANGE,
    STRUCT_O_BWP,
    STRUCT_O_GNBDUFUNCTION,
    STRUCT_O_NRCELLDU,
    STRUCT_O_RRM_POLICY_RATIO,
)

from ccc_test.structures import CELL_STRUCTURES, MAX_RATIO, MIN_RATIO


class Level(Enum):
    NODE = REPORT_STYLE_NODE_LEVEL
    CELL = REPORT_STYLE_CELL_LEVEL


class Trigger(Enum):
    NODE_CHANGE = EVENT_TRIGGER_FORMAT_NODE_CHANGE
    CELL_CHANGE = EVENT_TRIGGER_FORMAT_CELL_CHANGE
    PERIODIC = EVENT_TRIGGER_FORMAT_PERIODIC


class Expect(Enum):
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Spec:
    """One RIC subscription of the test, with one REPORT action."""

    key: str
    level: Level
    trigger: Trigger
    structure: str
    report_type: str
    attributes: Tuple[str, ...] = ()
    trigger_attributes: Tuple[str, ...] = ()
    cells: Tuple[dict, ...] = ()
    expect: Expect = Expect.ADMITTED
    encoded: Optional[Tuple[bytes, bytes]] = None
    priority_cell: Optional[dict] = None

    @property
    def is_change_trigger(self) -> bool:
        return self.trigger is not Trigger.PERIODIC

    @property
    def message_format(self) -> int:
        return IND_MSG_FORMAT_NODE_LEVEL if self.level is Level.NODE else IND_MSG_FORMAT_CELL_LEVEL

    def reacts_to(self, changed_attributes: Collection[str]) -> bool:
        """Whether a control that changes ``changed_attributes`` of O-RRMPolicyRatio instances makes this
        subscription report the change, as per the trigger attributes and the listed attributes."""
        changed = set(changed_attributes)
        if self.expect is Expect.REJECTED or self.structure != STRUCT_O_RRM_POLICY_RATIO or not changed:
            return False
        if self.is_change_trigger and self.trigger_attributes and not changed & set(self.trigger_attributes):
            return False
        if self.is_change_trigger and self.report_type == REPORT_TYPE_ALL:
            return True
        return not self.attributes or bool(changed & set(self.attributes))


def _key(level: Level, trigger: Trigger, structure: str, report_type: str, suffix: str = "") -> str:
    return "S{}-F{}-{}-{}{}".format(level.value, trigger.value, structure, report_type, suffix)


def _spec(level: Level, trigger: Trigger, structure: str, report_type: str, **kw) -> Spec:
    return Spec(_key(level, trigger, structure, report_type, kw.pop("suffix", "")), level, trigger, structure,
                report_type, **kw)


def _priority_action(cell: dict) -> bytes:
    """Action Definition Format 2 with an O-NRCellDU entry for all cells and an O-BWP entry for ``cell``."""
    out = json.loads(encode_action_definition_cell_level(STRUCT_O_NRCELLDU, []).to_bytes())
    one_cell = json.loads(encode_action_definition_cell_level(STRUCT_O_BWP, [], cell_global_id=cell).to_bytes())
    entries = "listOfCellConfigurationsToBeReportedForADF"
    out["actionDefinitionFormat"][entries] += one_cell["actionDefinitionFormat"][entries]
    return json.dumps(out, separators=(",", ":")).encode()


def build_plan(target_cell: dict) -> List[Spec]:
    """Every REPORT combination that OCUDU supports, the attribute and cell selections, and two inadmissible ones."""
    report_types = (REPORT_TYPE_ALL, REPORT_TYPE_CHANGE)
    plan = [_spec(Level.NODE, trigger, STRUCT_O_GNBDUFUNCTION, rt)
            for trigger in (Trigger.NODE_CHANGE, Trigger.PERIODIC) for rt in report_types]
    plan += [_spec(Level.CELL, trigger, structure, rt)
             for structure in CELL_STRUCTURES for trigger in (Trigger.CELL_CHANGE, Trigger.PERIODIC)
             for rt in report_types]
    plan += [
        _spec(Level.CELL, Trigger.CELL_CHANGE, STRUCT_O_RRM_POLICY_RATIO, REPORT_TYPE_CHANGE, suffix="-max-ratio-cell",
              attributes=(MAX_RATIO,), trigger_attributes=(MAX_RATIO,), cells=(target_cell,)),
        _spec(Level.CELL, Trigger.CELL_CHANGE, STRUCT_O_RRM_POLICY_RATIO, REPORT_TYPE_ALL, suffix="-on-min-ratio",
              trigger_attributes=(MIN_RATIO,)),
        _spec(Level.CELL, Trigger.CELL_CHANGE, STRUCT_O_BWP, REPORT_TYPE_ALL, suffix="-cell-priority",
              priority_cell=target_cell,
              encoded=(encode_event_trigger_upon_change(ran_cfg_structure_name=STRUCT_O_BWP).to_bytes(),
                       _priority_action(target_cell))),
        Spec("reject-S2-F1", Level.CELL, Trigger.NODE_CHANGE, STRUCT_O_RRM_POLICY_RATIO, REPORT_TYPE_ALL,
             expect=Expect.REJECTED,
             encoded=(encode_event_trigger_node_change().to_bytes(),
                      encode_action_definition_cell_level(STRUCT_O_RRM_POLICY_RATIO, []).to_bytes())),
        Spec("reject-F2-unknown-attribute", Level.CELL, Trigger.CELL_CHANGE, STRUCT_O_RRM_POLICY_RATIO,
             REPORT_TYPE_ALL, trigger_attributes=("arfcnDL",), expect=Expect.REJECTED),
    ]
    return plan
