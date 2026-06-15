# Digital Twin PRB Control Logic

> 41 nodes

## Key Concepts

- **xAppMonControlContainer** (32 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **digital_twin_prb_xapp.py** (11 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._try_send_to_gnb()** (7 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.start()** (7 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._encode_and_send()** (6 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **main()** (6 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._append_control_event()** (5 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.ind_msg_handler()** (5 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._dt_state_machine()** (5 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.control_ack_success_callback()** (5 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._dt_queue_step()** (4 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._propagate_to_real()** (4 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._arm_ack_timer()** (4 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.control_ack_failure_callback()** (4 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **_normalize_plmn()** (3 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **load_config()** (3 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._ack_timeout_fired()** (3 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._decode_meid()** (3 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._build_subscription_func_def()** (3 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.compute_bandwidth()** (2 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.store_to_csv()** (2 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._init_slice_runtime()** (2 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **._subscribe_per_slice()** (2 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.sub_resolved_callback()** (2 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **.termination()** (1 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- *... and 16 more nodes in this community*

## Relationships

- [[xApp Entrypoints & RMR Core]] (12 shared connections)
- [[xApp Framework Handlers & Namespaces]] (3 shared connections)
- [[PRB Control xApp]] (2 shared connections)

## Source Files

- `digital_twin_prb_xapp/digital_twin_prb_xapp.py`

## Audit Trail

- EXTRACTED: 140 (95%)
- INFERRED: 7 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*