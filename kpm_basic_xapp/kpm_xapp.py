import time

import setup_imports

import xDevSM.xapp_kpm_frame as kpmframe
from xDevSM.sm_framework.py_oran.kpm.KpmIndicationMsg import measurements_ids
from xDevSM.sm_framework.py_oran.kpm.enums import format_action_def_e



class KpmXapp(kpmframe.XappKpmFrame):
    def __init__(self, xapp_name, address, port):
        super().__init__(xapp_name, address, port)
        self.logic()
    
    def _post_init(self, xapp):
        super()._post_init(xapp)
        self.logger.info("Starting logic - kpmxapp")
    
    def indication_callback(self, ind_hdr, ind_msg):
        self.logger.info("Received callback")
        ind_msg.print_meas_info(self.logger)

    def sub_failed_callback(self, json_data):
        self.logger.info("subscription failed")

    def logic(self):
        time.sleep(30)
        # The logic considers each gnb available for that RIC
        self.register_ind_msg_callback(handler=self.indication_callback)
        self.register_sub_fail_callback(handler=self.sub_failed_callback)
        gnb_list = self.get_list_gnb_ids()
        if len(gnb_list) == 0:
            self.logger.error("no gnb available")
            return

        for index, gnb in enumerate(gnb_list):
            self.logger.info("there are some gnbs available selecting the first..")
            json_obj = self.get_ran_info(e2node=gnb)

            if json_obj["connectionStatus"] != "CONNECTED":
                self.logger.info("E2 node {} not connected! Skipping...".format(gnb.inventory_name))
                continue
            
            self.logger.info("subscribing to uri {}".format(self.uri_subscriptions))

            ran_function_description = self.get_ran_function_description(json_ran_info=json_obj)
            self.logger.info("end decoding {}".format(ran_function_description))
            func_def_dict = ran_function_description.get_dict_of_values()
            self.logger.debug("Available functions: {}".format(func_def_dict))

            # Only one ran function format at time is supported for now
            # Selecting format 4 or 1  (these are coherent with the wrapper provided)
            # If you want to support more format, change function gen_action_definition in wrapper
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
            func_def_sub_dict[selected_format] = [value for value in func_def_dict[selected_format] if value in measurements_ids]

            self.logger.debug("Selected functions: {}".format(func_def_sub_dict))

            # Sending subscription
            ev_trigger_tuple = (0, 1000)
            status = self.subscribe(gnb=gnb, ev_trigger=ev_trigger_tuple, func_def=func_def_sub_dict)

            if status != 201:
                    self.logger.error("something during subscription went wrong - status: {}".format(status))
                    return

            # Start running after finishing subscription requests
            if index == len(gnb_list)-1:
                self.run()



    

def main():
    xapp = KpmXapp("kpm-basic-xapp","0.0.0.0",8080)


if __name__ == '__main__':
    main()

