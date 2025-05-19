import time

import setup_imports

import xDevSM.xapp_rc_frame as rc_frame


class RCXapp(rc_frame.XappRCFrame):
    def __init__(self, address):
        super().__init__(address)
        self.logic()

    def logic(self):
        self.run(thread=True)
        time.sleep(30) # waiting for registrations

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

        # FIXME not complete
        self.send_control_request(e2_node_id=gnb.inventory_name, func_def=ran_function_description)




def main():
    xapp = RCXapp("0.0.0.0")


if __name__ == '__main__':
    main()