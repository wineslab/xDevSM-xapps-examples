# xAppMonControlContainer

> God node · 32 connections · `digital_twin_prb_xapp/digital_twin_prb_xapp.py`

**Community:** [[Digital Twin PRB Control Logic]]

## Connections by Relation

### calls
- [[main()]] `EXTRACTED`

### contains
- [[digital_twin_prb_xapp.py]] `EXTRACTED`

### method
- [[.start()]] `EXTRACTED`
- [[._try_send_to_gnb()]] `EXTRACTED`
- [[._encode_and_send()]] `EXTRACTED`
- [[._append_control_event()]] `EXTRACTED`
- [[.control_ack_success_callback()]] `EXTRACTED`
- [[._dt_state_machine()]] `EXTRACTED`
- [[.ind_msg_handler()]] `EXTRACTED`
- [[._arm_ack_timer()]] `EXTRACTED`
- [[.control_ack_failure_callback()]] `EXTRACTED`
- [[._dt_queue_step()]] `EXTRACTED`
- [[.__init__()]] `EXTRACTED`
- [[._propagate_to_real()]] `EXTRACTED`
- [[._ack_timeout_fired()]] `EXTRACTED`
- [[._build_subscription_func_def()]] `EXTRACTED`
- [[._decode_meid()]] `EXTRACTED`
- [[.compute_bandwidth()]] `EXTRACTED`
- [[._init_slice_runtime()]] `EXTRACTED`
- [[.store_to_csv()]] `EXTRACTED`
- [[.sub_resolved_callback()]] `EXTRACTED`
- [[._subscribe_per_slice()]] `EXTRACTED`

### rationale_for
- [[Manages KPM monitoring and RC PRB control across a real gNB and its     digital]] `EXTRACTED`

### uses
- [[xDevSMRMRXapp]] `INFERRED`
- [[RadioResourceAllocationControl]] `INFERRED`
- [[XappKpmFrame]] `INFERRED`
- [[meas_type_enum]] `INFERRED`
- [[meas_value_e]] `INFERRED`
- [[format_action_def_e]] `INFERRED`
- [[format_ind_msg_e]] `INFERRED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*