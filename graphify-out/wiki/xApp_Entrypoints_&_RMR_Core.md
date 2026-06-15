# xApp Entrypoints & RMR Core

> 77 nodes

## Key Concepts

- **XappKpmFrame** (28 connections) — `xDevSM/decorators/kpm/kpm_frame.py`
- **meas_value_e** (21 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **meas_type_enum** (21 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **xAppMonControlContainer** (18 connections) — `kpm_prb_xapp/kpm_prb_xapp.py`
- **format_action_def_e** (18 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **enums.py** (16 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **xAppMonControlContainer** (13 connections) — `ho_xapp/ho_xapp.py`
- **format_ind_msg_e** (12 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **ConnectedModeMobilityControl** (11 connections) — `xDevSM/decorators/rc/rc_connected_mode_mobility.py`
- **enum_value_e** (10 connections) — `xDevSM/sm_framework/py_oran/kpm/enums.py`
- **xDevSMRMRXapp** (9 connections) — `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- **ho_xapp.py** (9 connections) — `ho_xapp/ho_xapp.py`
- **xDevSMRMRXapp** (9 connections) — `ho_xapp/ho_xapp.py`
- **kpm_xapp.py** (9 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **kpm_prb_xapp.py** (9 connections) — `kpm_prb_xapp/kpm_prb_xapp.py`
- **xDevSMRMRXapp** (9 connections) — `kpm_prb_xapp/kpm_prb_xapp.py`
- **meas_data_basic_mue_t** (9 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **MeasData.py** (8 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **meas_record_lst_t** (7 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **Logger** (7 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **ByteArray** (6 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **main()** (5 connections) — `ho_xapp/ho_xapp.py`
- **main()** (5 connections) — `kpm_prb_xapp/kpm_prb_xapp.py`
- **Union** (5 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- **meas_type_union** (5 connections) — `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- *... and 52 more nodes in this community*

## Relationships

- [[Digital Twin PRB Control Logic]] (12 shared connections)
- [[xApp Framework Handlers & Namespaces]] (11 shared connections)
- [[KPM Indication Message Types]] (9 shared connections)
- [[Data Storage (Influx/Redis/CSV)]] (7 shared connections)
- [[KPM Function Definition Builder]] (7 shared connections)
- [[PRB Control xApp]] (6 shared connections)
- [[SM Wrapper & UE ID Handling]] (4 shared connections)
- [[Base xApp & SM Decorators]] (2 shared connections)
- [[xApp Report Service]] (1 shared connections)
- [[xApp Control Service]] (1 shared connections)

## Source Files

- `digital_twin_prb_xapp/digital_twin_prb_xapp.py`
- `ho_xapp/ho_xapp.py`
- `kpm_basic_xapp/kpm_xapp.py`
- `kpm_prb_xapp/kpm_prb_xapp.py`
- `xDevSM/decorators/kpm/kpm_frame.py`
- `xDevSM/decorators/rc/rc_connected_mode_mobility.py`
- `xDevSM/sm_framework/py_oran/kpm/MeasData.py`
- `xDevSM/sm_framework/py_oran/kpm/enums.py`

## Audit Trail

- EXTRACTED: 233 (61%)
- INFERRED: 149 (39%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*