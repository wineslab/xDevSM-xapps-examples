# Graph Report - .  (2026-07-03)

## Corpus Check
- 24 files · ~32,084 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 773 nodes · 1329 edges · 61 communities (56 shown, 5 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 315 edges (avg confidence: 0.54)
- Token cost: 125,390 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_xApp Runtime & Indication Handling|xApp Runtime & Indication Handling]]
- [[_COMMUNITY_Digital Twin PRB Control Logic|Digital Twin PRB Control Logic]]
- [[_COMMUNITY_KPM E2SM Node-ID Structs|KPM E2SM Node-ID Structs]]
- [[_COMMUNITY_RMR xApp Config & E2 Node Info|RMR xApp Config & E2 Node Info]]
- [[_COMMUNITY_KPM Function Definition Builder|KPM Function Definition Builder]]
- [[_COMMUNITY_KPM Metrics Aggregation|KPM Metrics Aggregation]]
- [[_COMMUNITY_xApp Catalog & Design Concepts|xApp Catalog & Design Concepts]]
- [[_COMMUNITY_RC Control Request Encoding|RC Control Request Encoding]]
- [[_COMMUNITY_PRB Control xApp (InfluxRedis)|PRB Control xApp (Influx/Redis)]]
- [[_COMMUNITY_Traffic Balancer Controller|Traffic Balancer Controller]]
- [[_COMMUNITY_Traffic Balancer State Buffer|Traffic Balancer State Buffer]]
- [[_COMMUNITY_RC Function Definition Structs|RC Function Definition Structs]]
- [[_COMMUNITY_KPM Ingest (sub_id routing)|KPM Ingest (sub_id routing)]]
- [[_COMMUNITY_xApp Report Service (KPM)|xApp Report Service (KPM)]]
- [[_COMMUNITY_Contextual Bandit & Demand Policies|Contextual Bandit & Demand Policies]]
- [[_COMMUNITY_xApp Control Service (RC)|xApp Control Service (RC)]]
- [[_COMMUNITY_Base Wrapper & Mock UE IDs|Base Wrapper & Mock UE IDs]]
- [[_COMMUNITY_KPM Indication Message Decode|KPM Indication Message Decode]]
- [[_COMMUNITY_KPM Basic DataManager (storage)|KPM Basic DataManager (storage)]]
- [[_COMMUNITY_RC Control Message Structs|RC Control Message Structs]]
- [[_COMMUNITY_Subscription Client (NewSubscriber)|Subscription Client (NewSubscriber)]]
- [[_COMMUNITY_RC Enums|RC Enums]]
- [[_COMMUNITY_Abstract xApp Interface|Abstract xApp Interface]]
- [[_COMMUNITY_StaticEqual PRB Policies|Static/Equal PRB Policies]]
- [[_COMMUNITY_RC Control Header Structs|RC Control Header Structs]]
- [[_COMMUNITY_ACK-gated RC Sender|ACK-gated RC Sender]]
- [[_COMMUNITY_Traffic Balancer Entrypoint|Traffic Balancer Entrypoint]]
- [[_COMMUNITY_Null Decorator|Null Decorator]]
- [[_COMMUNITY_RC Function Def Wrapper|RC Function Def Wrapper]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xApp Config Schema|xApp Config Schema]]
- [[_COMMUNITY_xDevSM Utility Helpers|xDevSM Utility Helpers]]
- [[_COMMUNITY_Metrics Hook Sink|Metrics Hook Sink]]
- [[_COMMUNITY_DT Control Pattern Concepts|DT Control Pattern Concepts]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 54|Community 54]]

## God Nodes (most connected - your core abstractions)
1. `ByteArray` - 114 edges
2. `xDevSMRMRXapp` - 42 edges
3. `XappKpmFrame` - 34 edges
4. `xAppMonControlContainer` - 32 edges
5. `RadioResourceAllocationControl` - 29 edges
6. `StateSnapshot` - 29 edges
7. `xAppControlService` - 26 edges
8. `xAppReportService` - 24 edges
9. `BalancerController` - 23 edges
10. `SampleBuffer` - 22 edges

## Surprising Connections (you probably didn't know these)
- `digital_twin xAppMonControlContainer` --semantically_similar_to--> `kpm_prb xAppMonControlContainer`  [INFERRED] [semantically similar]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → kpm_prb_xapp/kpm_prb_xapp.py
- `Digital Twin Validated Control Propagation` --semantically_similar_to--> `Throughput-driven PRB Quota Adaptation`  [INFERRED] [semantically similar]
  digital_twin_prb_xapp/README.md → kpm_prb_xapp/README.md
- `DT-validate-before-propagate control pattern` --rationale_for--> `digital_twin xAppMonControlContainer`  [EXTRACTED]
  CLAUDE.md → digital_twin_prb_xapp/digital_twin_prb_xapp.py
- `kpm_basic DataManager` --semantically_similar_to--> `kpm_prb xAppMonControlContainer`  [INFERRED] [semantically similar]
  kpm_basic_xapp/kpm_xapp.py → kpm_prb_xapp/kpm_prb_xapp.py
- `xAppMonControlContainer` --uses--> `xDevSMRMRXapp`  [INFERRED]
  digital_twin_prb_xapp/digital_twin_prb_xapp.py → xDevSM/handlers/xDevSM_rmr_xapp.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **KPM -> policy -> RC ACK -> CSV decision loop** — kpm_ingest_kpmingest, state_samplebuffer, controller_balancercontroller, policies_policy, controller_rcsender [EXTRACTED 0.95]
- **PRB-quota policy family** — policies_policy, policies_staticpolicy, policies_demandproportionalpolicy, policies_linucbpolicy, policies_get_policy [EXTRACTED 0.90]
- **Digital-twin validated PRB control flow** — digital_twin_prb_xapp_xappmoncontrolcontainer, kpm_frame_xappkpmframe, control_xappcontrolservice, digital_twin_prb_xapp_dt_state_machine [INFERRED 0.85]
- **KPM indication decode + metrics pipeline** — report_xappreportservice, kpm_frame_xappkpmframe, kpmindicationhdr_kpmindhdrwrapper, metrics_hook_record_e2ap, kpm_metrics_kpmmetrics [INFERRED 0.75]
- **KPM indication-consuming xApp containers** — kpm_xapp_datamanager, kpm_prb_xapp_xappmoncontrolcontainer, digital_twin_prb_xapp_xappmoncontrolcontainer [INFERRED 0.75]

## Communities (61 total, 5 thin omitted)

### Community 0 - "xApp Runtime & Indication Handling"
Cohesion: 0.05
Nodes (47): xDevSMRMRXapp, main(), xDevSMRMRXapp, Handle the indication message received from the xApp, xAppMonControlContainer, main(), cond_type_e, enb_type_id_e (+39 more)

### Community 1 - "Digital Twin PRB Control Logic"
Cohesion: 0.08
Nodes (20): load_config(), main(), _normalize_plmn(), Manages KPM monitoring and RC PRB control across a real gNB and its     digital, Record a control sent / acked / failed for later offline analysis., Process a KPM indication. The (gnb, slice) it refers to is identified         vi, Convert whatever the RIC's E2 manager hands us for `plmnId` into the     3-byte, Enqueue a DT control that sets max_prb to `new_max`. (+12 more)

### Community 2 - "KPM E2SM Node-ID Structs"
Cohesion: 0.09
Nodes (33): cond_union, e2ap_gnb_id_t, e2sm_gummei_t, en_gnb_e2sm_t, enb_e2sm_t, global_enb_id_t, global_gnb_id_t, global_ng_enb_id_t (+25 more)

### Community 3 - "RMR xApp Config & E2 Node Info"
Cohesion: 0.06
Nodes (13): Register a shutdown function to be called on termination.         This is partic, Get E2Node related info. Used to get RAN function description          Parameter, Returns:         ----------         app namespace, Returns:         ----------         plt namespace, Returns:         ----------         xapp name, Returns:         ----------         selected gnb, gnb info, xDevSMRMRXapp, main() (+5 more)

### Community 4 - "KPM Function Definition Builder"
Cohesion: 0.07
Nodes (24): action_array_builder(), action_encoder(), action_encoder_from_fun_obj(), ev_trigger_encoder(), Builds an action array from a given hexadecimal XML string.      This function t, Encodes a list of function definitions into a format suitable for the submgr., _remove_undecoded_bytes(), kpm_func_def_cus_t (+16 more)

### Community 5 - "KPM Metrics Aggregation"
Cohesion: 0.11
Nodes (13): _Agg, KpmMetrics, _percentile(), End-to-end metrics for the KPM xApp.  Ported from the spectrum-dApp xApp metrics, E2AP decode time + message size; also the per-indication anchor for         thro, KPM-SM (header+message) decode time., collect_start_us: KPM header collectStartTime (µs, CLOCK_REALTIME on the, Linear-interpolation percentile (no numpy dependency). (+5 more)

### Community 6 - "xApp Catalog & Design Concepts"
Cohesion: 0.09
Nodes (32): Digital Twin Validated Control Propagation, Adaptive PRB Explore-Up Phase, Per-gNB meid ACK Correlation Serialization, Per-slice PRB Control JSON Config, Digital Twin PRB xApp, HO xApp (Handover), KPM Basic xApp, KPM-PRB xApp (+24 more)

### Community 7 - "RC Control Request Encoding"
Cohesion: 0.12
Nodes (14): This method encodes a RCControlReq and returns the corresponding binary, # TODO: Needs refactoring based on the type of control action, This method creates the handover control action.         It fills the control re, radio reasource allocation format 1 control for each ue, meaning prb allocation, This method generates the Connected mode mobility control message in format 1., This method generates a control request based on the style selected.         It, RCControlReq, RCControlReqEncoded (+6 more)

### Community 8 - "PRB Control xApp (Influx/Redis)"
Cohesion: 0.08
Nodes (5): main(), PRBCotrolXAppDataManager, Get all UE IDs associated with a specific gNB, Get all unique gNB IDs from the database, RadioResourceAllocationControl

### Community 9 - "Traffic Balancer Controller"
Cohesion: 0.13
Nodes (14): BalancerController, ControlOutcome, Decision loop for the traffic_balancer xApp.  Runs in its own daemon thread. Eac, Runs the policy/control loop in a background thread., Proportional-fair utility:  log(thp_S1) + log(thp_S2).          Floored at 1.0 k, Clamp to a safe (sum <= 100, non-negative, <=100 each)., Per-step record written to the run CSV., Policy (+6 more)

### Community 10 - "Traffic Balancer State Buffer"
Cohesion: 0.12
Nodes (12): In-memory state for the traffic_balancer xApp.  Per-UE KPM samples flow in from, Thread-safe ring buffer of `Sample`s. Producers (the KPM ingest     threads) pus, Block until at least one sample has arrived. Returns False on timeout., Most recent sample per slice., Last n samples (any slice). For debugging / GUI., One KPM record for one UE at one timestamp, attributed to a slice     via the su, Latest sample per slice, keyed by `sd` (int)., Latest RLC DL delay for the slice (units: 0.01 ms per 3GPP). (+4 more)

### Community 11 - "RC Function Definition Structs"
Cohesion: 0.09
Nodes (22): call_proc_break_t, call_proc_id_frmt_t, ran_func_def_ctrl_t, ran_func_def_ev_trig_t, ran_func_def_insert_t, ran_func_def_policy_t, ran_func_def_report_t, ran_function_name_t (+14 more)

### Community 12 - "KPM Ingest (sub_id routing)"
Cohesion: 0.12
Nodes (12): _decode_meas_type(), KpmIngest, KPM ingestion with sub_id routing.  We subscribe twice — once per (sst, sd) — an, Subscribe to Style 4 + Style 1 once per sd; track each         submgr_sub_id ->, Decode the meas type name (a C ByteArray) to a Python str., Decode an integer/real meas record value to a Python float., Owns the KPM subscriptions, the sub_id↔sd bridges, and the IND     callback. Pus, Framework hook: called once the RIC has set up the subscription.         Bridges (+4 more)

### Community 13 - "xApp Report Service (KPM)"
Cohesion: 0.11
Nodes (7): Parameters:         ----------         inventory_name (str): gnb inventory name, Register a callback fired when the async subscription response resolves, This method registers the function to be called when received an indication mess, Base handler for DApp Reports., Get decoded ran function description         Parameters:         ----------, xAppReportService, get_c_byte_array_from_py_byte_string

### Community 14 - "Contextual Bandit & Demand Policies"
Cohesion: 0.15
Nodes (10): DemandProportionalPolicy, LinUCBPolicy, 7-arm contextual bandit over the static-sweep grid.      Arms (the report's §5.3, Return (min_S1, min_S2). Must satisfy min_S1 + min_S2 <= 100., Scale min ratios by recent PDCP-DL volume per slice.      Reads the latest sampl, ndarray, Proportional-fair utility reward, Policy (ABC) (+2 more)

### Community 15 - "xApp Control Service (RC)"
Cohesion: 0.14
Nodes (6): BaseXDevSMWrapper, Sends a Control Request.          Parameters:         - e2_node_id: Target E2 no, Add RMR rule for control messages, Delete RMR rule for control messages, Get decoded ran function description         Parameters:         ----------, xAppControlService

### Community 16 - "Base Wrapper & Mock UE IDs"
Cohesion: 0.16
Nodes (9): c_uint32, c_ulong, BaseXDevSMWrapper, Base class for XDevSM decorators.     This class can be extended to create speci, Values, c_uint32, ue_id_e2sm_t, ue_id_e2sm_t (+1 more)

### Community 17 - "KPM Indication Message Decode"
Cohesion: 0.24
Nodes (6): KpmIndMsg, KpmIndMsgWrapper, meas_record_lst_t, ByteArray, c_size_t, Logger

### Community 18 - "KPM Basic DataManager (storage)"
Cohesion: 0.19
Nodes (7): DataManager, Store measurement in Redis hash. ue_id is expected as a label., Extract the scalar value from a meas_record, or None if unsupported type., Atomically append ONE IND to a CSV dict. Every per-IND fixed column         and, Per-record dispatch: Influx + Redis + the right CSV dict.         kind == 'ue', This class manages data storage in InfluxDB, Redis, and CSV., Store measurement in Redis hash

### Community 19 - "RC Control Message Structs"
Cohesion: 0.13
Nodes (14): e2sm_rc_ctrl_msg_frmt_1_t, e2sm_rc_ctrl_msg_frmt_2_t, e2sm_rc_ctrl_msg_union, lst_ran_param_t, ran_param_list_t, ran_param_struct_t, ran_param_val_type_t, ran_param_val_type_union (+6 more)

### Community 20 - "Subscription Client (NewSubscriber)"
Cohesion: 0.13
Nodes (5): NewSubscriber, Parameters         ----------         subs_params: dict             subscription, init          Parameters         ----------         uri: string             xapp, Unsubscribe             subscription remove          Parameters         --------, ResponseHandler             Starts the response handler and set the callback

### Community 21 - "RC Enums"
Cohesion: 0.15
Nodes (12): e2sm_rc_ctrl_hdr_e, e2sm_rc_ctrl_msg_e, enb_type_id_e, gnb_type_id_e, ng_enb_type_id_e, ng_ran_node_type_id_e, ran_parameter_def_type_e, ran_parameter_val_type_e (+4 more)

### Community 22 - "Abstract xApp Interface"
Cohesion: 0.18
Nodes (6): ABC, BasexDevSMXapp, Abstract method to handle incoming SM-based messages.         Must be implemente, Abstract method for terminating the xApp.         Must be implemented by subclas, Abstract method to retrieve the RAN function description.         Must be implem, Abstract method to send SM-based messages.         Must be implemented by subcla

### Community 23 - "Static/Equal PRB Policies"
Cohesion: 0.20
Nodes (8): EqualPolicy, Always returns the same (min_S1, min_S2)., Always (50, 50). The naive fairness baseline., Static sweep oracle: (70, 30). PF utility peaks here per sweep_test., StaticG6Policy, StaticPolicy, get_policy, sum(min)<=100 gNB crash guard

### Community 24 - "RC Control Header Structs"
Cohesion: 0.41
Nodes (11): e2sm_plmn_t, ue_id_e2sm_t, e2ap_gnb_id_t, e2ap_gnb_id_t_union, e2sm_rc_ctrl_hdr_frmt_1_t, e2sm_rc_ctrl_hdr_frmt_2_t, e2sm_rc_ctrl_hdr_union, global_enb_id_t (+3 more)

### Community 25 - "ACK-gated RC Sender"
Cohesion: 0.22
Nodes (6): ACK-gated retry pattern, Wraps `RadioResourceAllocationControl` with the ACK-gated retry pattern.      Th, Set (sd, min), call send(), wait for ACK, retry on timeout.          `ran_ue_id`, RcSender, traffic-balancer-xapp descriptor, main

### Community 26 - "Traffic Balancer Entrypoint"
Cohesion: 0.31
Nodes (7): available_policies(), get_policy(), Policy implementations for the traffic_balancer xApp.  A policy maps a `StateSna, Look up a policy by short name. Raises KeyError on unknown name., main(), parse_args(), traffic_balancer xApp — combined KPM + RC with a swappable policy layer.  v1 ske

### Community 30 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 31 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 32 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 33 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 34 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 35 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 36 - "xApp Config Schema"
Cohesion: 0.29
Nodes (6): $id, properties, required, $schema, title, type

### Community 38 - "Metrics Hook Sink"
Cohesion: 0.33
Nodes (3): Optional, decoupled metrics sink for decode-stage timing.  The xDevSM framework, Register the metrics object (or None to disable)., set_sink()

### Community 39 - "DT Control Pattern Concepts"
Cohesion: 0.40
Nodes (5): DT-validate-before-propagate control pattern, DT PRB state machine, _normalize_plmn, digital_twin xAppMonControlContainer, decode_meid

## Knowledge Gaps
- **79 isolated node(s):** `$schema`, `$id`, `type`, `title`, `required` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ByteArray` connect `KPM E2SM Node-ID Structs` to `xApp Runtime & Indication Handling`, `KPM Function Definition Builder`, `RC Control Request Encoding`, `RC Function Definition Structs`, `xApp Report Service (KPM)`, `Base Wrapper & Mock UE IDs`, `KPM Indication Message Decode`, `RC Control Message Structs`, `RC Control Header Structs`, `RC Function Def Wrapper`?**
  _High betweenness centrality (0.314) - this node is a cross-community bridge._
- **Why does `XappKpmFrame` connect `xApp Runtime & Indication Handling` to `Digital Twin PRB Control Logic`, `KPM Function Definition Builder`, `DT Control Pattern Concepts`, `xApp Report Service (KPM)`, `Base Wrapper & Mock UE IDs`, `KPM Basic DataManager (storage)`, `Traffic Balancer Entrypoint`, `xDevSM Module Files`?**
  _High betweenness centrality (0.267) - this node is a cross-community bridge._
- **Why does `xAppMonControlContainer` connect `Digital Twin PRB Control Logic` to `xApp Runtime & Indication Handling`, `PRB Control xApp (Influx/Redis)`, `RMR xApp Config & E2 Node Info`, `KPM Metrics Aggregation`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Are the 109 inferred relationships involving `ByteArray` (e.g. with `xAppReportService` and `kpm_func_def_cus_t`) actually correct?**
  _`ByteArray` has 109 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `xDevSMRMRXapp` (e.g. with `xDevSMRMRXapp` and `xAppMonControlContainer`) actually correct?**
  _`xDevSMRMRXapp` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `XappKpmFrame` (e.g. with `xDevSMRMRXapp` and `xAppMonControlContainer`) actually correct?**
  _`XappKpmFrame` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `xAppMonControlContainer` (e.g. with `xDevSMRMRXapp` and `format_action_def_e`) actually correct?**
  _`xAppMonControlContainer` has 7 INFERRED edges - model-reasoned connections that need verification._