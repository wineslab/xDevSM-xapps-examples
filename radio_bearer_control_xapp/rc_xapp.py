import time
import argparse
import signal

import setup_imports


# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import RC Radio Bearer Control Decorator
from xDevSM.decorators.rc.rc_radio_bearer_control import RadioBearerControl

logger = None

def main(args):
    global logger

    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    logger = xapp_gen.logger

    rc_xapp = RadioBearerControl(xapp_gen,
                                 logger=logger,
                                 server=xapp_gen.server,
                                 xapp_name=xapp_gen.get_xapp_name(),
                                 rmr_port=xapp_gen.rmr_port,
                                 mrc=xapp_gen._mrc,
                                 http_port=xapp_gen.http_port,
                                 pltnamespace=xapp_gen.get_pltnamespace(),
                                 app_namespace=xapp_gen.get_app_namespace(),
                                 # control parameters
                                 drb_id=args.drb_id,
                                 qos_flow_id=args.qos_flow_id,
                                 qos_flow_mapping_indication=args.qos_flow_mapping_indication
                                 )

    # Register the handler for the xApp
    xapp_gen.register_handler(rc_xapp.handle)

    # Registering termination signal handlers
    signal.signal(signal.SIGINT, rc_xapp.terminate)
    signal.signal(signal.SIGTERM, rc_xapp.terminate)

    # Start the xApp
    xapp_gen.run(thread=True)
    time.sleep(10)  # waiting for registrations

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if not gnb:
        xapp_gen.info("[Main] Terminating xapp")
        rc_xapp.terminate(signal.SIGTERM, None)
        return

    ran_function_description = rc_xapp.get_ran_function_description(json_ran_info=gnb_info)
    ran_function_description.print_rc_functions()

    rc_xapp.send(e2_node_id=gnb.inventory_name,
                ran_func_dsc=ran_function_description,
                ue_id=None,  # Use mock UE ID
                control_action_id=2)  # QoS flow mapping configuration


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm xApp")

    parser.add_argument("-d", "--drb_id", metavar="<drb_id>",
                        help="DRB ID", type=int, default=1)
    parser.add_argument("-q", "--qos_flow_id", metavar="<qos_flow_id>",
                        help="QoS Flow ID", type=int, default=10)
    parser.add_argument("-m", "--qos_flow_mapping_indication", metavar="<qos_flow_mapping_indication>",
                        help="QoS Flow Mapping Indication", type=int, default=1)
    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)
    
    args = parser.parse_args()
    main(args)