import time
import argparse
import influxdb_client
import numpy as np
from influxdb_client.client.write_api import SYNCHRONOUS

import setup_imports

import xDevSM.xapp_kpm_frame as kpmframe
from xDevSM.sm_framework.py_oran.kpm.KpmIndicationMsg import measurements_ids
from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e
from xDevSM.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xDevSM.sm_framework.py_oran.kpm.enums import meas_type_enum
from xDevSM.sm_framework.py_oran.kpm.enums import meas_value_e



class KpmXapp(kpmframe.XappKpmFrame):
    def __init__(self, xapp_name, address, port, organization, token, bucket, influxdb_end_point=None):
        super().__init__(xapp_name, address, port)
        self.client_influx = None
        self.write_api = None
        self.bucket = bucket
        self.org = organization
        if not influxdb_end_point is None:
            self.client_influx = influxdb_client.InfluxDBClient(
                    url=influxdb_end_point,
                    token=token,
                    org=organization
            )
            self.write_api = self.client_influx.write_api(write_options=SYNCHRONOUS)
        self.logic()
    
    def _post_init(self, xapp):
        super()._post_init(xapp)
        self.logger.info("Starting logic - kpmxapp")
    
    # Called for each indication message received
    def indication_callback(self, ind_hdr, ind_msg, meid):
        gnbid = meid.decode('utf-8')
        self.logger.info("Received indication message from {}".format(gnbid))        
        # Decoding sender_name
        my_string = bytes(np.ctypeslib.as_array(ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.buf, shape = (ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.len,)))
        sender_name = my_string.decode('utf-8') 
        if not self.client_influx is None:
            if ind_msg.type.value == format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
                for i in range(ind_msg.data.frm_3.ue_meas_report_lst_len):
                    # for each ue
                    meas_report_ue = ind_msg.data.frm_3.meas_report_per_ue[i]
                    # ue id
                    ue_id = self.get_ue_id(meas_report_ue.ue_meas_report_lst)
                    self.logger.info("gnb: {}, sender_name: {}, ue: {}".format(gnbid, sender_name, ue_id))
                    ind_msg_format_1 = meas_report_ue.ind_msg_format_1
                    for j in range(ind_msg_format_1.meas_data_lst_len):
                        meas_data_lst = ind_msg_format_1.meas_data_lst
                        for k in range(meas_data_lst[j].meas_record_len):
                            meas_record_lst_el = meas_data_lst[j].meas_record_lst[k]
                            if ind_msg_format_1.meas_info_lst[k].meas_type.type.value == meas_type_enum.NAME_MEAS_TYPE:
                                self.store_on_influx(gnb_id=gnbid, ue_id=ue_id, meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                    meas_record=meas_record_lst_el)
                            else:
                                self.logger.info("Not supported meas type {}".format(ind_msg_format_1.meas_info_lst[k].meas_type.type.value))
            else:
                self.logger.info("format not supported for storing")
        else:
            ind_msg.print_meas_info(self.logger)


    def sub_failed_callback(self, json_data):
        self.logger.info("subscription failed")

    def logic(self):
        time.sleep(30)
        
        self.register_ind_msg_callback(handler=self.indication_callback)
        self.register_sub_fail_callback(handler=self.sub_failed_callback)
        gnb_list = self.get_list_gnb_ids()
        if len(gnb_list) == 0:
            self.logger.error("no gnb available")
            return
        
        # The logic considers each gnb available for that RIC
        for index, gnb in enumerate(gnb_list):
            self.logger.info("there are some gnbs available selecting the first..")
            json_obj = self.get_ran_info(e2node=gnb)

            ran_function_description = self.get_ran_function_description(json_ran_info=json_obj)
            self.logger.info("end decoding {}".format(ran_function_description))
            func_def_dict = ran_function_description.get_dict_of_values()
            self.logger.debug("Available functions: {}".format(func_def_dict))

            if json_obj["connectionStatus"] != "CONNECTED":
                self.logger.info("E2 node {} not connected! Skipping...".format(gnb.inventory_name))
                continue
            
            self.logger.info("subscribing to uri {}".format(self.uri_subscriptions))

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
                self.logger.error("No supported action definition format")
                self.terminating_xapp()
                return

            # Selecting only supported action definition
            #func_def_sub_dict[selected_format] = [value for value in func_def_dict[selected_format] if value in measurements_ids]

            # Filtering func_def by supported format
            func_def_sub_dict[selected_format] = func_def_dict[selected_format]
            self.logger.debug("Selected functions: {}".format(func_def_dict[selected_format]))

            # Sending subscription
            ev_trigger_tuple = (0, 1000)
            status = self.subscribe(gnb=gnb, ev_trigger=ev_trigger_tuple, func_def=func_def_sub_dict)

            if status != 201:
                    self.logger.error("something during subscription went wrong - status: {}".format(status))
                    return

            # Start running after finishing subscription requests
            if index == len(gnb_list)-1:
                self.run()

    def store_on_influx(self, gnb_id, ue_id, meas_type, meas_record):
        ue_id = "ue_" + str(ue_id)
        p = influxdb_client.Point("xapp-stats").tag("gnb_id", gnb_id).tag("ue_id", ue_id)
        
        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            p.field(meas_type_str, meas_record.union.int_val)
            self.logger.info("{}:{}".format(meas_type_str, meas_record.union.int_val))
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            p.field(meas_type_str, meas_record.union.real_val)
            self.logger.info("{}:{}".format(meas_type_str, meas_record.union.real_val))
        
        # storing on influxdb
        self.write_api.write(bucket=self.bucket, org=self.org, record=p)


    def terminate(self, signum, frame):
        if not self.client_influx is None:
            self.client_influx.close()
        super().terminate(signum, frame)

    

def main(args):
    xapp = KpmXapp("kpm-basic-xapp","0.0.0.0", 8080, args.organization, args.token, args.bucket, args.influx_end_point)
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm xApp")
    
    parser.add_argument("-i", "--influx_end_point", metavar="http://<ip>:port",
                        help="influx db endpoint", type=str, default=None)
    
    parser.add_argument("-o", "--organization", metavar="<organization>",
                        help="influx db organization", type=str, default="docs")
    
    parser.add_argument("-t", "--token", metavar="<token>",
                        help="influx db token", type=str, default="mytoken0==")
    
    parser.add_argument("-b", "--bucket", metavar="<bucket>",
                        help="influx db bucket", type=str, default="xapp_bucket")
    
    args = parser.parse_args()
    
    main(args)

