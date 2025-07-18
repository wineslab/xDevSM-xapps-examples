import time
import argparse

import setup_imports

from xDevSM.rc.rc_radio_resource_alloc_control import RadioResourceAllocationControl



class RCXapp(RadioResourceAllocationControl):
    def __init__(self, address, plmn_identity, sst, sd, min_prb_policy_ratio, max_prb_policy_ratio, dedicated_prb_policy_ratio):
        super().__init__(address, plmn_identity, sst, sd, min_prb_policy_ratio, max_prb_policy_ratio, dedicated_prb_policy_ratio)
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
                                            ue_id=None  # Use mock UE ID
                                            )
        




def main(args):
    xapp = RCXapp("0.0.0.0", args.plmn, args.sst, args.sd, args.min_prb_policy_ratio, args.max_prb_policy_ratio, args.dedicated_prb_policy_ratio)


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