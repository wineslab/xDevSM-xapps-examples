import argparse
import signal
import time

import setup_imports

# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import kpm functionalities
from xDevSM.decorators.kpm.kpm_frame import XappKpmFrame

from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e


def indication_callback(ind_hdr, ind_msg, meid):
    print("Received indication message")

def sub_failed_callback(json_data):
    print("[Main]subscription failed: {}".format(json_data))

def main(args):

    # Creating a generic xDevSM RMR xApp
    xapp_gen = xDevSMRMRXapp("0.0.0.0")

    # Adding kpm functionalities to the xapp
    kpm_xapp = XappKpmFrame(xapp_gen, 
                            xapp_gen.logger, 
                            xapp_gen.server, 
                            xapp_gen.get_xapp_name(), 
                            xapp_gen.rmr_port, 
                            xapp_gen.http_port,xapp_gen.get_pltnamespace(), 
                            xapp_gen.get_app_namespace())

    # Registering the outermost rmr handler
    xapp_gen.register_handler(kpm_xapp.handle) 

    # Registering indication message callback
    # kpm_xapp.register_ind_msg_callback(handler=indication_callback)

    # Registering termination signal handlers
    signal.signal(signal.SIGINT, kpm_xapp.terminate)
    signal.signal(signal.SIGTERM, kpm_xapp.terminate)

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if gnb is None:
        xapp_gen.logger.error("No gNB selected. Exiting...")
        kpm_xapp.terminate(signal.SIGTERM, None)
        return

    # There exist one gnb available
    ran_function_description = kpm_xapp.get_ran_function_description(json_ran_info=gnb_info)
    func_def_dict = ran_function_description.get_dict_of_values()
        
    xapp_gen.logger.debug("Available functions: {}".format(func_def_dict))

    if len(func_def_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION]) == 0:
        xapp_gen.logger.error("Format 4 not supported. Exiting...")
        kpm_xapp.terminate(signal.SIGTERM, None)
        return
    
    func_def_sub_dict = {}
    # Selecting only supported action definition
    func_def_sub_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION] = func_def_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION]
    
    # Waiting for xApp registration (no callback available)
    time.sleep(15)

    # Sending subscription
    ev_trigger_tuple = (0, args.event_trigger)
    kpm_xapp.subscribe(gnb=gnb, ev_trigger=ev_trigger_tuple, func_def=func_def_sub_dict,  ran_period_ms=1000, sst=args.sst, sd=args.sd)

    # Start running after finishing subscription requests
    xapp_gen.logger.info("Starting xapp")
    xapp_gen.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="open6g KPM xApp")


    parser.add_argument("-s", "--sst", metavar="<sst>",
                        help="SST", type=int, default=1)
    
    parser.add_argument("-d", "--sd", metavar="<sd>",
                        help="SD", type=int, default=1)
    
    parser.add_argument("-e", "--event_trigger", metavar="<event_trigger>",
                        help="Event trigger in ms", type=int, default=1000)
    
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)
    
    args = parser.parse_args()

    main(args)