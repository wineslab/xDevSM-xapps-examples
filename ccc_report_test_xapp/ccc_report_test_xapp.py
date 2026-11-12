"""E2SM-CCC REPORT end-to-end test xApp for OCUDU.

It subscribes to every REPORT combination that the OCUDU E2 agent supports, changes the rRMPolicyMaxRatio of
one slice with an O-RRMPolicyRatio CONTROL, restores it, and logs one PASS or FAIL line per check. The exit code
is 0 if every check passes and 1 otherwise.
"""

import logging
import os
import signal
import sys
from typing import Optional

from mdclogpy import Level
from ricxappframe.xapp_frame import rmr
from xdevsm.decorators.ccc.ccc_frame import XappCccFrame
from xdevsm.decorators.ccc.ccc_rrm_policy_control import CccRrmPolicyRatioControl
from xdevsm.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp
from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import (
    CCCByteArray,
    RrmPolicySlice,
    encode_action_def_per_cell,
    encode_event_trigger_periodic,
    nr_cell_id_of,
)
from xdevsm.utils.constants import Values

from ccc_test import config
from ccc_test.journal import AckKind, Journal, make_indication
from ccc_test.plan import Level as ReportLevel
from ccc_test.plan import Spec, Trigger
from ccc_test.scenario import Scenario

logger = logging.getLogger("ccc_report_test")

NODE_POLL_S = 2.0
MDC_LEVELS = {"DEBUG": Level.DEBUG, "INFO": Level.INFO, "WARNING": Level.WARNING, "ERROR": Level.ERROR}
CONFIG_FILE_ENV = "CONFIG_FILE"
# Placeholders until the scenario has chosen the cell: CccRrmPolicyRatioControl takes them at construction.
UNSET_PLMN = ("001", "01")
UNSET_NCI = 0


class XdevsmPort:
    """The scenario's view of the RIC, through xDevSM."""

    def __init__(self, xapp: xDevSMRMRXapp, frame: XappCccFrame, control: CccRrmPolicyRatioControl,
                 journal: Journal, cfg: config.RunConfig):
        self.xapp = xapp
        self.frame = frame
        self.control = control
        self.journal = journal
        self.cfg = cfg
        self.gnb = None

    def wait_for_node(self, deadline_s: float) -> Optional[dict]:
        next_poll_s = self.journal.clock()
        while not self.journal.aborted:
            try:
                gnb, info = self.xapp.get_selected_e2node_info(self.cfg.gnb_target)
            except Exception as e:
                logger.warning("e2mgr query failed: %s", e)
                gnb, info = None, None
            if gnb is not None:
                self.gnb = gnb
                self.xapp.wait_until_ready_for_subscriptions()
                return info
            next_poll_s += NODE_POLL_S
            if next_poll_s >= deadline_s:
                return None
            self.journal.wait_until(lambda: False, next_poll_s)
        return None

    def set_function_id(self, function_id: int) -> None:
        self.frame.function_id = function_id
        self.control.function_id = function_id

    def subscribe(self, spec: Spec) -> Optional[str]:
        attributes = list(spec.attributes) or None
        trigger_attributes = list(spec.trigger_attributes) or None
        cells = list(spec.cells) or None
        try:
            if spec.encoded is not None:
                return self.frame.subscribe_encoded(self.gnb, CCCByteArray(spec.encoded[0]),
                                                    CCCByteArray(spec.encoded[1]))
            if spec.level is ReportLevel.NODE and spec.trigger is Trigger.NODE_CHANGE:
                return self.frame.subscribe_node_upon_change(self.gnb, trigger_attributes, attributes,
                                                             spec.report_type, spec.structure)
            if spec.level is ReportLevel.NODE:
                return self.frame.subscribe_node_periodic(self.gnb, self.cfg.period_ms, attributes,
                                                          spec.report_type, spec.structure)
            if spec.trigger is Trigger.CELL_CHANGE:
                return self.frame.subscribe_upon_change(self.gnb, trigger_attributes, attributes, cells,
                                                        spec.report_type, spec.structure)
            if cells:
                return self.frame.subscribe_encoded(
                    self.gnb, encode_event_trigger_periodic(self.cfg.period_ms),
                    encode_action_def_per_cell(spec.structure, attributes, cells, spec.report_type))
            return self.frame.subscribe(self.gnb, self.cfg.period_ms, spec.structure, attributes or [],
                                        spec.report_type)
        except Exception:
            logger.exception("subscription %s not sent", spec.key)
            return None

    def send_control(self, cell: dict, member: dict, min_ratio: int, max_ratio: int) -> None:
        if self.gnb is None:
            raise RuntimeError("no E2 node to control")
        plmn = cell["plmnIdentity"]
        snssai = member["snssai"]
        self.control.mcc, self.control.mnc = plmn["mcc"], plmn["mnc"]
        self.control.nci = nr_cell_id_of(cell)
        policy = RrmPolicySlice(sst=snssai["sst"], sd=snssai.get("sd"), min_ratio=min_ratio, max_ratio=max_ratio)
        self.control.send_policies(self.gnb.inventory_name, [policy], resource_type=self.cfg.resource_type)

    def unsubscribe_all(self) -> None:
        self.frame.unsubscribe_all()


def _rejection_cause(response: dict) -> str:
    instances = response.get("SubscriptionInstances") or [{}]
    return "{} ({})".format(instances[0].get("ErrorCause"), instances[0].get("ErrorSource"))


def _wire(xapp: xDevSMRMRXapp, journal: Journal):
    common = dict(logger=xapp.logger, server=xapp.server, xapp_name=xapp.get_xapp_name(), rmr_port=xapp.rmr_port,
                  http_port=xapp.http_port, pltnamespace=xapp.get_pltnamespace(),
                  app_namespace=xapp.get_app_namespace())
    control = CccRrmPolicyRatioControl(xapp, mrc=xapp._mrc, mcc=UNSET_PLMN[0], mnc=UNSET_PLMN[1], nci=UNSET_NCI,
                                       function_id=-1, **common)
    frame = XappCccFrame(control, **common)

    def on_indication(hdr, msg, meid, sub_id):
        journal.on_indication(sub_id, make_indication(hdr, msg, journal.clock()))

    def on_rmr(rmr_xapp, summary, sbuf):
        # The acknowledges are recorded here, so that the control service decodes no E2SM-DAPP outcome.
        mtype = summary[rmr.RMR_MS_MSG_TYPE]
        if mtype == Values.RIC_CONTROL_ACK:
            journal.on_control_ack(AckKind.ACK)
        elif mtype == Values.RIC_CONTROL_FAILURE:
            journal.on_control_ack(AckKind.FAILURE)
        frame.handle(rmr_xapp, summary, sbuf)

    frame.register_ind_msg_callback(on_indication)
    frame.register_sub_resolved_callback(lambda sub_id, instance_id, gnb: journal.on_resolved(sub_id, instance_id))
    frame.register_sub_fail_callback(lambda response: journal.on_rejected(response.get("SubscriptionId"),
                                                                          _rejection_cause(response)))
    xapp.register_handler(on_rmr)
    return frame, control


def main(argv=None) -> int:
    logging.basicConfig(stream=sys.stdout, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        level=logging.INFO)
    try:
        cfg, args, descriptor = config.load(argv, os.environ.get(CONFIG_FILE_ENV))
    except (OSError, ValueError) as e:
        logger.error("configuration: %s", e)
        return 2
    logging.getLogger().setLevel(cfg.log_level)
    if descriptor:
        os.environ[CONFIG_FILE_ENV] = descriptor

    journal = Journal()
    xapp = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    xapp.logger.set_level(MDC_LEVELS[cfg.log_level])
    frame, control = _wire(xapp, journal)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: journal.abort())
    xapp.run(thread=True)

    report = Scenario(XdevsmPort(xapp, frame, control, journal, cfg), journal, cfg).run()
    print(report.summary(), flush=True)
    frame.terminate(signal.SIGTERM, None)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
