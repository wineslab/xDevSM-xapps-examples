# xApp Control Service

> 18 nodes

## Key Concepts

- **xAppControlService** (21 connections) — `xDevSM/decorators/control.py`
- **.send()** (4 connections) — `xDevSM/decorators/control.py`
- **.handle()** (3 connections) — `xDevSM/decorators/control.py`
- **.add_rmr_rule()** (3 connections) — `xDevSM/decorators/control.py`
- **.delete_rmr_rule()** (3 connections) — `xDevSM/decorators/control.py`
- **.__init__()** (2 connections) — `xDevSM/decorators/control.py`
- **.get_ran_function_description()** (2 connections) — `xDevSM/decorators/control.py`
- **.generate_control_request()** (2 connections) — `xDevSM/decorators/control.py`
- **.send_control_request_rmr()** (2 connections) — `xDevSM/decorators/control.py`
- **._handle_control_ack_suc()** (2 connections) — `xDevSM/decorators/control.py`
- **._handle_control_ack_fail()** (2 connections) — `xDevSM/decorators/control.py`
- **.terminate()** (2 connections) — `xDevSM/decorators/control.py`
- **.register_control_ack_suc_callback()** (1 connections) — `xDevSM/decorators/control.py`
- **.register_control_ack_fail_callback()** (1 connections) — `xDevSM/decorators/control.py`
- **Get decoded ran function description         Parameters:         ----------** (1 connections) — `xDevSM/decorators/control.py`
- **Sends a Control Request.          Parameters:         - e2_node_id: Target E2 no** (1 connections) — `xDevSM/decorators/control.py`
- **Add RMR rule for control messages** (1 connections) — `xDevSM/decorators/control.py`
- **Delete RMR rule for control messages** (1 connections) — `xDevSM/decorators/control.py`

## Relationships

- [[SM Wrapper & UE ID Handling]] (4 shared connections)
- [[Base xApp & SM Decorators]] (1 shared connections)
- [[xApp Entrypoints & RMR Core]] (1 shared connections)
- [[xApp Framework Handlers & Namespaces]] (1 shared connections)
- [[PRB Control xApp]] (1 shared connections)

## Source Files

- `xDevSM/decorators/control.py`

## Audit Trail

- EXTRACTED: 49 (91%)
- INFERRED: 5 (9%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*