"""The subscriptions that XdevsmPort sends through the xDevSM frame helpers. Needs ricxappframe and RMR (Linux)."""

import json
import logging
from typing import Any

import pytest

import ocudu_json as oj
from ccc_test.config import RunConfig
from ccc_test.journal import Journal
from ccc_test.plan import build_plan

try:
    import ccc_report_test_xapp as xapp_module
except Exception as e:  # ricxappframe loads RMR and inotify, which exist on Linux only
    pytest.skip("ccc_report_test_xapp does not import: {}".format(e), allow_module_level=True)


class _Subscriber:
    def ActionToBeSetup(self, **kw):
        return kw

    def SubsequentAction(self, **kw):
        return kw


def _port(sent):
    from xdevsm.decorators.ccc.ccc_frame import XappCccFrame

    frame: Any = object.__new__(XappCccFrame)
    frame.logger = logging.getLogger("test")
    frame.subscriber = _Subscriber()

    def send_subscription(gnb, ev_trig, actions):
        sent.append((json.loads(ev_trig.to_bytes()), json.loads(bytes(actions[0]["action_definition"]))))
        return 201, "sub-{}".format(len(sent))

    frame.send_subscription = send_subscription
    unused: Any = None
    port = xapp_module.XdevsmPort(unused, frame, unused, Journal(), RunConfig(period_ms=1000))
    port.gnb = object()
    return port


def test_port_sends_the_ocudu_json_of_each_combination():
    sent = []
    port = _port(sent)
    plan = {s.key: s for s in build_plan(oj.TEST_CELL)}
    expected = {
        "S1-F1-O-GNBDUFunction-all": (oj.NODE_TRIGGER, oj.NODE_ACTION),
        "S2-F2-O-RRMPolicyRatio-all": (oj.CELL_TRIGGER, oj.CELL_ACTION),
        "S2-F3-O-RRMPolicyRatio-all": (oj.PERIODIC_TRIGGER, oj.CELL_ACTION),
    }
    for key, (trigger, action) in expected.items():
        assert port.subscribe(plan[key]) is not None
        assert sent[-1] == (json.loads(trigger), json.loads(action)), key


def test_port_sends_every_spec_of_the_plan():
    sent = []
    port = _port(sent)
    plan = build_plan(oj.TEST_CELL)
    assert all(port.subscribe(spec) for spec in plan)
    assert len(sent) == len(plan)
    node_periodic = dict(zip((s.key for s in plan), sent))["S1-F3-O-GNBDUFunction-change"]
    assert node_periodic[0] == {"eventTriggerDefinitionFormat": {"period": 1000}}
    assert node_periodic[1]["ricStyleType"] == 1
    attribute_trigger = dict(zip((s.key for s in plan), sent))["reject-F2-unknown-attribute"][0]
    entry = attribute_trigger["eventTriggerDefinitionFormat"]["listOfCellLevelConfigurationStructuresForEventTrigger"]
    assert entry[0]["listOfRANConfigurationStructuresForEventTrigger"][0]["listOfAttributes"] == ["arfcnDL"]
