# xApp Framework Handlers & Namespaces

> 38 nodes

## Key Concepts

- **xDevSMRMRXapp** (42 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **RadioBearerControl** (11 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **rc_xapp.py** (3 connections) — `radio_bearer_control_xapp/rc_xapp.py`
- **main()** (3 connections) — `radio_bearer_control_xapp/rc_xapp.py`
- **.__init__()** (3 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.get_ran_info()** (3 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.get_selected_e2node_info()** (3 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **write_routing_table()** (3 connections) — `xDevSM/utils/utility.py`
- **.register_shutdown()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **._dispatch_event()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.get_app_namespace()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.get_pltnamespace()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.get_xapp_name()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.loading_ports()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.handle()** (2 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.__init__()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **.set_drb_id()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **.set_qos_flow_id()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **.set_qos_flow_mapping_indication()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **.generate_control_request()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **.logic()** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **Radio Bearer Control Decorator** (1 connections) — `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- **RMRXapp** (1 connections)
- **.__config_get_handler()** (1 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- **.__healthy_get_alive_handler()** (1 connections) — `xDevSM/handlers/xDevSM_rmr_xapp.py`
- *... and 13 more nodes in this community*

## Relationships

- [[xApp Entrypoints & RMR Core]] (11 shared connections)
- [[Base xApp & SM Decorators]] (4 shared connections)
- [[Digital Twin PRB Control Logic]] (3 shared connections)
- [[PRB Control xApp]] (3 shared connections)
- [[xApp Control Service]] (1 shared connections)
- [[Data Storage (Influx/Redis/CSV)]] (1 shared connections)
- [[SM Wrapper & UE ID Handling]] (1 shared connections)

## Source Files

- `radio_bearer_control_xapp/rc_xapp.py`
- `xDevSM/decorators/rc/rc_radio_bearer_control.py`
- `xDevSM/handlers/xDevSM_rmr_xapp.py`
- `xDevSM/utils/utility.py`

## Audit Trail

- EXTRACTED: 97 (90%)
- INFERRED: 11 (10%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*