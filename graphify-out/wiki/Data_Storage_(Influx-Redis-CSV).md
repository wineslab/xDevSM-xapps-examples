# Data Storage (Influx/Redis/CSV)

> 14 nodes

## Key Concepts

- **DataManager** (17 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **._store_records()** (6 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **._csv_append_ind()** (4 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **.store_on_redis()** (3 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **._record_value()** (3 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **.store_on_influx()** (2 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **.indication_callback()** (2 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **.__init__()** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **.shutdown()** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **This class manages data storage in InfluxDB, Redis, and CSV.** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **Store measurement in Redis hash. ue_id is expected as a label.** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **Extract the scalar value from a meas_record, or None if unsupported type.** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **Atomically append ONE IND to a CSV dict. Every per-IND fixed column         and** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`
- **Per-record dispatch: Influx + Redis + the right CSV dict.         kind == 'ue'** (1 connections) — `kpm_basic_xapp/kpm_xapp.py`

## Relationships

- [[xApp Entrypoints & RMR Core]] (7 shared connections)
- [[xApp Framework Handlers & Namespaces]] (1 shared connections)

## Source Files

- `kpm_basic_xapp/kpm_xapp.py`

## Audit Trail

- EXTRACTED: 38 (86%)
- INFERRED: 6 (14%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*