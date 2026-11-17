"""JSON of the E2SM-CCC REPORT unit tests of OCUDU (tests/unittests/e2/e2sm_ccc_report_test.cpp) and of its
E2SM-CCC README (lib/e2/e2sm/e2sm_ccc/README.md), branch feature/e2sm_ccc_report."""

import copy
import json
from typing import Optional

PLMN = {"mcc": "001", "mnc": "01"}
# gNB ID 411 with 22 bits, cell local ID 0.
TEST_NCI = 0x00066C000
TEST_CELL = {"plmnIdentity": PLMN, "nRCellIdentity": "00066C000"}
OTHER_CELL = {"plmnIdentity": PLMN, "nRCellIdentity": "00066C001"}
TEST_CELL_NOF_PRBS = 106
SSTS = (1, 2, 3)

NODE_TRIGGER = (
    '{"eventTriggerDefinitionFormat":{"listOfNodeLevelConfigurationStructuresForEventTrigger":['
    '{"ranConfigurationStructureName":"O-GNBDUFunction"}]}}'
)
CELL_TRIGGER = (
    '{"eventTriggerDefinitionFormat":{"listOfCellLevelConfigurationStructuresForEventTrigger":[{'
    '"listOfRANConfigurationStructuresForEventTrigger":[{"ranConfigurationStructureName":"O-RRMPolicyRatio"}]}]}}'
)
PERIODIC_TRIGGER = '{"eventTriggerDefinitionFormat":{"period":1000}}'
NODE_ACTION = (
    '{"ricStyleType":1,"actionDefinitionFormat":{"listOfNodeLevelRANConfigurationStructuresForADF":['
    '{"reportType":"all","ranConfigurationStructureName":"O-GNBDUFunction"}]}}'
)
CELL_ACTION = (
    '{"ricStyleType":2,"actionDefinitionFormat":{"listOfCellConfigurationsToBeReportedForADF":[{'
    '"listOfCellLevelRANConfigurationStructuresForADF":[{"reportType":"all",'
    '"ranConfigurationStructureName":"O-RRMPolicyRatio"}]}]}}'
)
README_ACTION = (
    '{"ricStyleType": 2, "actionDefinitionFormat": {"listOfCellConfigurationsToBeReportedForADF": [\n'
    '  {"listOfCellLevelRANConfigurationStructuresForADF": [\n'
    '    {"reportType": "change", "ranConfigurationStructureName": "O-RRMPolicyRatio",\n'
    '     "listOfAttributes": [{"attributeName": "rRMPolicyMaxRatio"}]}]}]}}'
)
README_HEADER = '{"indicationHeaderFormat": {"indicationReason": "uponChange", "eventTime": "ECA8B1C2A3D70A3D"}}'
README_MESSAGE = (
    '{"indicationMessageFormat": {"listOfCellsReported": [{\n'
    '  "cellGlobalId": {"plmnIdentity": {"mcc": "001", "mnc": "01"}, "nRCellIdentity": "00066C000"},\n'
    '  "listOfConfigurationStructuresReported": [\n'
    '    {"changeType": "modification", "ranConfigurationStructureName": "O-RRMPolicyRatio",\n'
    '     "valuesOfAttributes": {"ranConfigurationStructure": {"rRMPolicyMaxRatio": 50}},\n'
    '     "oldValuesOfAttributes": {"ranConfigurationStructure": {"rRMPolicyMaxRatio": 100}}},\n'
    '    {"changeType": "modification", "ranConfigurationStructureName": "O-RRMPolicyRatio",\n'
    '     "valuesOfAttributes": {"ranConfigurationStructure": {"rRMPolicyMaxRatio": 50}},\n'
    '     "oldValuesOfAttributes": {"ranConfigurationStructure": {"rRMPolicyMaxRatio": 100}}}]}]}}'
)

NODE_VALUES = {"gnbDuId": 7, "gnbDuName": "ocudu-du", "gnbId": 411, "gnbIdLength": 22}


def member(sst: int) -> dict:
    return {"plmnId": dict(PLMN), "snssai": {"sst": sst, "sd": "000001"}}


def bwp(context: str) -> dict:
    return {"bwpContext": context, "isInitialBwp": "INITIAL", "subCarrierSpacing": 15, "startRB": 0,
            "numberOfRBs": TEST_CELL_NOF_PRBS}


def nr_cell_du(pci: int = 1) -> dict:
    return {
        "cellLocalId": 0, "operationalState": "ENABLED", "administrativeState": "UNLOCKED",
        "plmnInfoList": [member(sst) for sst in SSTS], "nrPci": pci, "nrTac": 7, "arfcnDL": 368500,
        "arfcnUL": 349500, "bSChannelBwDL": 20, "ssbFrequency": 368410, "ssbPeriodicity": 10,
        "ssbSubCarrierSpacing": 15, "ssbOffset": 0, "bSChannelBwUL": 20, "bwpList": [bwp("DL"), bwp("UL")],
    }


def ratio(resource_type: str, sst: int, min_ratio: int = 0, max_ratio: int = 100) -> dict:
    return {"resourceType": resource_type, "rRMPolicyMemberList": [member(sst)], "rRMPolicyMaxRatio": max_ratio,
            "rRMPolicyMinRatio": min_ratio, "rRMPolicyDedicatedRatio": 0}


def structure(name: str, values: dict, change_type: str = "none", old: Optional[dict] = None) -> dict:
    out = {"changeType": change_type, "ranConfigurationStructureName": name,
           "valuesOfAttributes": {"ranConfigurationStructure": copy.deepcopy(values)}}
    if old is not None:
        out["oldValuesOfAttributes"] = {"ranConfigurationStructure": copy.deepcopy(old)}
    return out


def cell_structures() -> list:
    """The nine structures of the test cell, as in cell_level_report_holds_the_du_cell_configuration."""
    out = [structure("O-NRCellDU", nr_cell_du()), structure("O-BWP", bwp("DL")), structure("O-BWP", bwp("UL"))]
    out += [structure("O-RRMPolicyRatio", ratio(rt, sst)) for rt in ("PRB_DL", "PRB_UL") for sst in SSTS]
    return out


def header(reason: str, ntp: int) -> bytes:
    return json.dumps({"indicationHeaderFormat": {"indicationReason": reason, "eventTime": "{:016X}".format(ntp)}}
                      ).encode()


def node_message(structures: list) -> bytes:
    return json.dumps({"indicationMessageFormat": {"listOfConfigurationStructuresReported": structures}}).encode()


def cell_message(cells: list) -> bytes:
    """``cells``: (cell global ID, structures) pairs."""
    return json.dumps({"indicationMessageFormat": {"listOfCellsReported": [
        {"cellGlobalId": cgi, "listOfConfigurationStructuresReported": s} for cgi, s in cells]}}).encode()


def _services(level_format: int, controllable: bool) -> dict:
    out = {
        "eventTrigger": {"listOfSupportedEventTriggerStyles": [
            {"eventTriggerStyleType": 1, "eventTriggerStyleName": "E2 Node Configuration Change",
             "eventTriggerFormatType": level_format},
            {"eventTriggerStyleType": 2, "eventTriggerStyleName": "Periodic", "eventTriggerFormatType": 3}]},
        "reportService": {"listOfSupportedReportStyles": [{
            "reportServiceStyleType": level_format,
            "reportServiceStyleName": "Node-Level Configuration" if level_format == 1 else "Cell-Level Configuration",
            "listOfSupportedEventTriggerStylesForReportStyle": [{"eventTriggerStyleType": 1},
                                                                {"eventTriggerStyleType": 2}],
            "reportServiceActionDefinitionFormatType": level_format,
            "reportServiceIndicationHeaderFormatType": 1,
            "reportServiceIndicationMessageFormatType": level_format}]},
    }
    if controllable:
        out["controlService"] = {"listOfSupportedControlStyles": [{
            "controlServiceStyleType": 2, "controlServiceStyleName": "Cell Configuration and Control",
            "controlServiceHeaderFormatType": 1, "controlServiceMessageFormatType": 2,
            "controlServiceControlOutcomeFormatType": 2}]}
    return out


NAMES = {
    "O-GNBDUFunction": ["gNBDUId", "gNBDUName", "gNBId", "gNBIdLength"],
    "O-NRCellDU": ["cellLocalId", "operationalState", "administrativeState", "pLMNInfoList", "nRPCI", "nRTAC",
                   "arfcnDL", "arfcnUL", "bSChannelBwDL", "ssbFrequency", "ssbPeriodicity", "ssbSubCarrierSpacing",
                   "ssbOffset", "bSChannelBwUL", "bWPList"],
    "O-BWP": ["bwpContext", "isInitialBwp", "subCarrierSpacing", "startRB", "numberOfRBs"],
    "O-RRMPolicyRatio": ["resourceType", "rRMPolicyMemberList", "rRMPolicyMaxRatio", "rRMPolicyMinRatio",
                         "rRMPolicyDedicatedRatio"],
}
KEYS = {name: [{"pLMNInfoList": "plmnInfoList", "nRPCI": "nrPci", "nRTAC": "nrTac", "bWPList": "bwpList",
                "gNBDUId": "gnbDuId", "gNBDUName": "gnbDuName", "gNBId": "gnbId", "gNBIdLength": "gnbIdLength"}
               .get(a, a) for a in attributes] for name, attributes in NAMES.items()}


def _supported(name: str, level_format: int) -> dict:
    return {"ranConfigurationStructureName": name, "listOfSupportedAttributes": [
        {"attributeName": a, "supportedServices": _services(level_format, name == "O-RRMPolicyRatio")}
        for a in NAMES[name]]}


def ran_function_definition(cells=(TEST_CELL,)) -> dict:
    """The RAN Function Definition of e2sm_ccc_asn1_packer::pack_ran_function_description."""
    return {
        "ranFunctionName": {"ranFunctionShortName": "ORAN-E2SM-CCC",
                            "ranFunctionServiceModelOID": "1.3.6.1.4.1.53148.1.6.2.4",
                            "ranFunctionDescription": "Cell Configuration and Control", "ranFunctionInstance": 0},
        "listOfSupportedNodeLevelConfigurationStructures": [_supported("O-GNBDUFunction", 1)],
        "listOfCellsForRANFunctionDefinition": [
            {"cellGlobalID": cgi, "listOfSupportedCellLevelRANConfigurationStructures": [
                _supported(s, 2) for s in ("O-NRCellDU", "O-BWP", "O-RRMPolicyRatio")]} for cgi in cells],
    }


def e2mgr_info(definition: Optional[dict] = None) -> dict:
    definition = ran_function_definition() if definition is None else definition
    return {
        "ranName": "gnbd_001_001_00019b_0",
        "connectionStatus": "CONNECTED",
        "gnb": {"ranFunctions": [
            {"ranFunctionId": 2, "ranFunctionOid": "1.3.6.1.4.1.53148.1.2.2.2", "ranFunctionDefinition": "00"},
            {"ranFunctionId": 4, "ranFunctionOid": "1.3.6.1.4.1.53148.1.6.2.4",
             "ranFunctionDefinition": json.dumps(definition).encode().hex().upper()}]},
    }
