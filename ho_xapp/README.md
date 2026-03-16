# HO xApp

Example of a Radio Resource Connected Mobility Control (RC) xApp built using the xDevSM framework.

This xApp subscribes to a target E2 node (or the first available one) and triggers a handover procedure for the first UE listed within the source E2 node, transferring it to the selected target E2 node.



### Options
```python
  -r <route_file>, --route_file <route_file>
                        path of xApp route file
  -p <plmn>, --plmn <plmn>
                        PLMN ID target cell
  -n <nr_cell_id>, --nr_cell_id <nr_cell_id>
                        NR Cell ID target cell
  -e <event_trigger_period>, --event_trigger <event_trigger_period>
                        event trigger period in seconds
  -s <sst>, --sst <sst>
                        SST
  -l <log_level>, --log_level <log_level>
                        Log level
  -d <sd>, --sd <sd>    SD
  -g <gnb_target>, --gnb_target <gnb_target>
                        gNB to subscribe to (source gnb)
```