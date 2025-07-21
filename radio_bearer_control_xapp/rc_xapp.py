import time
import argparse

import setup_imports

from xDevSM.rc.rc_radio_bearer_control import RadioBearerControl



class RCXapp(RadioBearerControl):
    def __init__(self, address, drb_id, qos_flow_id, qos_flow_mapping_indication):
        super().__init__(address, drb_id, qos_flow_id, qos_flow_mapping_indication)
        self.logic()

    def logic(self):
        self.run(thread=True)
        time.sleep(10) # waiting for registrations

        # add callbacks

        gnb_list = self.get_list_gnb_ids()
        if len(gnb_list) == 0:
            self.logger.error("no gnb available")
            return
        
        # We send control only to the first gNB 
        # (usually this should be selected based on the inventory_name)
        gnb_to_use = None
        for index, gnb in enumerate(gnb_list):
            json_obj = self.get_ran_info(e2node=gnb)
            if json_obj["connectionStatus"] == "CONNECTED":
                gnb_to_use = gnb
                break
        # gnb_to_use = gnb_list[0]
        if gnb_to_use is None:
            self.logger.error("No gNB connected")
            return

        self.logger.info("gnb selected: {}".format(gnb_to_use.inventory_name))
        gnb_info = self.get_ran_info(gnb)

        ran_function_description = self.get_ran_function_description(json_ran_info=gnb_info)
        
        self.logger.info("GLOBAL ID: {}".format(gnb.global_nb_id))
        self.logger.info("INVENTORY NAME: {}".format(gnb.inventory_name))
        # Printing ran function description
        ran_function_description.print_rc_functions()

        self.send_control_request(e2_node_id=gnb.inventory_name,
                                            ran_func_dsc=ran_function_description,
                                            ue_id=None,  # Use mock UE ID
                                            control_action_id=2)  # QoS flow mapping configuration

def main(args):
    xapp = RCXapp("0.0.0.0", args.drb_id, args.qos_flow_id, args.qos_flow_mapping_indication)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="kpm xApp")

    parser.add_argument("-d", "--drb_id", metavar="<drb_id>",
                        help="DRB ID", type=int, default=1)
    parser.add_argument("-q", "--qos_flow_id", metavar="<qos_flow_id>",
                        help="QoS Flow ID", type=int, default=10)
    parser.add_argument("-m", "--qos_flow_mapping_indication", metavar="<qos_flow_mapping_indication>",
                        help="QoS Flow Mapping Indication", type=int, default=1)
    
    args = parser.parse_args()
    main(args)