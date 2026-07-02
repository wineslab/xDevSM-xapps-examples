# traffic_balancer xApp

A combined **KPM monitor + PRB-quota controller** xApp built on the xDevSM framework. It subscribes to KPM measurements on two slices (LOS / NLOS), runs a swappable policy in a background loop, and applies the chosen `(min_S1, min_S2)` via two ACK-gated RC controls per decision step.

## Status

**v1 skeleton** — no GUI yet. Only the `g6` static policy (the sweep oracle: `min_S1=70, min_S2=30`) is registered. The follow-up pass adds the Flask/Socket.IO dashboard on port 7777 and the other policies (`equal`, `demand_prop`, `linucb`).

## What's wired up

| Layer | File | Purpose |
|---|---|---|
| Main entry | [`traffic_balancer.py`](traffic_balancer.py) | xApp bootstrap, RC + KPM decorators, signal handling, RMR event loop. |
| State | [`balancer/state.py`](balancer/state.py) | Thread-safe `SampleBuffer`, `StateSnapshot`, UE↔slice mapping. |
| Policies | [`balancer/policies.py`](balancer/policies.py) | `Policy` ABC + `StaticG6Policy` (only one in v1). |
| KPM ingest | [`balancer/kpm_ingest.py`](balancer/kpm_ingest.py) | Two `subscribe()` calls (one per slice), per-UE IND decode → `SampleBuffer`. |
| Controller | [`balancer/controller.py`](balancer/controller.py) | Decision loop + `RcSender` ACK-gated dual-slice control. |

## Slice / UE convention (1 UE per slice)

```
ue_1  →  slice nlos   (sst=1, sd=1)
ue_2  →  slice los    (sst=1, sd=16777215)
```

This is hard-coded in [`state.UE_TO_SLICE`](balancer/state.py). The first UE to attach must be the NLOS one — if attach order changes, edit that table.

Why a hardcoded map: this fork doesn't decode `label_info_lst_t.sliceID` from the KPM IND (see [REPORT_ML_xAPP.md §3.1](../../oai-custom-rc/reports/REPORT_ML_xAPP.md)), so we can't tag a slice from the indication payload itself. The pragmatic alternative for the demo is the UE-id mapping above.

## Safety

`sum(min_S1 + min_S2) > 100` crashes the gNB (`ran_func_rc.c:1193`). Two guards:

1. `StaticPolicy.__init__` rejects bad combinations at policy construction.
2. `BalancerController._validate_action` re-clamps every action (defence in depth).

The controller also serialises the two RC sends so the **decreasing** slice always lands first — the running `sum(min)` never exceeds 100 mid-transition.

## Build

Run from the **repo root** (build context must include both this xApp folder and the `xDevSM/` submodule):

```bash
docker build \
  --tag traffic-balancer-xapp:0.1.0-dev \
  --file docker/Dockerfile.traffic_balancer.dev \
  .

docker tag traffic-balancer-xapp:0.1.0-dev angeloferaudo/traffic-balancer-xapp:0.1.0-dev
docker push angeloferaudo/traffic-balancer-xapp:0.1.0-dev
```

Then update `containers[].image.tag` in [`config/config-file.json`](config/config-file.json) if you bumped the tag, and deploy via the OSC RIC ([guide](https://github.com/aferaudo/ORANInABox/wiki/Deploying-xApp)).

## Run (inside the pod)

The dev Dockerfile uses `ENTRYPOINT ["sleep", "infinity"]`, so exec in and start manually:

```bash
oc exec -n ricxapp-j <traffic-balancer-pod> -- \
  python3 /ws/traffic_balancer.py \
    -g gnb_001_001_00000e01 \
    --initial_policy g6 \
    --csv_dir /ws/experiments/traffic_balancer \
    --decision_period_s 1.0 \
    --ack_timeout 1.0
```

## CLI

| Flag | Default | Meaning |
|---|---|---|
| `-g/--gnb_target` | (required) | E2 node id to subscribe to. |
| `--initial_policy` | `g6` | Policy id from the registry (v1: only `g6`). |
| `-r/--route_file` | `./config/uta_rtg.rt` | Static RMR route table. |
| `--csv_dir` | `/ws/experiments/traffic_balancer` | Per-run CSV output dir. |
| `--ack_timeout` | `1.0` | Seconds to wait for an RC ACK before resending. |
| `--decision_period_s` | `1.0` | Seconds between policy decisions. |
| `--boot_delay_s` | `10.0` | Wait before querying the E2 manager. |
| `--log_level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |

## Per-run CSV schema

One row per decision in `{csv_dir}/run_<unix_ts>.csv`:

```
timestamp_ms, policy, min_S1, min_S2, applied, thp_los, thp_nlos, pdcp_los, pdcp_nlos
```

`applied=1` means a fresh control pair was sent this step; `0` means the policy returned the same action as last time, so the gNB was not touched.

## Sanity check the wiring

1. After `oc exec ... python3 /ws/traffic_balancer.py ...`, look for in the xApp log:
   - `[KpmIngest] subscribing Style 4 (per-UE) sst=1 sd=16777215` and `sd=1`
   - `[KpmIngest] first IND for slice=los (ue=ue_2, gnb=...)` and `slice=nlos (ue=ue_1, ...)`
   - `[Controller] applied action min_S1=70 min_S2=30` (once, then no more — StaticG6 returns the same action so we skip subsequent sends)
2. From the gNB log: two `Slice-level PRB quota` lines around the same wall-clock moment as the `[Controller] applied action` line. Use:
   ```bash
   oc logs -n <gnb_ns> <gnb_pod> 2>&1 | \
     grep --line-buffered -E "Received Control Request|Slice-level PRB quota|min_ratio [0-9]+, max_ratio"
   ```
3. CSV grows by one row per second; `applied` is 1 only on the first row after each action change.

## What's deferred to the next pass

- Flask + Flask-SocketIO web GUI on port 7777 with live charts and a policy dropdown.
- `EqualPolicy`, `DemandProportionalPolicy`, `LinUCBPolicy`.
- Cell-wide `RRU.*` samples pushed into the buffer (currently logged-only).
- Optional `--warmstart sweep_test/` for the §5.5 RF bootstrap.
