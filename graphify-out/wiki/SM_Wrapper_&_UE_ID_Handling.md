# SM Wrapper & UE ID Handling

> 16 nodes

## Key Concepts

- **BaseXDevSMWrapper** (17 connections) — `xDevSM/decorators/base.py`
- **Values** (10 connections) — `xDevSM/utils/constants.py`
- **ue_id_e2sm_t** (5 connections) — `xDevSM/decorators/kpm/kpm_frame.py`
- **ue_id_e2sm_t** (4 connections) — `xDevSM/decorators/control.py`
- **ByteArray** (4 connections) — `xDevSM/decorators/report.py`
- **.get_mock_du_ue_id()** (3 connections) — `xDevSM/decorators/control.py`
- **c_uint32** (3 connections) — `xDevSM/decorators/control.py`
- **.get_mock_ue_id()** (3 connections) — `xDevSM/decorators/control.py`
- **c_ulong** (3 connections) — `xDevSM/decorators/control.py`
- **.get_ue_id()** (2 connections) — `xDevSM/decorators/kpm/kpm_frame.py`
- **.send_subscription()** (2 connections) — `xDevSM/decorators/report.py`
- **.send()** (1 connections) — `xDevSM/decorators/base.py`
- **.handle()** (1 connections) — `xDevSM/decorators/base.py`
- **.terminate()** (1 connections) — `xDevSM/decorators/base.py`
- **.get_ran_function_description()** (1 connections) — `xDevSM/decorators/base.py`
- **Base class for XDevSM decorators.     This class can be extended to create speci** (1 connections) — `xDevSM/decorators/base.py`

## Relationships

- [[Base xApp & SM Decorators]] (5 shared connections)
- [[xApp Control Service]] (4 shared connections)
- [[xApp Report Service]] (4 shared connections)
- [[xApp Entrypoints & RMR Core]] (4 shared connections)
- [[KPM Indication Message Types]] (1 shared connections)
- [[xApp Framework Handlers & Namespaces]] (1 shared connections)

## Source Files

- `xDevSM/decorators/base.py`
- `xDevSM/decorators/control.py`
- `xDevSM/decorators/kpm/kpm_frame.py`
- `xDevSM/decorators/report.py`
- `xDevSM/utils/constants.py`

## Audit Trail

- EXTRACTED: 29 (48%)
- INFERRED: 32 (52%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*