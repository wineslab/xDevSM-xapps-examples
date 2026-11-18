import argparse
import os
import signal
import traceback

from xdevsm.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp
from xdevsm.decorators.ccc.ccc_frame import XappCccFrame
from xdevsm.sm_framework.py_oran.ccc.ccc_decoder import find_ccc_function_id
from xdevsm.sm_framework.py_oran.ccc.ccc_encoder import nr_cell_id_of
from xdevsm.sm_framework.py_oran.ccc.constants import STRUCT_O_NRCELLDU

# E2SM-CCC Section 9.2.1.1.3 minimum period of Event Trigger Definition Format 3.
MIN_REPORT_PERIOD_MS = 10

logger = None


def indication_callback(hdr, msg, meid, sub_id=None):
    gnb_id = meid.decode("utf-8")
    logger.info("[Main] {} report from {} at {}".format(hdr.indication_reason, gnb_id, hdr.event_time))
    for cell, s in msg.iter_structures():
        logger.info("[Main] cell={} struct={} change={} values={}".format(
            nr_cell_id_of(cell.get("cellGlobalId")), s.get("ranConfigurationStructureName"),
            s.get("changeType"), (s.get("valuesOfAttributes") or {}).get("ranConfigurationStructure")))


def sub_failed_callback(json_data):
    logger.error("[Main] subscription failed: {}".format(json_data))
    # The REST thread must reply to submgr at once, so the SIGTERM handler stops the xApp.
    os.kill(os.getpid(), signal.SIGTERM)


def main(args):
    global logger

    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    logger = xapp_gen.logger

    ccc_xapp = XappCccFrame(xapp_gen,
                            logger,
                            xapp_gen.server,
                            xapp_gen.get_xapp_name(),
                            xapp_gen.rmr_port,
                            xapp_gen.http_port,
                            xapp_gen.get_pltnamespace(),
                            xapp_gen.get_app_namespace())

    xapp_gen.register_handler(ccc_xapp.handle)
    ccc_xapp.register_ind_msg_callback(handler=indication_callback)
    ccc_xapp.register_sub_fail_callback(handler=sub_failed_callback)

    signal.signal(signal.SIGINT, ccc_xapp.terminate)
    signal.signal(signal.SIGTERM, ccc_xapp.terminate)

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if not gnb:
        logger.info("[Main] Terminating xapp")
        ccc_xapp.terminate(signal.SIGTERM, None)
        return

    # The E2 node assigns the RAN function ID at E2 Setup.
    try:
        ccc_xapp.function_id = find_ccc_function_id(gnb_info)
    except LookupError as e:
        logger.error("[Main] {}".format(e))
        ccc_xapp.terminate(signal.SIGTERM, None)
        return

    xapp_gen.wait_until_ready_for_subscriptions()
    try:
        sub_id = ccc_xapp.subscribe(gnb=gnb, ran_period_ms=args.period_ms,
                                    ran_cfg_structure_name=STRUCT_O_NRCELLDU, attributes=args.attributes)
    except Exception:
        logger.error("[Main] Subscription request raised: {}".format(traceback.format_exc()))
        sub_id = None
    if sub_id is None:
        logger.error("[Main] Subscription request failed")
        ccc_xapp.terminate(signal.SIGTERM, None)
        return
    logger.info("[Main] Subscribed {} attributes={} -> sub_id={}".format(STRUCT_O_NRCELLDU, args.attributes, sub_id))

    logger.info("[Main] Starting xapp")
    xapp_gen.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="CCC REPORT Style 2 xApp")

    parser.add_argument("-p", "--period-ms", dest="period_ms", metavar="<ms>", type=int, default=1000,
                        help="report period, at least {} ms".format(MIN_REPORT_PERIOD_MS))

    parser.add_argument("-a", "--attributes", metavar="<attr1,attr2,...>", type=str, default=None,
                        help="comma-separated O-NRCellDU attributes to report "
                             "(default: arfcnDL,bSChannelBwDL,bWPList)")

    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")

    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)

    args = parser.parse_args()
    if args.period_ms < MIN_REPORT_PERIOD_MS:
        parser.error("--period-ms must be at least {}".format(MIN_REPORT_PERIOD_MS))
    if args.attributes is not None:
        args.attributes = [a.strip() for a in args.attributes.split(",") if a.strip()]
        if not args.attributes:
            parser.error("--attributes must name at least one attribute")

    main(args)
