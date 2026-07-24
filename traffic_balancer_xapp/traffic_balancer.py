"""traffic_balancer xApp — combined KPM + RC with a swappable policy layer.

v1 skeleton: ships only the `g6` static policy (the sweep oracle). The
decision loop closes the KPM -> policy -> RC ACK -> CSV log cycle in
the same process, no GUI yet (that's the next pass).

Wiring follows the framework conventions described in CLAUDE.md:
  setup_imports             # path bootstrap — must come BEFORE xDevSM imports
  xDevSMRMRXapp             # the spine: RMR ports, HTTP server, E2 link
  RadioResourceAllocationControl   # RC service-model decorator wrapping xapp_gen
  XappKpmFrame              # KPM service-model decorator wrapping the RC one
  KpmIngest                 # subscribes both slices, decodes IND -> SampleBuffer
  BalancerController        # background thread: snapshot -> policy.act() -> RC send
"""

import argparse
import os
import signal
import sys
import time


from mdclogpy import Level

from xdevsm.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp
from xdevsm.decorators.kpm.kpm_frame import XappKpmFrame
from xdevsm.decorators.rc.rc_radio_resource_alloc_control import (
    RadioResourceAllocationControl,
)

from balancer.controller import BalancerController, RcSender
from balancer.kpm_ingest import KpmIngest
from balancer.policies import available_policies, get_policy
from balancer.state import SampleBuffer


_LOG_LEVELS = {
    "DEBUG": Level.DEBUG,
    "INFO": Level.INFO,
    "WARNING": Level.WARNING,
    "ERROR": Level.ERROR,
}


def parse_args():
    p = argparse.ArgumentParser(description="traffic_balancer xApp (KPM + RC + policy loop)")
    p.add_argument("-g", "--gnb_target", required=True, metavar="<gnb_id>",
                   help="E2 node id of the gNB to subscribe to and control")
    p.add_argument("--initial_policy", default="g6", choices=available_policies(),
                   help="Policy to start with. v1 ships only 'g6'.")
    p.add_argument("-r", "--route_file", default="./config/uta_rtg.rt", metavar="<path>",
                   help="Static RMR route table. Default ./config/uta_rtg.rt")
    p.add_argument("--csv_dir", default="/ws/experiments/traffic_balancer", metavar="<dir>",
                   help="Directory to write per-run decision CSV into.")
    p.add_argument("--ack_timeout", type=float, default=1.0, metavar="<s>",
                   help="Seconds to wait for an RC ACK before resending. Default 1.0.")
    p.add_argument("--decision_period_s", type=float, default=5.0, metavar="<s>",
                   help="Seconds between policy decisions. Default 5.0 — "
                        "holds each action long enough for the gNB to settle "
                        "between transitions and lets the controller average "
                        "out per-second KPM jitter. Lower this only for "
                        "smoke-tests of static policies.")
    p.add_argument("--boot_delay_s", type=float, default=10.0, metavar="<s>",
                   help="Seconds to wait before querying the E2 manager. Default 10.")
    p.add_argument("--log_level", default="INFO", choices=sorted(_LOG_LEVELS),
                   help="Log level. Default INFO.")
    return p.parse_args()


def main():
    args = parse_args()

    # ---- Framework spine ----------------------------------------------------
    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    logger = xapp_gen.logger
    logger.set_level(_LOG_LEVELS[args.log_level])
    logger.info("[Main] traffic_balancer starting; policy={} gnb_target={}".format(
        args.initial_policy, args.gnb_target))

    # ---- RC service-model wrapper (initial slice = NLOS) -------------------
    # Initial sst/sd are placeholders — the controller will set the right slice
    # before each send via rc_func.set_sd(...).
    rc_func = RadioResourceAllocationControl(
        xapp_gen,
        logger=logger,
        server=xapp_gen.server,
        xapp_name=xapp_gen.get_xapp_name(),
        rmr_port=xapp_gen.rmr_port,
        http_port=xapp_gen.http_port,
        mrc=xapp_gen._mrc,
        pltnamespace=xapp_gen.get_pltnamespace(),
        app_namespace=xapp_gen.get_app_namespace(),
        sst=1,
        sd=1,
    )
    rc_func.set_max_prb_policy_ratio(100)
    rc_func.set_min_prb_policy_ratio(10)
    rc_func.set_dedicated_prb_policy_ratio(0)

    # ---- KPM service-model wrapper ----------------------------------------
    kpm_func = XappKpmFrame(
        rc_func,
        logger,
        xapp_gen.server,
        xapp_gen.get_xapp_name(),
        xapp_gen.rmr_port,
        xapp_gen.http_port,
        xapp_gen.get_pltnamespace(),
        xapp_gen.get_app_namespace(),
    )

    # ---- App-level pieces -------------------------------------------------
    buffer = SampleBuffer(maxlen=600)
    ingest = KpmIngest(kpm_func, buffer, logger)

    xapp_gen.register_handler(kpm_func.handle)
    kpm_func.register_ind_msg_callback(ingest.indication_callback)
    kpm_func.register_sub_fail_callback(ingest.sub_failed_callback)
    # Bridge the submgr SubscriptionId (returned by subscribe()) to the
    # E2EventInstanceId stamped on every IND, so the indication callback
    # can route by sub_id → sd. Without this, no IND is taggable.
    kpm_func.register_sub_resolved_callback(ingest.on_sub_resolved)

    # ---- E2 registration + gNB discovery ----------------------------------
    logger.info("[Main] waiting {}s for E2 registration".format(args.boot_delay_s))
    time.sleep(args.boot_delay_s)

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if not gnb:
        logger.error("[Main] gNB '{}' not found; terminating".format(args.gnb_target))
        kpm_func.terminate(signal.SIGTERM, None)
        return 1

    plmn_id = gnb_info["globalNbId"]["plmnId"]
    rc_func.set_plmn_identity(plmn_id)
    logger.info("[Main] selected gNB: {} (plmn={})".format(gnb.inventory_name, plmn_id))

    rc_func_dsc = rc_func.get_ran_function_description(json_ran_info=gnb_info)
    rc_func_dsc.print_rc_functions()

    # ---- Subscribe both slices --------------------------------------------
    if not ingest.subscribe_all(gnb, gnb_info, ran_period_ms=1000):
        logger.error("[Main] KPM subscription bring-up failed; terminating")
        kpm_func.terminate(signal.SIGTERM, None)
        return 2

    # ---- Decision loop ----------------------------------------------------
    sender = RcSender(
        rc_func=rc_func,
        gnb=gnb,
        ran_func_dsc=rc_func_dsc,
        logger=logger,
        ack_timeout=args.ack_timeout,
        max_retries=None,  # match rc_xapp.py: retry forever, operator SIGINT-able
    )

    policy = get_policy(args.initial_policy)
    # LinUCB exposes a `set_logger` hook so it can announce its warmup
    # progress + the warmup→UCB transition. Other policies don't have it.
    setter = getattr(policy, "set_logger", None)
    if callable(setter):
        setter(logger)
    logger.info("[Main] initial policy: {}".format(policy.name))

    csv_path = os.path.join(args.csv_dir, "run_{}.csv".format(int(time.time())))
    controller = BalancerController(
        buffer=buffer,
        policy=policy,
        sender=sender,
        logger=logger,
        decision_period_s=args.decision_period_s,
        csv_path=csv_path,
    )

    # ---- Signal handling --------------------------------------------------
    def _shutdown(signum, frame):
        logger.info("[Main] shutdown signal {}".format(signum))
        try:
            controller.stop()
        except Exception as exc:
            logger.warning("[Main] controller.stop() error: {}".format(exc))
        kpm_func.terminate(signum, frame)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    controller.start()

    logger.info("[Main] entering RMR event loop")
    xapp_gen.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
