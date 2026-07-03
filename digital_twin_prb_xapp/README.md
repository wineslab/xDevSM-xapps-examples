# Digital Twin PRB xApp

This xApp is an evolution of the simple [`kpm_prb_xapp`](../kpm_prb_xapp/) (restored from <https://github.com/wineslab/xDevSM-xapps-examples/tree/dev/kpm_prb_xapp>). It adds digital-twin validation, per-slice configuration, ACK-timeout retries, and adaptive PRB exploration. The CLI flags, config schema, and behaviour are documented below.

A Radio Resource Allocation Control (RC) and KPM xApp built using the xDevSM framework.

This xApp dynamically manages Physical Resource Block (PRB) allocation **per slice** on a real gNB and its **digital twin (DT)**. Every control action is first validated on the DT, and only replayed on the real gNB after the DT acknowledges it successfully.

It works by:

1. **Monitoring**: subscribes to KPM (Format-3, Format-4 action definitions) on both the real gNB and the DT, with one subscription per (gNB, slice).
2. **Per-slice control on the DT**: when the throughput on a DT slice exceeds the threshold configured for that slice, the xApp queues a slice-level PRB-quota reduction and sends it to the DT.
3. **Validated propagation**: on `RIC_CONTROL_ACK` from the DT, the same policy is queued and sent to the real gNB for that slice. On `RIC_CONTROL_FAILURE`, the real gNB is left untouched.
4. **Serialization**: at most one control is in flight per gNB (option-A correlation by `meid`). Per-(gNB, slice) FIFO queues absorb back-to-back over-threshold ticks; the queue drains as ACKs arrive.

### CLI options

```
-r <route_file>, --route_file <route_file>
                      path of xApp route file
-c <csv_file>, --csv_file <csv_file>
                      base path of csv files written on exit.
                      Two files are produced: `<path>` with per-UE KPM
                      measurements (incl. timestamp_ms, sst, sd) and
                      `<path-stem>_controls<ext>` with every control PDU
                      sent on either gNB plus its ACK/failure event,
                      so KPM and controls can be joined on time/slice.
-e <event_trigger_period>, --event_trigger <event_trigger_period>
                      event trigger period in seconds
-f <config_file>, --config <config_file>
                      path of the PRB control JSON config
                      (default: ./config/prb_control_conf.json)
-l <log_level>, --log_level <log_level>
                      Log level
-g <gnb_target>, --gnb_target <gnb_target>
                      real gNB to subscribe to (required)
-G <gnb_dt_target>, --gnb_dt_target <gnb_dt_target>
                      digital twin gNB to subscribe to; control is applied
                      here first and only replayed on the real gNB after a
                      successful ACK (required)
```

### Example invocation

```
python3 digital_twin_prb_xapp.py \
    -r ./config/uta_rtg.rt \
    -f ./config/prb_control_conf.json \
    -c kpm.csv \
    -g <real_gnb_inventory_name> \
    -G <dt_gnb_inventory_name>
```

### Config file

The xApp reads a JSON file (default: `./config/prb_control_conf.json`) that describes how PRB control should behave per slice. Up to two slices are supported, all sharing the same SST and differing only by SD.

Example:

```json
{
  "sst": 1,
  "plmn_real": "00F110",
  "plmn_dt": "00F110",
  "slices": [
    {
      "sd": 0,
      "max_down_throughput_mbps": 50,
      "max_up_throughput_mbps": null,
      "min_prb_policy_ratio": 10,
      "max_prb_policy_ratio": 100,
      "dedicated_prb_policy_ratio": 5,
      "prb_step": 5,
      "under_threshold_gap": 10,
      "prb_step_up": 2,
      "improvement_epsilon": 1,
      "convergence_indications": 5
    },
    {
      "sd": 1,
      "max_down_throughput_mbps": 30,
      "max_up_throughput_mbps": null,
      "min_prb_policy_ratio": 10,
      "max_prb_policy_ratio": 100,
      "dedicated_prb_policy_ratio": 5,
      "prb_step": 5,
      "under_threshold_gap": 10,
      "prb_step_up": 2,
      "improvement_epsilon": 1,
      "convergence_indications": 5
    }
  ]
}
```

#### Top-level fields

- **`sst`** *(int, required)* — Slice/Service Type, shared by every entry in `slices`. Used as the `sST` field in the RC slice identifier sent in every control PDU.
  - *Example:* `"sst": 1`.

- **`plmn_real`** / **`plmn_dt`** *(string, optional)* — Static PLMN identity (6 BCD hex chars, e.g. `"00F110"` for MCC=001 MNC=01) to embed in the RC control PDU sent to the real and DT gNBs respectively. If provided, these override whatever the E2 manager reports for `globalNbId.plmnId`. The xApp also accepts the digit form (`"00101"`) or a dict (`{"mcc":"001","mnc":"01"}`); both are normalized to the 6-hex-char BCD form before encoding. Use these if the auto-derived PLMN doesn't match what the gNB actually serves.
  - *Example:* `"plmn_real": "00F110"`, `"plmn_dt": "00F110"`.

- **`slices`** *(array, required, length 1–2)* — Per-slice configuration. Each entry distinguishes itself by `sd`.

#### Per-slice fields (each entry of `slices`)

- **`sd`** *(int, required)* — Slice Differentiator. Together with `sst` and the gNB's PLMN it uniquely identifies a slice on each gNB. The xApp opens one KPM subscription per `(gNB, sd)` filtered with this SST/SD pair.
  - *Example:* `"sd": 0` for the default slice, `"sd": 1` for a second slice.

- **`max_down_throughput_mbps`** *(number, required)* — Downlink throughput threshold for this slice, in Mb/s, **measured on the DT**. When the aggregated `DRB.UEThpDl` of the DT slice exceeds this value, the xApp triggers a PRB step-down.
  - *Example:* `"max_down_throughput_mbps": 50` — start throttling when DT DL exceeds 50 Mb/s.

- **`max_up_throughput_mbps`** *(number or `null`, optional)* — Uplink threshold in Mb/s. Set to `null` (or omit) to disable the uplink check for the slice.
  - *Example:* `"max_up_throughput_mbps": null` — only downlink drives the controller.

- **`min_prb_policy_ratio`** *(int, required, 0–100)* — Minimum PRB percentage the slice may receive. The xApp will never step `max_prb_policy_ratio` below `min_prb_policy_ratio + prb_step`; it stops reducing PRB once that floor is reached. This value is also sent verbatim as the `minPRBPolicyRatio` field of the slice-level PRB-quota control.
  - *Example:* `"min_prb_policy_ratio": 10` — never drop the slice below 10%.

- **`max_prb_policy_ratio`** *(int, required, 0–100)* — Initial / upper bound for the slice's PRB percentage. The xApp uses this as the starting `current_max_prb` and decrements it by `prb_step` on every breach.
  - *Example:* `"max_prb_policy_ratio": 100` — start the slice unconstrained, scale down from there.

- **`dedicated_prb_policy_ratio`** *(int, required, 0–100)* — Sent as the `dedicatedPRBPolicyRatio` of the control PDU. Reserved per-slice PRB share.
  - *Example:* `"dedicated_prb_policy_ratio": 5`.

- **`prb_step`** *(int, optional, default `5`)* — How many percentage points to subtract from `current_max_prb` on each breach.
  - *Example:* `"prb_step": 5` — five-point steps per breach.

- **`convergence_indications`** *(int, optional, default `5`)* — Number of consecutive KPM indications that must confirm a stable DT state before the xApp propagates anything to the real gNB (or before it switches to the explore-up phase). Counts DT-side PRB-allocation attempts: nothing reaches the OTA gNB until the DT has shown the same outcome for this many ticks in a row. Any contrary observation (e.g. `dl` going back above the threshold) resets the counter.
  - *Example:* `"convergence_indications": 5` — wait for 5 stable indications before declaring convergence.

- **`under_threshold_gap`** *(int, optional, default `10`)* — After the stability window confirms `dl ≤ threshold`, if `threshold − dl` is greater than this value, the xApp enters the **explore-up** phase to try to recover unused PRBs. Same scale as `max_down_throughput_mbps` (i.e. the xApp's internal throughput units — `DRB.UEThpDl / 1024`).
  - *Example:* `"under_threshold_gap": 10` — only explore upwards if we ended at least 10 below the threshold.

- **`prb_step_up`** *(int, optional, default `2`)* — Step size used while in the explore-up phase. Smaller than `prb_step` so we approach the operating point gently.
  - *Example:* `"prb_step_up": 2`.

- **`improvement_epsilon`** *(int, optional, default `1`)* — Minimum increase in `dl` (in the same units as the threshold) required between two consecutive explore-up steps to count as "the workload made use of the extra PRBs". If the delta stays below this for `convergence_indications` consecutive ticks, the xApp reverts to the last validated `safe_max_prb` and propagates it to the real gNB.
  - *Example:* `"improvement_epsilon": 1`.

### Notes on the control flow

- The xApp keeps an independent `current_max_prb` per (gNB, slice). On a successful DT ACK, it commits the new value to the DT's slice state, queues the replay on the real gNB, and only commits the real gNB's `current_max_prb` once the real-gNB ACK arrives.
- ACK correlation is by meid (RMR-level): there is at most one outstanding control per gNB at any time. Additional over-threshold events on the same gNB pile up in the per-(gNB, slice) queue and drain as ACKs come in.
- If `dt` and `real` gNBs use different PLMNs, the xApp swaps `rc_func.plmn_identity` automatically before each send. The slice key in the control PDU is `(PLMN, SST, SD)`, so the xApp targets the right slice on each gNB.
