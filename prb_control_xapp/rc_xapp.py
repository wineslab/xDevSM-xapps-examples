import time
import argparse
import signal

import influxdb_client
import redis
import setup_imports


# import xDevSM base xapp
from xDevSM.handlers.xDevSM_rmr_xapp import xDevSMRMRXapp

# import RC Radio Resource Allocation Control Decorator
from xDevSM.decorators.rc.rc_radio_resource_alloc_control import RadioResourceAllocationControl


logger = None

class PRBCotrolXAppDataManager():
    def __init__(self, rc_xapp, time_stamp_file_name, influx_end_point, organization, token, bucket, redis_end_point, query_range):
        self.rc_xapp = rc_xapp
        self.time_stamp_file_name = time_stamp_file_name
        self.influx_end_point = influx_end_point
        self.organization = organization
        self.token = token
        self.bucket = bucket
        self.redis_end_point = redis_end_point
        self.influx_client = None
        self.redis_client = None
        self.query_range = query_range
        self.query_api_influx = None
        self.rc_xapp.register_rc_control_ack_suc_callback(self.handle_control_ack)
        self._setup_influxdb_client()
        self._setup_redis_client()
    
    def _setup_influxdb_client(self):
        if self.influx_end_point:
            self.influx_client = influxdb_client.InfluxDBClient(
                url=self.influx_end_point,
                token=self.token,
                org=self.organization
            )
            logger.info("[PRBCotrolXAppDataManager] InfluxDB client set up successfully.")
            self.query_api_influx = self.influx_client.query_api_influx()
        else:
            logger.warning("[PRBCotrolXAppDataManager] InfluxDB endpoint not provided. Skipping InfluxDB client setup.")
    
    def _setup_redis_client(self):
        if self.redis_end_point:
            host, port = self.redis_end_point.split(":")
            self.redis_client = redis.Redis(host=host, port=int(port))
            logger.info("[PRBCotrolXAppDataManager] Redis client set up successfully.")
        else:
            logger.warning("[PRBCotrolXAppDataManager] Redis endpoint not provided. Skipping Redis client setup.")

    def handle_control_ack(self):
        global logger
        logger.info("[PRBCotrolXAppDataManager] Control Ack received!")
        if self.time_stamp_file_name:
            with open(self.time_stamp_file_name, "a") as f:
                timestamp_ms = int(time.time() * 1000)
                f.write(f"{timestamp_ms} - ACK - [PRBCotrolXAppDataManager] Control Ack received!\n")
        self.rc_xapp.terminate(signal.SIGTERM, None)
    
    def read_data_from_influx(self):
        if not self.influx_client:
            logger.error("[PRBCotrolXAppDataManager] InfluxDB client is not set up.")
            return None
        query = 'from(bucket:"{}") |> range(start: {})'.format(self.bucket, self.query_range)
        result = self.query_api_influx.query(org=self.organization, query=query)
        return result

    def get_all_gnbs(self):
        """Get all unique gNB IDs from the database"""
        query = '''
        from(bucket: "{}")
            |> range(start: {})
            |> filter(fn: (r) => r._measurement == "xapp-stats")
            |> keep(columns: ["gnb_id"])
            |> distinct(column: "gnb_id")
        '''
        if self.query_api_influx is None:
            logger.error("[PRBCotrolXAppDataManager] InfluxDB client is not set up.")
            return []
        result = self.query_api_influx.query(query.format(self.bucket, self.query_range))
        gnb_ids = []
        
        for table in result:
            for record in table.records:
                gnb_ids.append(record.values.get("gnb_id"))
        
        return sorted(set(gnb_ids))
    
    def get_all_ues(self):
        """Get all unique UE IDs from the database"""
        query = '''
        from(bucket: "{}")
            |> range(start: {})
            |> filter(fn: (r) => r._measurement == "xapp-stats")
            |> keep(columns: ["ue_id"])
            |> distinct(column: "ue_id")
        '''
        if self.query_api_influx is None:
            logger.error("[PRBCotrolXAppDataManager] InfluxDB client is not set up.")
            return []
        result = self.query_api_influx.query(query.format(self.bucket, self.query_range))
        ue_ids = []
        
        for table in result:
            for record in table.records:
                ue_ids.append(record.values.get("ue_id"))
        
        return sorted(set(ue_ids))

    def get_ues_by_gnb(self, gnb_id):
        """Get all UE IDs associated with a specific gNB"""
        query = '''
        from(bucket: "{}")
            |> range(start: {})
            |> filter(fn: (r) => r._measurement == "xapp-stats")
            |> filter(fn: (r) => r.gnb_id == "{}")
            |> keep(columns: ["ue_id"])
            |> distinct(column: "ue_id")
        '''
        if self.query_api_influx is None:
            logger.error("[PRBCotrolXAppDataManager] InfluxDB client is not set up.")
            return []
        result = self.query_api_influx.query(query.format(self.bucket, self.query_range, gnb_id))
        ue_ids = []
        
        for table in result:
            for record in table.records:
                ue_ids.append(record.values.get("ue_id"))
        
        return sorted(set(ue_ids))

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
                                            dedicated_prb_policy_ratio=args.dedicated_prb_policy_ratio,
                                            ue_id_type=args.mock_du_ue_id,
                                            ue_id=args.ue_id # as int so the structure is built inside the decorator
                                            )

    # Register the handler for the xApp
    xapp_gen.register_handler(rc_xapp.handle)

    prb_data_manager = PRBCotrolXAppDataManager(rc_xapp, args.time_stamp, args.influx_end_point, args.organization, args.token, args.bucket, args.redis_end_point, args.query_range)
    
    # Register control ack handler
    rc_xapp.register_rc_control_ack_suc_callback(prb_data_manager.handle_control_ack)

    # Registering termination signal handlers
    signal.signal(signal.SIGINT, rc_xapp.terminate)
    signal.signal(signal.SIGTERM, rc_xapp.terminate)

    # Start the xApp
    xapp_gen.run(thread=True)

    # testing
    # print(prb_data_manager.read_data_from_influx())
    # print(prb_data_manager.get_all_gnbs())
    # print(prb_data_manager.get_all_ues())
    # print(prb_data_manager.get_ues_by_gnb("gnb_001_001_00000e00"))
    # print(prb_data_manager.get_ues_by_gnb("gnb_001_007_00000e00"))

    # time.sleep(10)  # waiting for registrations

    gnb, gnb_info = xapp_gen.get_selected_e2node_info(args.gnb_target)
    if not gnb:
        logger.info("[Main] Terminating xapp")
        rc_xapp.terminate(signal.SIGTERM, None)
        return

    ran_function_description = rc_xapp.get_ran_function_description(json_ran_info=gnb_info)
    ran_function_description.print_rc_functions()


    logger.info("[Main] Sending RC Control Request to gNB: {}".format(gnb.inventory_name))
    
    if args.time_stamp:
        with open(args.time_stamp, "a") as f:
            timestamp_ms = int(time.time() * 1000)
            f.write(f"{timestamp_ms} - SEND - [Main] Send Control Request\n")
    
    rc_xapp.send(e2_node_id=gnb.inventory_name,
                ran_func_dsc=ran_function_description,
                ue_id_struct=None, # this ue id is the struct
                control_action_id=6)  # Slice-level PRB quota

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="prb xApp")

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
    parser.add_argument("-g", "--gnb_target", metavar="<gnb_target>",
                        help="gNB where to send the control request",
                        type=str)
    # interaction with a KPM xApp
    parser.add_argument("--influx_end_point", metavar="http://<ip>:port",
                        help="influx db endpoint", type=str, default=None)
    
    parser.add_argument("--organization", metavar="<organization>",
                        help="influx db organization", type=str, default="docs")
    
    parser.add_argument("--token", metavar="<token>",
                        help="influx db token", type=str, default="mytoken0==")
    
    parser.add_argument("--bucket", metavar="<bucket>",
                        help="influx db bucket", type=str, default="xapp_bucket")

    parser.add_argument("--redis_end_point", metavar="<host:port>",
                        help="Redis endpoint", type=str, default=None)
    
    # TODO - check if this could be used also for redis
    parser.add_argument("--query_range", metavar="<query_range>",
                        help="Range for InfluxDB queries, e.g., -30d for last 30 days", type=str, default="-30d")
    
    # Debugging and testing
    parser.add_argument("-t", "--time_stamp", metavar="<time_stamp_file>",
                        help="Records time stamp of control message sent and control ack received in .txt file",
                        type=str, default=None)
    # change type of gnb ue id to mock
    parser.add_argument("-m", "--mock_du_ue_id",
                        help="Type of ue id to mock, defaults to get_mock_ue_id if not passed",
                        action="store_true")
    # ue id
    parser.add_argument("-u", "--ue_id", metavar="<ue_id>",
                        help="ue id to use when db not available",
                        type=int, default=1)
    
    args = parser.parse_args()
    main(args)