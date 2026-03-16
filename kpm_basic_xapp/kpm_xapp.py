import time
import signal
import argparse
import influxdb_client
import redis
import numpy as np
import pandas as pd
from influxdb_client.client.write_api import SYNCHRONOUS

import setup_imports

# import xDevSM.kpm.xapp_kpm_frame as kpmframe

# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import xDevSM kpm decorator
from xDevSM.decorators.kpm.kpm_frame import XappKpmFrame


from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e
from xDevSM.sm_framework.py_oran.kpm.enums import format_ind_msg_e
from xDevSM.sm_framework.py_oran.kpm.enums import meas_type_enum
from xDevSM.sm_framework.py_oran.kpm.enums import meas_value_e

logger = None

class DataManager():
    """
    This class manages data storage in InfluxDB, Redis, and CSV.
    """
    def __init__(self, kpm_xapp, organization, token, bucket, influxdb_end_point=None, redis_end_point=None, redis_pwd=None, csv_file=None):
        self.kpm_xapp = kpm_xapp
        self.organization = organization
        self.client_influx = None
        self.write_api = None
        self.client_redis = None
        self.bucket = bucket
        self.org = organization
        self.df = None
        self.df_dict = {}
        self.csv_file = csv_file
        
        if influxdb_end_point:
            self.client_influx = influxdb_client.InfluxDBClient(
                    url=influxdb_end_point,
                    token=token,
                    org=organization
            )
            self.write_api = self.client_influx.write_api(write_options=SYNCHRONOUS)
        
        if redis_end_point:
            try:
                host, port = redis_end_point.split(':')
                self.client_redis = redis.Redis(host=host, 
                                                port=int(port), 
                                                password=redis_pwd,
                                                decode_responses=False)
                self.client_redis.ping()
                logger.info("[DataManager] connected to redis!")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {redis_end_point}: {e}")
                self.client_redis = None
        
        if csv_file:
            self.df_dict = {}
            self.df_dict ["timestamp"]= []
            self.df_dict["ue_id"] = []
            self.df_dict["gnb_id"] = []

    def store_on_influx(self, gnb_id, ue_id, meas_type, meas_record):
        ue_id = "ue_" + str(ue_id)
        p = influxdb_client.Point("xapp-stats").tag("gnb_id", gnb_id).tag("ue_id", ue_id)
        
        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            p.field(meas_type_str, meas_record.union.int_val)
            logger.info("{}:{}".format(meas_type_str, meas_record.union.int_val))
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            p.field(meas_type_str, meas_record.union.real_val)
            logger.info("{}:{}".format(meas_type_str, meas_record.union.real_val))
        
        # storing on influxdb
        self.write_api.write(bucket=self.bucket, org=self.org, record=p)

    def store_on_redis(self, gnb_id, ue_id, meas_type, meas_record):
        """Store measurement in Redis hash"""
        try:
            ue_id_str = "ue_" + str(ue_id)
            key = f"xapp:metrics:{gnb_id}:{ue_id_str}"
            
            meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape=(meas_type.len,)))
            meas_type_str = meas_type_bs.decode('utf-8')
            
            if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
                value = str(meas_record.union.int_val)
            elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
                value = str(meas_record.union.real_val)
            else:
                return
            
            self.client_redis.hset(key, meas_type_str, value)
            self.client_redis.expire(key, 300)  # 5 min expiry
        except Exception as e:
            logger.warning(f"Failed to store on Redis: {e}")

    def store_to_csv(self,gnb_id, ue_id, meas_type, meas_record):
        ue_id = "ue_" + str(ue_id)
        # self.df_dict["ue_id"].append(ue_id)
        # self.df_dict["gnb_id"].append(gnb_id)

        meas_type_bs = bytes(np.ctypeslib.as_array(meas_type.buf, shape = (meas_type.len,)))
        meas_type_str = meas_type_bs.decode('utf-8')
        if meas_type_str not in self.df_dict.keys():
            self.df_dict[meas_type_str] = []
        if meas_record.value.value == meas_value_e.INTEGER_MEAS_VALUE:
            logger.info("{}:{}".format(meas_type_str, meas_record.union.int_val))
            self.df_dict[meas_type_str].append(meas_record.union.int_val)
        elif meas_record.value.value == meas_value_e.REAL_MEAS_VALUE:
            logger.info("{}:{}".format(meas_type_str, meas_record.union.real_val))
            self.df_dict[meas_type_str].append(meas_record.union.real_val)


    # Called for each indication message received
    def indication_callback(self, ind_hdr, ind_msg, meid):
        gnbid = meid.decode('utf-8')
        logger.info("[Main] Received indication message from {}".format(gnbid))        
        # Decoding sender_name
        sender_name = None
        if ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name:
            my_string = bytes(np.ctypeslib.as_array(ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.buf, shape = (ind_hdr.data.kpm_ric_ind_hdr_format_1.sender_name.contents.len,)))
            sender_name = my_string.decode('utf-8') 
        
        if sender_name is None:
            logger.info("[Main]Sender name not specified in the indication message")

        
        if ind_msg.type.value == format_ind_msg_e.FORMAT_3_INDICATION_MESSAGE:
            for i in range(ind_msg.data.frm_3.ue_meas_report_lst_len):
                # for each ue
                meas_report_ue = ind_msg.data.frm_3.meas_report_per_ue[i]
                # ue id
                ue_id = self.kpm_xapp.get_ue_id(meas_report_ue.ue_meas_report_lst)
                if self.csv_file is not None:
                    ue_id_str = "ue_" + str(ue_id)
                    self.df_dict["timestamp"].append(int(time.time() * 1000))
                    self.df_dict["ue_id"].append(ue_id_str)
                    self.df_dict["gnb_id"].append(gnbid)
                logger.info("[Main]gnb: {}, sender_name: {}, ue: {}".format(gnbid, sender_name, ue_id))
                ind_msg_format_1 = meas_report_ue.ind_msg_format_1
                for j in range(ind_msg_format_1.meas_data_lst_len):
                    meas_data_lst = ind_msg_format_1.meas_data_lst
                    for k in range(meas_data_lst[j].meas_record_len):
                        meas_record_lst_el = meas_data_lst[j].meas_record_lst[k]
                        if ind_msg_format_1.meas_info_lst[k].meas_type.type.value == meas_type_enum.NAME_MEAS_TYPE:
                            if not self.client_influx is None:
                                self.store_on_influx(gnb_id=gnbid, ue_id=ue_id, meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                    meas_record=meas_record_lst_el)
                            if not self.client_redis is None:
                                self.store_on_redis(gnb_id=gnbid, ue_id=ue_id, meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                   meas_record=meas_record_lst_el)
                            if not self.csv_file is None:
                                self.store_to_csv(gnb_id=gnbid, ue_id=ue_id, meas_type=ind_msg_format_1.meas_info_lst[k].meas_type.value.name,
                                                meas_record=meas_record_lst_el)
                        else:
                            logger.info("[Main] Not supported meas type {}".format(ind_msg_format_1.meas_info_lst[k].meas_type.type.value))
        else:
            logger.info("[Main] format not supported for storing")
        
        if self.client_influx is None and self.client_redis is None and self.csv_file is None:
            logger.info("[Main]indication message not stored")
            ind_msg.print_meas_info(logger)
    
    def shutdown(self):
        logger.info("[Main] Shutting down DataManager")
        if not self.client_influx is None:
            logger.info("[Main] closing influx connection")
            self.client_influx.close()
        if self.df_dict is not None:
            self.df = pd.DataFrame.from_dict(self.df_dict, orient='index').transpose()
            self.df.to_csv(self.csv_file, index=False)
        if not self.client_redis is None:
            logger.info("[Main] closing redis connection")
            self.client_redis.close()


def sub_failed_callback(json_data):
    logger.info("[Main]subscription failed: {}".format(json_data))




def main(args):
    global logger
        
    # Creating a generic xDevSM RMR xApp
    xapp_gen = xDevSMRMRXapp("0.0.0.0", route_file=args.route_file)
    logger = xapp_gen.logger

    
    # Adding kpm functionalities to the xapp
    kpm_xapp = XappKpmFrame(xapp_gen, 
                            logger, 
                            xapp_gen.server, 
                            xapp_gen.get_xapp_name(), 
                            xapp_gen.rmr_port, 
                            xapp_gen.http_port,xapp_gen.get_pltnamespace(), 
                            xapp_gen.get_app_namespace())
    
    # Creating a DataManager instance
    data_manager = DataManager(kpm_xapp=kpm_xapp, organization=args.organization, token=args.token, bucket=args.bucket,
                               influxdb_end_point=args.influx_end_point, redis_end_point=args.redis_end_point, redis_pwd=args.redis_pwd, csv_file=args.csv_file)
    
    # Registering the DataManager shutdown function to clean data resources
    xapp_gen.register_shutdown(data_manager.shutdown)

    # Registering the outermost rmr handler
    xapp_gen.register_handler(kpm_xapp.handle) 

    # Registering indication message callback
    kpm_xapp.register_ind_msg_callback(handler=data_manager.indication_callback)
    # Registering subscription failed callback
    kpm_xapp.register_sub_fail_callback(handler=sub_failed_callback)

    # Registering termination signal handlers
    signal.signal(signal.SIGINT, kpm_xapp.terminate)
    signal.signal(signal.SIGTERM, kpm_xapp.terminate)

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if not gnb:
        logger.info("[Main] Terminating xapp")
        kpm_xapp.terminate(signal.SIGTERM, None)
        return
    
    # There exist one gnb available
    ran_function_description = kpm_xapp.get_ran_function_description(json_ran_info=gnb_info)
    func_def_dict = ran_function_description.get_dict_of_values()
        
    logger.debug("[Main] Available functions: {}".format(func_def_dict))

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
        logger.error("[Main] No supported action definition format")
        kpm_xapp.terminate(signal.SIGTERM, None)
        return

    # Selecting only supported action definition
    func_def_sub_dict[selected_format] = func_def_dict[selected_format]

    logger.debug("[Main] Selected functions: {}".format(func_def_dict[selected_format]))
    time.sleep(10)
    # Sending subscription
    ev_trigger_tuple = (0, 1000)
    status = kpm_xapp.subscribe(gnb=gnb, ev_trigger=ev_trigger_tuple, func_def=func_def_sub_dict,  ran_period_ms=1000, sst=args.sst, sd=args.sd)

    if status != 201:
        logger.error("[Main] something during subscription went wrong - status: {}".format(status))
        return

    # Start running after finishing subscription requests

    logger.info("[Main] Starting xapp")
    xapp_gen.run()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm xApp")
    
    parser.add_argument("-s", "--sst", metavar="<sst>",
                        help="SST", type=int, default=1)
    
    parser.add_argument("-d", "--sd", metavar="<sd>",
                        help="SD", type=int, default=1)
    
    parser.add_argument("-i", "--influx_end_point", metavar="http://<ip>:port",
                        help="influx db endpoint", type=str, default=None)
    
    parser.add_argument("-o", "--organization", metavar="<organization>",
                        help="influx db organization", type=str, default="docs")
    
    parser.add_argument("-t", "--token", metavar="<token>",
                        help="influx db token", type=str, default="mytoken0==")
    
    parser.add_argument("-b", "--bucket", metavar="<bucket>",
                        help="influx db bucket", type=str, default="xapp_bucket")

    parser.add_argument("--redis_end_point", metavar="<host:port>",
                        help="Redis endpoint", type=str, default=None)
    
    parser.add_argument("--redis_pwd", metavar="<redis_pwd>",
                        help="Redis password", type=str, default=None)

    parser.add_argument("-r", "--route_file", metavar="<route_file>",
                        help="path of xApp route file",
                        type=str, default="./config/uta_rtg.rt")
    
    parser.add_argument("-c", "--csv_file", metavar="<csv_file>",
                        help="path of csv file",
                        type=str)

    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB to subscribe to",
                        type=str)
    
    args = parser.parse_args()
    
    main(args)

