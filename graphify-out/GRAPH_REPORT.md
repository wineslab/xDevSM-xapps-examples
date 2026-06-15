# Graph Report - .  (2026-06-13)

## Corpus Check
- Corpus is ~24,673 words - fits in a single context window. You may not need a graph.

## Summary
- 587 nodes · 976 edges · 45 communities (43 shown, 2 thin omitted)
- Extraction: 73% EXTRACTED · 27% INFERRED · 0% AMBIGUOUS · INFERRED: 264 edges (avg confidence: 0.53)
- Token cost: 37,962 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_xApp Entrypoints & RMR Core|xApp Entrypoints & RMR Core]]
- [[_COMMUNITY_Digital Twin PRB Control Logic|Digital Twin PRB Control Logic]]
- [[_COMMUNITY_KPM Indication Message Types|KPM Indication Message Types]]
- [[_COMMUNITY_xApp Framework Handlers & Namespaces|xApp Framework Handlers & Namespaces]]
- [[_COMMUNITY_Base xApp & SM Decorators|Base xApp & SM Decorators]]
- [[_COMMUNITY_xApp Concepts & Architecture|xApp Concepts & Architecture]]
- [[_COMMUNITY_RC Control Request Builder|RC Control Request Builder]]
- [[_COMMUNITY_KPM Function Definition Builder|KPM Function Definition Builder]]
- [[_COMMUNITY_PRB Control xApp|PRB Control xApp]]
- [[_COMMUNITY_RC Function Definition Types|RC Function Definition Types]]
- [[_COMMUNITY_xApp Report Service|xApp Report Service]]
- [[_COMMUNITY_xApp Control Service|xApp Control Service]]
- [[_COMMUNITY_KPM Indication Message Logging|KPM Indication Message Logging]]
- [[_COMMUNITY_SM Wrapper & UE ID Handling|SM Wrapper & UE ID Handling]]
- [[_COMMUNITY_RC Control Message Types|RC Control Message Types]]
- [[_COMMUNITY_E2 Subscription Manager|E2 Subscription Manager]]
- [[_COMMUNITY_Data Storage (InfluxRedisCSV)|Data Storage (Influx/Redis/CSV)]]
- [[_COMMUNITY_RC Enumerations|RC Enumerations]]
- [[_COMMUNITY_RC Control Header Types|RC Control Header Types]]
- [[_COMMUNITY_KPM Indication Header|KPM Indication Header]]
- [[_COMMUNITY_RC Function Def Decoder|RC Function Def Decoder]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_Config JSON Schema|Config JSON Schema]]
- [[_COMMUNITY_PRB Sweep Script|PRB Sweep Script]]

## God Nodes (most connected - your core abstractions)
1. `ByteArray` - 114 edges
2. `xDevSMRMRXapp` - 42 edges
3. `xAppMonControlContainer` - 32 edges
4. `RadioResourceAllocationControl` - 29 edges
5. `XappKpmFrame` - 28 edges
6. `xAppControlService` - 21 edges
7. `xAppReportService` - 21 edges
8. `meas_value_e` - 21 edges
9. `meas_type_enum` - 21 edges
10. `xAppMonControlContainer` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Digital Twin Validated Control Propagation` --semantically_similar_to--> `Throughput-driven PRB Quota Adaptation`  [INFERRED] [semantically similar]
  digital_twin_prb_xapp/README.md → kpm_prb_xapp/README.md
- `xAppMonControlContainer` --uses--> `xDevSMRMRXapp`  [INFERRED]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → xDevSM/handlers/xDevSM_rmr_xapp.py
- `xAppMonControlContainer` --uses--> `format_action_def_e`  [INFERRED]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → xDevSM/sm_framework/py_oran/kpm/enums.py
- `xAppMonControlContainer` --uses--> `format_ind_msg_e`  [INFERRED]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → xDevSM/sm_framework/py_oran/kpm/enums.py
- `xAppMonControlContainer` --uses--> `meas_type_enum`  [INFERRED]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → xDevSM/sm_framework/py_oran/kpm/enums.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **xDevSM Class Hierarchy** — xdevsm_readme_basexdevsmxapp, xdevsm_readme_xdevsmrmrxapp, xdevsm_readme_basexdevsmwrapper, xdevsm_readme_xappreportservice, xdevsm_readme_xappcontrolservice [EXTRACTED 0.95]
- **RC Control Service Specializations** — xdevsm_readme_xappcontrolservice, xdevsm_readme_radiobearercontrol, xdevsm_readme_radioresourceallocationcontrol, xdevsm_readme_connectedmodemobilitycontrol [EXTRACTED 0.95]
- **xApp to E2AP+RMR Encode/Decode Flow** — xdevsm_readme_xappcontrolservice, xdevsm_readme_sm_framework, xdevsm_readme_ricxappframe [EXTRACTED 0.85]

## Communities (45 total, 2 thin omitted)

### Community 0 - "xApp Entrypoints & RMR Core"
Cohesion: 0.06
Nodes (45): xDevSMRMRXapp, main(), xDevSMRMRXapp, Handle the indication message received from the xApp, xAppMonControlContainer, main(), cond_type_e, enb_type_id_e (+37 more)

### Community 1 - "Digital Twin PRB Control Logic"
Cohesion: 0.08
Nodes (19): load_config(), main(), _normalize_plmn(), Manages KPM monitoring and RC PRB control across a real gNB and its     digital, Record a control sent / acked / failed for later offline analysis., Process a KPM indication. The (gnb, slice) it refers to is identified         vi, Convert whatever the RIC's E2 manager hands us for `plmnId` into the     3-byte, Enqueue a DT control that sets max_prb to `new_max`. (+11 more)

### Community 2 - "KPM Indication Message Types"
Cohesion: 0.09
Nodes (33): cond_union, e2ap_gnb_id_t, e2sm_gummei_t, en_gnb_e2sm_t, enb_e2sm_t, global_enb_id_t, global_gnb_id_t, global_ng_enb_id_t (+25 more)

### Community 3 - "xApp Framework Handlers & Namespaces"
Cohesion: 0.06
Nodes (13): Register a shutdown function to be called on termination.         This is partic, Get E2Node related info. Used to get RAN function description          Parameter, Returns:         ----------         app namespace, Returns:         ----------         plt namespace, Returns:         ----------         xapp name, Returns:         ----------         selected gnb, gnb info, xDevSMRMRXapp, main() (+5 more)

### Community 4 - "Base xApp & SM Decorators"
Cohesion: 0.07
Nodes (10): ABC, NullDecorator, A no-operation decorator that does nothing.     This can be used as a placeholde, BasexDevSMXapp, Abstract method to handle incoming SM-based messages.         Must be implemente, Abstract method for terminating the xApp.         Must be implemented by subclas, Abstract method to retrieve the RAN function description.         Must be implem, Abstract method to send SM-based messages.         Must be implemented by subcla (+2 more)

### Community 5 - "xApp Concepts & Architecture"
Cohesion: 0.08
Nodes (33): Digital Twin Validated Control Propagation, Adaptive PRB Explore-Up Phase, Per-gNB meid ACK Correlation Serialization, Per-slice PRB Control JSON Config, Digital Twin PRB xApp, HO xApp (Handover), KPM Basic xApp, KPM-PRB xApp (+25 more)

### Community 6 - "RC Control Request Builder"
Cohesion: 0.12
Nodes (14): This method encodes a RCControlReq and returns the corresponding binary, # TODO: Needs refactoring based on the type of control action, This method creates the handover control action.         It fills the control re, radio reasource allocation format 1 control for each ue, meaning prb allocation, This method generates the Connected mode mobility control message in format 1., This method generates a control request based on the style selected.         It, RCControlReq, RCControlReqEncoded (+6 more)

### Community 7 - "KPM Function Definition Builder"
Cohesion: 0.10
Nodes (17): action_array_builder(), action_encoder(), action_encoder_from_fun_obj(), ev_trigger_encoder(), Builds an action array from a given hexadecimal XML string.      This function t, Encodes a list of function definitions into a format suitable for the submgr., _remove_undecoded_bytes(), kpm_func_def_cus_t (+9 more)

### Community 8 - "PRB Control xApp"
Cohesion: 0.11
Nodes (4): main(), PRBCotrolXAppDataManager, RadioResourceAllocationControl, Radio Resource Allocation Control Decorator

### Community 9 - "RC Function Definition Types"
Cohesion: 0.09
Nodes (22): call_proc_break_t, call_proc_id_frmt_t, ran_func_def_ctrl_t, ran_func_def_ev_trig_t, ran_func_def_insert_t, ran_func_def_policy_t, ran_func_def_report_t, ran_function_name_t (+14 more)

### Community 10 - "xApp Report Service"
Cohesion: 0.10
Nodes (7): Parameters:         ----------         inventory_name (str): gnb inventory name, Register a callback fired when the async subscription response resolves, This method registers the function to be called when received an indication mess, This method registers the function to be called when received an indication mess, Base handler for DApp Reports., Get decoded ran function description         Parameters:         ----------, xAppReportService

### Community 11 - "xApp Control Service"
Cohesion: 0.15
Nodes (5): Sends a Control Request.          Parameters:         - e2_node_id: Target E2 no, Add RMR rule for control messages, Delete RMR rule for control messages, Get decoded ran function description         Parameters:         ----------, xAppControlService

### Community 12 - "KPM Indication Message Logging"
Cohesion: 0.24
Nodes (6): KpmIndMsg, KpmIndMsgWrapper, meas_record_lst_t, ByteArray, c_size_t, Logger

### Community 13 - "SM Wrapper & UE ID Handling"
Cohesion: 0.17
Nodes (8): c_ulong, BaseXDevSMWrapper, Base class for XDevSM decorators.     This class can be extended to create speci, Values, c_uint32, ue_id_e2sm_t, ue_id_e2sm_t, ByteArray

### Community 14 - "RC Control Message Types"
Cohesion: 0.13
Nodes (14): e2sm_rc_ctrl_msg_frmt_1_t, e2sm_rc_ctrl_msg_frmt_2_t, e2sm_rc_ctrl_msg_union, lst_ran_param_t, ran_param_list_t, ran_param_struct_t, ran_param_val_type_t, ran_param_val_type_union (+6 more)

### Community 15 - "E2 Subscription Manager"
Cohesion: 0.13
Nodes (5): NewSubscriber, Parameters         ----------         subs_params: dict             subscription, init          Parameters         ----------         uri: string             xapp, Unsubscribe             subscription remove          Parameters         --------, ResponseHandler             Starts the response handler and set the callback

### Community 16 - "Data Storage (Influx/Redis/CSV)"
Cohesion: 0.20
Nodes (6): DataManager, Store measurement in Redis hash. ue_id is expected as a label., Extract the scalar value from a meas_record, or None if unsupported type., Atomically append ONE IND to a CSV dict. Every per-IND fixed column         and, Per-record dispatch: Influx + Redis + the right CSV dict.         kind == 'ue', This class manages data storage in InfluxDB, Redis, and CSV.

### Community 17 - "RC Enumerations"
Cohesion: 0.15
Nodes (12): e2sm_rc_ctrl_hdr_e, e2sm_rc_ctrl_msg_e, enb_type_id_e, gnb_type_id_e, ng_enb_type_id_e, ng_ran_node_type_id_e, ran_parameter_def_type_e, ran_parameter_val_type_e (+4 more)

### Community 18 - "RC Control Header Types"
Cohesion: 0.41
Nodes (11): e2sm_plmn_t, ue_id_e2sm_t, e2ap_gnb_id_t, e2ap_gnb_id_t_union, e2sm_rc_ctrl_hdr_frmt_1_t, e2sm_rc_ctrl_hdr_frmt_2_t, e2sm_rc_ctrl_hdr_union, global_enb_id_t (+3 more)

### Community 19 - "KPM Indication Header"
Cohesion: 0.24
Nodes (7): FormatIndHdrE, KpmIndHdr, KpmIndHdrWrapper, KpmRicIndHdrFormat1, TypeUnion, Structure, Union

### Community 21 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 22 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 23 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 24 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 25 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 26 - "Config JSON Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

## Knowledge Gaps
- **65 isolated node(s):** `$schema`, `$id`, `type`, `title`, `required` (+60 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ByteArray` connect `KPM Indication Message Types` to `xApp Entrypoints & RMR Core`, `RC Control Request Builder`, `KPM Function Definition Builder`, `RC Function Definition Types`, `xApp Report Service`, `KPM Indication Message Logging`, `SM Wrapper & UE ID Handling`, `RC Control Message Types`, `RC Control Header Types`, `KPM Indication Header`, `RC Function Def Decoder`?**
  _High betweenness centrality (0.372) - this node is a cross-community bridge._
- **Why does `xAppReportService` connect `xApp Report Service` to `xApp Entrypoints & RMR Core`, `KPM Indication Message Types`, `Base xApp & SM Decorators`, `SM Wrapper & UE ID Handling`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `xDevSMRMRXapp` connect `xApp Framework Handlers & Namespaces` to `xApp Entrypoints & RMR Core`, `Digital Twin PRB Control Logic`, `Base xApp & SM Decorators`, `PRB Control xApp`, `SM Wrapper & UE ID Handling`, `Data Storage (Influx/Redis/CSV)`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 109 inferred relationships involving `ByteArray` (e.g. with `xAppReportService` and `kpm_func_def_cus_t`) actually correct?**
  _`ByteArray` has 109 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `xDevSMRMRXapp` (e.g. with `xDevSMRMRXapp` and `xAppMonControlContainer`) actually correct?**
  _`xDevSMRMRXapp` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `xAppMonControlContainer` (e.g. with `xDevSMRMRXapp` and `format_action_def_e`) actually correct?**
  _`xAppMonControlContainer` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `RadioResourceAllocationControl` (e.g. with `xDevSMRMRXapp` and `xAppMonControlContainer`) actually correct?**
  _`RadioResourceAllocationControl` has 6 INFERRED edges - model-reasoned connections that need verification._