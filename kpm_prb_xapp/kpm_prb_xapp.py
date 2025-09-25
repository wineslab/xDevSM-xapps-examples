import argparse
import signal
import numpy as np
import setup_imports
import time
import pandas as pd
from mdclogpy import Level

# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import xDevSM kpm decorator
from xDevSM.decorators.kpm.kpm_frame import XappKpmFrame
# import xDevSM rc decorator
from xDevSM.decorators.rc.rc_radio_resource_alloc_control import RadioResourceAllocationControl

# kpm related formats
from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e
from xDevSM.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xDevSM.sm_framework.py_oran.kpm.enums import meas_type_enum
from xDevSM.sm_framework.py_oran.kpm.enums import meas_value_e


string_to_level = {"DEBUG": Level.DEBUG,
                "INFO": Level.INFO,
                "WARNING": Level.WARNING,
                "ERROR": Level.ERROR}

class xAppMonControlContainer():
    "This class manage xApp related messages and actions"
    def __init__(self, xapp_gen: xDevSMRMRXapp, gnb_target, csv_file, event_trigger, sst, sd, max_down_throughput, max_up_throughput):
        self.xapp_gen = xapp_gen
        self.gnb_target = gnb_target
        self.csv_file = csv_file
        self.event_trigger = event_trigger*1000
        self.sst = sst
        self.sd = sd
        self.selected_gnb = None
        self.max_down_throughput = max_down_throughput
        self.max_up_throughput = max_up_throughput
        self.rc_func_desc = None
        self.rc_func = RadioResourceAllocationControl(xapp_gen,
                                            logger=xapp_gen.logger,
                                            server=xapp_gen.server,
                                            xapp_name=xapp_gen.get_xapp_name(),
                                            rmr_port=xapp_gen.rmr_port,
                                            mrc=xapp_gen._mrc,
                                            http_port=xapp_gen.http_port,
                                            pltnamespace=xapp_gen.get_pltnamespace(),
                                            app_namespace=xapp_gen.get_app_namespace(),
                                            # control parameters
                                            sst=sst,
                                            sd=sd
                                            )
        self.rc_func.set_max_prb_policy_ratio(100)
        self.rc_func.set_min_prb_policy_ratio(10)
        self.rc_func.set_dedicated_prb_policy_ratio(5)
        self.kpm_func = XappKpmFrame(self.rc_func, xapp_gen.logger, xapp_gen.server, xapp_gen.get_xapp_name(), xapp_gen.rmr_port, xapp_gen.http_port,xapp_gen.get_pltnamespace(), xapp_gen.get_app_namespace())

        # Register the handler for the xApp
        self.xapp_gen.register_handler(self.kpm_func.handle)

        self.kpm_func.register_ind_msg_callback(self.ind_msg_handler)
        self.kpm_func.register_sub_fail_callback(self.sub_failed_callback)

        # Registering termination signal handlers
        signal.signal(signal.SIGINT, self.termination)
        signal.signal(signal.SIGTERM, self.termination)

        # Dataframe to store kpm    data 
        self.df_dict = {}
        self.df_dict["ue_id"] = []
        self.df_dict["gnb_id"] = []
        self.df_dict["MAX_PRB"] = []
        self.df_dict["MIN_PRB"] = []

    def termination(self, signum, frame):
        print(self.df_dict)
        if self.csv_file is not None:
            df = pd.DataFrame.from_dict(self.df_dict, orient='index').transpose()
            df.to_csv(self.csv_file, index=False)
            self.xapp_gen.logger.info("[xAppMonControlContainer] Data saved to {}".format(self.csv_file))
        self.kpm_func.terminate(signum, frame)

    def ind_msg_handler(self, ind_hdr, ind_msg, meid):
        """
        Handle the indication message received from the xApp
        """
        gnbid = meid.decode('utf-8')
        self.xapp_gen.logger.info("[xAppMonControlContainer] Received indication message from {}".format(gnbid))
        downlink_bandwidth = 0
        uplink_bandwidth = 0
        sender_name = None
        if ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name:
            my_string = bytes(np.ctypeslib.as_array(ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.buf, shape = (ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.len,)))
            sender_name = my_string.decode('utf-8') 
        
        if sender_name is None:
            self.xapp_gen.logger.info("[xAppMonControlContainer]Sender name not specified in the indication message")

        
        if ind_msg.type.value == format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
            for i in range(ind_msg.data.frm_3.ue_meas_report_lst_len):
                # for each ue
                meas_report_ue = ind_msg.data.frm_3.meas_report_per_ue[i]
                # ue id
                ue_id_value = self.kpm_func.get_ue_id(meas_report_ue.ue_meas_report_lst)
                self.xapp_gen.logger.info("[xAppMonControlContainer]gnb: {}, sender_name: {}, ue: {}".format(gnbid, sender_name, ue_id_value))
                ind_msg_format_1 = meas_report_ue.ind_msg_format_1
                self.df_dict["ue_id"].append(ue_id_value)
                self.df_dict["gnb_id"].append(gnbid)
                self.df_dict["MAX_PRB"].append(self.rc_func.get_max_prb_policy_ratio())
                self.df_dict["MIN_PRB"].append(self.rc_func.get_min_prb_policy_ratio())
                for j in range(ind_msg_format_1.meas_data_lst_len):
                    meas_data_lst = ind_msg_format_1.meas_data_lst
                    for k in range(meas_data_lst[j].meas_record_len):
                        meas_record_lst_el = meas_data_lst[j].meas_record_lst[k]
                        if ind_msg_format_1.meas_info_lst[k].meas_type.type.value == meas_type_enum.NAME_MEAS_TYPE:
                            #self.log_kpm_metrics(meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                            #                        meas_record=meas_record_lst_el)
                            # Compute uplink and downlink bandwidth
                            self.store_to_csv(gnb_id=gnbid, ue_id=ue_id_value, meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                meas_record=meas_record_lst_el)
                            tmp_down, tmp_up = self.compute_bandwidth(meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                                    meas_record=meas_record_lst_el)
                            downlink_bandwidth = downlink_bandwidth + tmp_down
                            uplink_bandwidth = uplink_bandwidth + tmp_up
                        else:
                            self.xapp_gen.logger.info("[xAppMonControlContainer] Not supported meas type {}".format(ind_msg_format_1.meas_info_lst[k].meas_type.type.value))
            self.xapp_gen.logger.info("[xAppMonControlContainer] Downlink Bandwidth: {}, Uplink Bandwidth: {}, max prb: {}".format(downlink_bandwidth, uplink_bandwidth, self.rc_func.get_max_prb_policy_ratio()))
            if downlink_bandwidth > self.max_down_throughput or (self.max_up_throughput is not None and uplink_bandwidth > self.max_up_throughput):
                # Here you can add the logic to handle the exceeded bandwidth, e.g., sending a control request

                self.xapp_gen.logger.info("[xAppMonControlContainer] Downlink or Uplink Bandwidth exceeded the limit! Downlink: {}, Uplink: {}, xapp max prb now: {}".format(downlink_bandwidth, uplink_bandwidth, self.rc_func.get_max_prb_policy_ratio()))
                if self.rc_func.get_max_prb_policy_ratio() > self.rc_func.get_min_prb_policy_ratio() + 5: # keeping a margin of 5%
                    new_max_prb = self.rc_func.get_max_prb_policy_ratio() - 5 # removing 5% or prb
                    self.rc_func.set_max_prb_policy_ratio(new_max_prb)
                    # Sending SLICE-LEVEL PRB Quota
                else:
                    self.xapp_gen.logger.error("[xAppMonControlContainer] Max PRB Policy Ratio is not greater than 20!")
                
                self.rc_func.send(e2_node_id=self.selected_gnb.inventory_name,ran_func_dsc=self.rc_func_desc,ue_id=meas_report_ue.ue_meas_report_lst,control_action_id=6)

    def sub_failed_callback(self, json_data):
        self.xapp_gen.logger.info("[xAppMonControlContainer] subscription failed: {}".format(json_data))

    def log_kpm_metrics(self, meas_type, meas_record):
        """
        Log the KPM metrics received from the xApp
        """
        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            self.xapp_gen.logger.info("{}:{}".format(meas_type_str, meas_record.union.int_val))
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            self.xapp_gen.logger.info("{}:{}".format(meas_type_str, meas_record.union.real_val))

    def compute_bandwidth(self, meas_type, meas_record):
        """
        Compute the uplink and downlink bandwidth from the KPM metrics
        """
        downlink_bandwidth = 0
        up_link_bandwidth = 0
        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_type_str == "DRB.UEThpDl":
            if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
                downlink_bandwidth = meas_record.union.int_val/1024
            elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
                downlink_bandwidth = meas_record.union.real_val/1024
            # self.xapp_gen.logger.info("[xAppMonControlContainer] Downlink Bandwidth: {}".format(downlink_bandwidth))
        elif meas_type_str == "DRB.UEThpUl":
            if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
                up_link_bandwidth = meas_record.union.int_val/1024
            elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
                up_link_bandwidth = meas_record.union.real_val/1024
            # self.xapp_gen.logger.info("[xAppMonControlContainer] Uplink Bandwidth: {}".format(up_link_bandwidth))


        return downlink_bandwidth, up_link_bandwidth
    
    def store_to_csv(self,gnb_id, ue_id, meas_type, meas_record):
        ue_id = "ue_" + str(ue_id)
        

        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_type_str not in self.df_dict.keys():
            self.df_dict[meas_type_str] = []
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            self.df_dict[meas_type_str].append(meas_record.union.int_val)
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            self.df_dict[meas_type_str].append(meas_record.union.real_val)


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

        self.xapp_gen.logger.info("[xAppMonControlContainer] plmn identity: {}".format(plmn_id))
        self.rc_func.set_plmn_identity(plmn_id)

        # Get kpm data
        ran_function_description = self.kpm_func.get_ran_function_description(json_ran_info=gnb_info)
        func_def_dict = ran_function_description.get_dict_of_values()

        # Get RC function
        self.rc_func_desc = self.rc_func.get_ran_function_description(json_ran_info=gnb_info)
        self.rc_func_desc.print_rc_functions()

        # Only one ran function format at time is supported for now
        # Selecting format 4 or 1 (these are coherent with the wrapper provided)
        # If you want to support more formats, change function gen_action_definition in wrapper
        func_def_sub_dict = {}
        selected_format = format_action_def_e.END_ACTION_DEFINITION
        if len(func_def_dict[format_action_def_e.FORMAT_4_ACTION_DEFINITION]) == 0:
            selected_format = format_action_def_e.FORMAT_1_ACTION_DEFINITION
        else:
            selected_format = format_action_def_e.FORMAT_4_ACTION_DEFINITION
        
        if selected_format == format_action_def_e.END_ACTION_DEFINITION:
            self.xapp_gen.logger.error("[xAppMonControlContainer] No supported action definition format")
            self.kpm_func.terminate(signal.SIGTERM, None)
            return
        if "DRB.UEThpDl" not in func_def_dict[selected_format] or "DRB.UEThpUl" not in func_def_dict[selected_format]:
            self.xapp_gen.logger.error("[xAppMonControlContainer] No supported action definition format for DRB.UEThpDl or DRB.UEThpUl")
            self.kpm_func.terminate(signal.SIGTERM, None)
            return
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
    xapp_container = xAppMonControlContainer(xapp_gen, args.gnb_target, args.csv_file, args.event_trigger, args.sst, args.sd, args.max_down_throughput, args.max_up_throughput)
    xapp_container.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm prb xApp")

    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")
    parser.add_argument("-c", "--csv_file", metavar="<csv_file>",
                        help="path of csv file",
                        type=str)
    parser.add_argument("-e", "--event_trigger", metavar="<event_trigger_period>",
                        help="event trigger period in seconds",
                        type=int, default=1)
    parser.add_argument("-m", "--max_down_throughput", metavar="<max_down_throughput>",
                        help="Max Downlink Throughput in Mb/s", type=int, default=50)
    parser.add_argument("-n", "--max_up_throughput", metavar="<max_up_throughput>",
                        help="Max Uplink Throughput in Mb/s", type=int, default=None)
    parser.add_argument("-s", "--sst", metavar="<sst>",
                        help="SST", type=int, default=1)
    parser.add_argument("-d", "--sd", metavar="<sd>",
                        help="SD", type=int, default=0)
    parser.add_argument("-l", "--log_level", metavar="<log_level>",
                        help="Log level", type=str, default="INFO")
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)

    main(parser.parse_args())