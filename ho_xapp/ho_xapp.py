import time
import argparse
import signal
import numpy as np
import setup_imports

from mdclogpy import Level

# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import RC Radio Resource Allocation Control Decorator
from xDevSM.decorators.rc.rc_connected_mode_mobility import ConnectedModeMobilityControl
from xDevSM.decorators.kpm.kpm_frame import XappKpmFrame

# kpm related formats
from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e
from xDevSM.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xDevSM.sm_framework.py_oran.kpm.enums import meas_type_enum
from xDevSM.sm_framework.py_oran.kpm.enums import meas_value_e


string_to_level = {
                "DEBUG": Level.DEBUG,
                "INFO": Level.INFO,
                "WARNING": Level.WARNING,
                "ERROR": Level.ERROR}

class xAppMonControlContainer():
    def __init__(self, xapp_gen: xDevSMRMRXapp, gnb_target: str, event_trigger, sst: int, sd: int,plmn_identity: str, nr_cell_id: str):
        self.xapp_gen = xapp_gen
        self.gnb_target = gnb_target
        self.event_trigger = event_trigger*1000
        self.sst = sst
        self.sd = sd
        self.dest_plmn_identity = plmn_identity
        self.dest_nr_cell_id = nr_cell_id

        self.counter_indications = 0
        
        # Adding RC - HO functionality
        self.rc_func = ConnectedModeMobilityControl(self.xapp_gen,
                                            logger=self.xapp_gen.logger,
                                            server=self.xapp_gen.server,
                                            xapp_name=self.xapp_gen.get_xapp_name(),
                                            rmr_port=self.xapp_gen.rmr_port,
                                            mrc=self.xapp_gen._mrc,
                                            http_port=self.xapp_gen.http_port,
                                            pltnamespace=self.xapp_gen.get_pltnamespace(),
                                            app_namespace=self.xapp_gen.get_app_namespace(),
                                            # control parameters
                                            plmn_identity=plmn_identity,
                                            nr_cell_id=nr_cell_id
                                            )
        # Adding KPM functionality
        self.kpm_func = XappKpmFrame(self.rc_func, 
                                     self.xapp_gen.logger, 
                                     self.xapp_gen.server, 
                                     self.xapp_gen.get_xapp_name(), 
                                     self.xapp_gen.rmr_port, 
                                     self.xapp_gen.http_port, 
                                     self.xapp_gen.get_pltnamespace(), 
                                     self.xapp_gen.get_app_namespace())
        
        self.xapp_gen.register_handler(self.kpm_func.handle)

        self.kpm_func.register_ind_msg_callback(self.ind_msg_handler)
        self.kpm_func.register_sub_fail_callback(self.sub_failed_callback)


        signal.signal(signal.SIGINT, self.kpm_func.terminate)
        signal.signal(signal.SIGTERM, self.kpm_func.terminate)


    def ind_msg_handler(self, ind_hdr, ind_msg, meid):
        """
        Handle the indication message received from the xApp
        """
        gnbid = meid.decode('utf-8')
        self.xapp_gen.logger.info("[xAppMonControlContainer] Received indication message from {}".format(gnbid))
        sender_name = None
        if ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name:
            my_string = bytes(np.ctypeslib.as_array(ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.buf, shape = (ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.len,)))
            sender_name = my_string.decode('utf-8') 
        
        if sender_name is None:
            self.xapp_gen.logger.info("[xAppMonControlContainer]Sender name not specified in the indication message")

        self.counter_indications += 1
        self.xapp_gen.logger.info("[xAppMonControlContainer] Indication message count: {}".format(self.counter_indications))
        ue_id = None
        meas_report_ue = None
        if ind_msg.type.value == format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
            # for each ue
            meas_report_ue = ind_msg.data.frm_3.meas_report_per_ue[0] # Take the first ue only
            # ue id
            ue_id = self.kpm_func.get_ue_id(meas_report_ue.ue_meas_report_lst)

        self.xapp_gen.logger.info("[xAppMonControlContainer]gnb: {}, sender_name: {}, ue: {}".format(gnbid, sender_name, ue_id))

        if self.counter_indications == 10:
            self.xapp_gen.logger.info("[xAppMonControlContainer] Sending HO Control Action to gNB {} --> target is plmn: {}, nr_cell_id: {}".format(gnbid, self.dest_plmn_identity, self.dest_nr_cell_id))
            # Sending control request
            self.rc_func.set_nr_cell_id(self.dest_nr_cell_id)
            self.rc_func.set_plmn_identity(self.dest_plmn_identity)
            self.rc_func.send(e2_node_id=self.selected_gnb.inventory_name,
                            ran_func_dsc=self.rc_func_desc,
                            ue_id_struct=meas_report_ue.ue_meas_report_lst,  
                            control_action_id=1)
            self.kpm_func.terminate(signal.SIGTERM, None)

    def sub_failed_callback(self, json_data):
        self.xapp_gen.logger.info("[xAppMonControlContainer] subscription failed: {}".format(json_data))

    def start(self):
        time.sleep(5)  # we need to wait the registration of RMR rule -> no callback defined in the osc framework

        # Obtain gnb info
        self.selected_gnb, gnb_info = self.xapp_gen.get_selected_e2node_info(self.gnb_target)
        if not self.selected_gnb:
            self.xapp_gen.logger.info("[Main] Terminating xapp")
            self.kpm_func.terminate(signal.SIGTERM, None)
            return

        # Getting plmn_identity
        plmn_id = gnb_info["globalNbId"]["plmnId"]
        nr_cell_id = gnb_info["globalNbId"]["nbId"]

        self.xapp_gen.logger.info("[xAppMonControlContainer] gnb target plmn identity: {}, nr_cell_id: {}".format(plmn_id, nr_cell_id))
        self.rc_func.set_plmn_identity(plmn_id)

        # Get kpm data
        ran_function_description = self.kpm_func.get_ran_function_description(json_ran_info=gnb_info)
        func_def_dict = ran_function_description.get_dict_of_values()

        # Get RC function
        self.rc_func_desc = self.rc_func.get_ran_function_description(json_ran_info=gnb_info)
        self.rc_func_desc.print_rc_functions()

        func_def_sub_dict = {}
        selected_format = format_action_def_e.END_ACTION_DEFINITION
        if len(func_def_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION]) == 0:
            selected_format = format_action_def_e.FORMAT_1_ACTION_DEFINITION
        else:
            selected_format = format_action_def_e.FORMAT_4_ACTION_DEFINITION
        func_def_sub_dict[selected_format] = func_def_dict[selected_format]

        ev_trigger_tuple = (0, self.event_trigger)
        status = self.kpm_func.subscribe(gnb=self.selected_gnb, ev_trigger=ev_trigger_tuple, func_def=func_def_sub_dict, ran_period_ms=1000, sst=self.sst, sd=self.sd)

        if status != 201:
            self.xapp_gen.logger.error("[xAppMonControlContainer] Error subscribing to gNB {}: {}".format(self.gnb.inventory_name, status))
            self.kpm_func.terminate(signal.SIGTERM, None)
            return

        # Running xApp Thread
        self.xapp_gen.run()

def main(args):
    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    xapp_gen.logger.set_level(string_to_level[args.log_level])
    xapp_container = xAppMonControlContainer(xapp_gen, args.gnb_target, args.event_trigger, args.sst, args.sd, args.plmn, args.nr_cell_id)
    xapp_container.start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ho xApp")

    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")
    parser.add_argument("-p", "--plmn", metavar="<plmn>",
                        help="PLMN ID", type=str, default="00F110")
    parser.add_argument("-n", "--nr_cell_id", metavar="<nr_cell_id>",
                        help="NR Cell ID", type=str, default="00000000000000000000111000000001")
    parser.add_argument("-e", "--event_trigger", metavar="<event_trigger_period>",
                        help="event trigger period in seconds",
                        type=int, default=1)
    parser.add_argument("-s", "--sst", metavar="<sst>",
                        help="SST", type=int, default=1)
    parser.add_argument("-l", "--log_level", metavar="<log_level>",
                        help="Log level", type=str, default="INFO")
    parser.add_argument("-d", "--sd", metavar="<sd>",
                        help="SD", type=int, default=0)
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)
                        
    args = parser.parse_args()
    main(args)