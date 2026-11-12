"""What OCUDU reports for each RAN Configuration Structure."""

import json
from typing import Dict, List, Optional, Sequence

from xdevsm.sm_framework.py_oran.ccc.constants import (
    RESOURCE_TYPE_PRB_DL,
    RESOURCE_TYPE_PRB_UL,
    STRUCT_O_BWP,
    STRUCT_O_GNBDUFUNCTION,
    STRUCT_O_NRCELLDU,
    STRUCT_O_RRM_POLICY_RATIO,
)

MAX_RATIO = "rRMPolicyMaxRatio"
MIN_RATIO = "rRMPolicyMinRatio"
DEDICATED_RATIO = "rRMPolicyDedicatedRatio"
MEMBER_LIST = "rRMPolicyMemberList"
RESOURCE_TYPE = "resourceType"
BWP_CONTEXT_DL = "DL"

NODE_STRUCTURES = (STRUCT_O_GNBDUFUNCTION,)
CELL_STRUCTURES = (STRUCT_O_NRCELLDU, STRUCT_O_BWP, STRUCT_O_RRM_POLICY_RATIO)

# Attribute names of O-RAN.WG3.TS.E2SM-CCC Section 8.8 that the RAN Function Definition lists.
ATTRIBUTE_NAMES: Dict[str, frozenset] = {
    STRUCT_O_GNBDUFUNCTION: frozenset({"gNBDUId", "gNBDUName", "gNBId", "gNBIdLength"}),
    STRUCT_O_NRCELLDU: frozenset({
        "cellLocalId", "operationalState", "administrativeState", "pLMNInfoList", "nRPCI", "nRTAC", "arfcnDL",
        "arfcnUL", "bSChannelBwDL", "ssbFrequency", "ssbPeriodicity", "ssbSubCarrierSpacing", "ssbOffset",
        "bSChannelBwUL", "bWPList"}),
    STRUCT_O_BWP: frozenset({"bwpContext", "isInitialBwp", "subCarrierSpacing", "startRB", "numberOfRBs"}),
    STRUCT_O_RRM_POLICY_RATIO: frozenset({RESOURCE_TYPE, MEMBER_LIST, MAX_RATIO, MIN_RATIO, DEDICATED_RATIO}),
}

# Property names of the JSON schema of Section 9.4.2 that the indications carry.
ATTRIBUTE_KEYS: Dict[str, frozenset] = {
    STRUCT_O_GNBDUFUNCTION: frozenset({"gnbDuId", "gnbDuName", "gnbId", "gnbIdLength"}),
    STRUCT_O_NRCELLDU: frozenset({
        "cellLocalId", "operationalState", "administrativeState", "plmnInfoList", "nrPci", "nrTac", "arfcnDL",
        "arfcnUL", "bSChannelBwDL", "ssbFrequency", "ssbPeriodicity", "ssbSubCarrierSpacing", "ssbOffset",
        "bSChannelBwUL", "bwpList"}),
    STRUCT_O_BWP: ATTRIBUTE_NAMES[STRUCT_O_BWP],
    STRUCT_O_RRM_POLICY_RATIO: ATTRIBUTE_NAMES[STRUCT_O_RRM_POLICY_RATIO],
}
# OCUDU leaves out gnbDuName when the DU has no name.
OPTIONAL_KEYS: Dict[str, frozenset] = {STRUCT_O_GNBDUFUNCTION: frozenset({"gnbDuName"})}

OPERATIONAL_STATES = ("ENABLED", "DISABLED")
ADMINISTRATIVE_STATES = ("LOCKED", "SHUTTINGDOWN", "UNLOCKED")
BWP_CONTEXTS = ("DL", "UL")
INITIAL_BWP = "INITIAL"
RESOURCE_TYPES = (RESOURCE_TYPE_PRB_DL, RESOURCE_TYPE_PRB_UL)
# A gNB ID has 22 to 32 bits, as per TS 38.413 Section 9.3.1.6.
GNB_ID_BITS = (22, 32)
MAX_PCI = 1007
PERCENT = 100

INSTANCES_PER_CELL = {STRUCT_O_NRCELLDU: 1, STRUCT_O_BWP: 2}


def instance_key(structure: str, values: dict) -> str:
    """Identity of an instance among the instances of its structure in one node or cell, as OCUDU defines it."""
    if structure == STRUCT_O_BWP:
        return "{}/{}".format(values.get("bwpContext"), values.get("isInitialBwp"))
    if structure == STRUCT_O_RRM_POLICY_RATIO:
        return "{}/{}".format(values.get(RESOURCE_TYPE), json.dumps(values.get(MEMBER_LIST), sort_keys=True))
    return ""


def member_key(member: dict) -> str:
    return json.dumps([member], sort_keys=True)


def value_problems(structure: str, values: dict, listed: Sequence[str] = ()) -> List[str]:
    """Problems of the values of one reported instance. ``listed`` are the attributes of the action definition."""
    keys = set(values)
    if listed:
        if keys != set(listed):
            return ["{} reports {} instead of the listed {}".format(structure, sorted(keys), sorted(listed))]
        return []
    expected = ATTRIBUTE_KEYS.get(structure, frozenset())
    required = expected - OPTIONAL_KEYS.get(structure, frozenset())
    problems = []
    if keys - expected:
        problems.append("{} reports unexpected attributes {}".format(structure, sorted(keys - expected)))
    if required - keys:
        problems.append("{} misses attributes {}".format(structure, sorted(required - keys)))
    return problems + _semantic_problems(structure, values)


def _semantic_problems(structure: str, values: dict) -> List[str]:
    if structure == STRUCT_O_GNBDUFUNCTION:
        bits = values.get("gnbIdLength")
        gnb_id = values.get("gnbId")
        if not isinstance(bits, int) or not GNB_ID_BITS[0] <= bits <= GNB_ID_BITS[1]:
            return ["gnbIdLength {!r} is not in {}..{}".format(bits, *GNB_ID_BITS)]
        if not isinstance(gnb_id, int) or not 0 <= gnb_id < 1 << bits:
            return ["gnbId {!r} does not fit in {} bits".format(gnb_id, bits)]
        return []
    if structure == STRUCT_O_NRCELLDU:
        problems = []
        if values.get("operationalState") not in OPERATIONAL_STATES:
            problems.append("operationalState {!r}".format(values.get("operationalState")))
        if values.get("administrativeState") not in ADMINISTRATIVE_STATES:
            problems.append("administrativeState {!r}".format(values.get("administrativeState")))
        if not isinstance(values.get("nrPci"), int) or not 0 <= values["nrPci"] <= MAX_PCI:
            problems.append("nrPci {!r}".format(values.get("nrPci")))
        if len(values.get("bwpList") or []) != INSTANCES_PER_CELL[STRUCT_O_BWP]:
            problems.append("bwpList does not hold the initial DL and UL BWPs")
        return problems
    if structure == STRUCT_O_BWP:
        if values.get("bwpContext") not in BWP_CONTEXTS or values.get("isInitialBwp") != INITIAL_BWP:
            return ["O-BWP {}/{} is not an initial DL or UL BWP".format(
                values.get("bwpContext"), values.get("isInitialBwp"))]
        return []
    if structure == STRUCT_O_RRM_POLICY_RATIO:
        return _ratio_problems(values)
    return []


def _ratio_problems(values: dict) -> List[str]:
    problems = []
    if values.get(RESOURCE_TYPE) not in RESOURCE_TYPES:
        problems.append("resourceType {!r}".format(values.get(RESOURCE_TYPE)))
    if len(values.get(MEMBER_LIST) or []) != 1:
        problems.append("rRMPolicyMemberList does not hold one member")
    ratios = [values.get(k) for k in (DEDICATED_RATIO, MIN_RATIO, MAX_RATIO)]
    numbers = [r for r in ratios if isinstance(r, int)]
    if len(numbers) != len(ratios) or not 0 <= numbers[0] <= numbers[1] <= numbers[2] <= PERCENT:
        problems.append("ratios dedicated {}, min {}, max {} are not ordered in 0..100".format(*ratios))
    return problems


def count_problems(structure: str, instances: Dict[str, dict]) -> List[str]:
    """Problems of the set of instances of one structure in one cell."""
    expected = INSTANCES_PER_CELL.get(structure)
    if expected is not None and len(instances) != expected:
        return ["{} instances of {} instead of {}".format(len(instances), structure, expected)]
    if structure != STRUCT_O_RRM_POLICY_RATIO:
        return []
    # The DU applies the limits of a member to both directions, so PRB_DL and PRB_UL hold the same values.
    by_type = {t: {} for t in RESOURCE_TYPES}
    for values in instances.values():
        rest = {k: v for k, v in values.items() if k != RESOURCE_TYPE}
        member = json.dumps(values.get(MEMBER_LIST), sort_keys=True)
        by_type.setdefault(str(values.get(RESOURCE_TYPE)), {})[member] = rest
    if by_type[RESOURCE_TYPE_PRB_DL] != by_type[RESOURCE_TYPE_PRB_UL]:
        return ["the PRB_DL and PRB_UL instances of O-RRMPolicyRatio differ"]
    if not instances:
        return ["no O-RRMPolicyRatio instance: the cell has no RRM policy member (cell_cfg slicing)"]
    return []


def expected_ratio(requested: int, nof_prbs: Optional[int]) -> int:
    """Ratio that OCUDU reports after a control requests ``requested`` percent of a cell of ``nof_prbs`` PRBs.

    The OCUDU DU truncates the ratio to PRBs in double precision and reports the smallest ratio of that PRB count.
    """
    if not nof_prbs:
        return requested
    prbs = int((1.0 * requested / PERCENT) * nof_prbs)
    return min((prbs * PERCENT + nof_prbs - 1) // nof_prbs, PERCENT)
