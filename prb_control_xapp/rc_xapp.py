import time
import argparse
import signal

import setup_imports


# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import RC Radio Resource Allocation Control Decorator
from xDevSM.decorators.rc.rc_radio_resource_alloc_control import RadioResourceAllocationControl


logger = None


def main(args):
    global logger

    xapp_gen = xDevSMRMRXapp("0.0.0.0")
    logger = xapp_gen.logger

    rc_xapp = RadioResourceAllocationControl(xapp_gen,
                                            logger=logger,
                                            server=xapp_gen.server,
                                            xapp_name=xapp_gen.get_xapp_name(),
                                            rmr_port=xapp_gen.rmr_port,
                                            mrc=xapp_gen._mrc,
                                            http_port=xapp_gen.http_port,
                                            pltnamespace=xapp_gen.get_pltnamespace(),
                                            app_namespace=xapp_gen.get_app_namespace(),
                                            # control parameters
                                            plmn_identity=args.plmn,
                                            sst=args.sst,
                                            sd=args.sd,
                                            min_prb_policy_ratio=args.min_prb_policy_ratio,
                                            max_prb_policy_ratio=args.max_prb_policy_ratio,
                                            dedicated_prb_policy_ratio=args.dedicated_prb_policy_ratio
                                            )

    # Register the handler for the xApp
    xapp_gen.register_handler(rc_xapp.handle)

    # Registering termination signal handlers
    signal.signal(signal.SIGINT, rc_xapp.terminate)
    signal.signal(signal.SIGTERM, rc_xapp.terminate)

    # Start the xApp
    xapp_gen.run(thread=True)
    time.sleep(10)  # waiting for registrations

    gnb_list = xapp_gen.get_list_gnb_ids()
    if len(gnb_list) == 0:
        logger.error("[Main] no gnb available")
        return
    
    # We send control only to the first gNB 
    # (usually this should be selected based on the inventory_name)
    gnb_to_use = None
    for index, gnb in enumerate(gnb_list):
        json_obj = xapp_gen.get_ran_info(e2node=gnb)
        if json_obj["connectionStatus"] == "CONNECTED":
            gnb_to_use = gnb
            break
    # gnb_to_use = gnb_list[0]
    if gnb_to_use is None:
        xapp_gen.logger.error("[Main] No gNB connected")
        return

    xapp_gen.logger.info("[Main] gnb selected: {}".format(gnb_to_use.inventory_name))
    
    # Printing ran function description
    gnb_info = xapp_gen.get_ran_info(gnb_to_use)

    ran_function_description = rc_xapp.get_ran_function_description(json_ran_info=gnb_info)
    ran_function_description.print_rc_functions()

    rc_xapp.send(e2_node_id=gnb.inventory_name,
                ran_func_dsc=ran_function_description,
                ue_id=None,  # Use mock UE ID
                control_action_id=6) # Slice-level PRB quota


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm xApp")

    parser.add_argument("-p", "--plmn", metavar="<plmn>",
                        help="PLMN ID", type=str, default="00F110")
    parser.add_argument("-s", "--sst", metavar="<sst>",
                        help="SST", type=int, default=1)
    parser.add_argument("-d", "--sd", metavar="<sd>",
                        help="SD", type=int, default=1)
    parser.add_argument("-r", "--min_prb_policy_ratio", metavar="<min_prb_policy_ratio>",
                        help="Minimum PRB Policy Ratio", type=int, default=20)
    parser.add_argument("-x", "--max_prb_policy_ratio", metavar="<max_prb_policy_ratio>",
                        help="Maximum PRB Policy Ratio", type=int, default=80)
    parser.add_argument("-y", "--dedicated_prb_policy_ratio", metavar="<dedicated_prb_policy_ratio>",
                        help="Dedicated PRB Policy Ratio", type=int, default=5)
    
    args = parser.parse_args()
    main(args)