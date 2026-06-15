# xApp Report Service

> 21 nodes

## Key Concepts

- **xAppReportService** (21 connections) — `xDevSM/decorators/report.py`
- **._handle_indication()** (3 connections) — `xDevSM/decorators/report.py`
- **.get_ran_function_description()** (2 connections) — `xDevSM/decorators/report.py`
- **.decode_message()** (2 connections) — `xDevSM/decorators/report.py`
- **.get_subscription_id()** (2 connections) — `xDevSM/decorators/report.py`
- **.remove_sub_id()** (2 connections) — `xDevSM/decorators/report.py`
- **.subs_response_cb()** (2 connections) — `xDevSM/decorators/report.py`
- **.register_sub_resolved_callback()** (2 connections) — `xDevSM/decorators/report.py`
- **.register_sub_fail_callback()** (2 connections) — `xDevSM/decorators/report.py`
- **.register_ind_msg_callback()** (2 connections) — `xDevSM/decorators/report.py`
- **.__init__()** (1 connections) — `xDevSM/decorators/report.py`
- **.handle()** (1 connections) — `xDevSM/decorators/report.py`
- **.send()** (1 connections) — `xDevSM/decorators/report.py`
- **.terminate()** (1 connections) — `xDevSM/decorators/report.py`
- **.get_indication_msg_callback()** (1 connections) — `xDevSM/decorators/report.py`
- **Base handler for DApp Reports.** (1 connections) — `xDevSM/decorators/report.py`
- **Get decoded ran function description         Parameters:         ----------** (1 connections) — `xDevSM/decorators/report.py`
- **Parameters:         ----------         inventory_name (str): gnb inventory name** (1 connections) — `xDevSM/decorators/report.py`
- **Register a callback fired when the async subscription response resolves** (1 connections) — `xDevSM/decorators/report.py`
- **This method registers the function to be called when received an indication mess** (1 connections) — `xDevSM/decorators/report.py`
- **This method registers the function to be called when received an indication mess** (1 connections) — `xDevSM/decorators/report.py`

## Relationships

- [[SM Wrapper & UE ID Handling]] (4 shared connections)
- [[xApp Entrypoints & RMR Core]] (1 shared connections)
- [[Base xApp & SM Decorators]] (1 shared connections)
- [[KPM Indication Message Types]] (1 shared connections)

## Source Files

- `xDevSM/decorators/report.py`

## Audit Trail

- EXTRACTED: 46 (90%)
- INFERRED: 5 (10%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*