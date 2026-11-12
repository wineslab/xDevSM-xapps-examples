# CCC REPORT test xApp

This xApp is an end-to-end test of the E2SM-CCC REPORT service of the OCUDU gNB. E2SM-CCC is the O-RAN Cell Configuration and Control service model (O-RAN.WG3.TS.E2SM-CCC). The xApp uses the xDevSM CCC API for all subscriptions, indications, and controls.

The xApp runs once and stops. It logs one `PASS` or `FAIL` line per check and a `SUMMARY` line. Its exit code is the result:

- 0: all checks pass.
- 1: a check fails.
- 2: the configuration is not valid.

## What the xApp does

1. It waits for a connected E2 node and finds the E2SM-CCC RAN function by the OCUDU OID `1.3.6.1.4.1.53148.1.6.2.4`.
2. It decodes the RAN Function Definition and checks the structures, attributes, styles, and formats that OCUDU announces.
3. It sends 21 RIC subscriptions, each with one REPORT action.
4. It waits for the uponSubscription and periodic indications and checks their content.
5. It sends an O-RRMPolicyRatio CONTROL that changes the rRMPolicyMaxRatio of one slice, and then a second CONTROL that restores the original value.
6. After each CONTROL, it checks the uponChange and periodic indications, the old and new values, and the eventTime order.
7. It deletes its subscriptions.

If the run stops after the first CONTROL, the xApp sends the restore CONTROL before it deletes its subscriptions.

## Subscriptions

| Subscription | REPORT style | Event trigger | Structure | Report type |
| --- | --- | --- | --- | --- |
| `S1-F1-O-GNBDUFunction-{all,change}` | 1, node level | Format 1, node configuration change | O-GNBDUFunction | all, change |
| `S1-F3-O-GNBDUFunction-{all,change}` | 1, node level | Format 3, periodic | O-GNBDUFunction | all, change |
| `S2-F2-<structure>-{all,change}` | 2, cell level | Format 2, cell configuration change | O-NRCellDU, O-BWP, O-RRMPolicyRatio | all, change |
| `S2-F3-<structure>-{all,change}` | 2, cell level | Format 3, periodic | O-NRCellDU, O-BWP, O-RRMPolicyRatio | all, change |
| `S2-F2-O-RRMPolicyRatio-change-max-ratio-cell` | 2 | Format 2 on rRMPolicyMaxRatio of the tested cell | O-RRMPolicyRatio, rRMPolicyMaxRatio only | change |
| `S2-F2-O-RRMPolicyRatio-all-on-min-ratio` | 2 | Format 2 on rRMPolicyMinRatio | O-RRMPolicyRatio | all |
| `S2-F2-O-BWP-all-cell-priority` | 2 | Format 2 | O-NRCellDU for all cells, O-BWP for the tested cell | all |
| `reject-S2-F1` | 2 | Format 1 | O-RRMPolicyRatio | all |
| `reject-F2-unknown-attribute` | 2 | Format 2 on arfcnDL of O-RRMPolicyRatio | O-RRMPolicyRatio | all |

The two `reject-` subscriptions must fail: a node configuration change trigger does not apply to a cell-level action, and O-RRMPolicyRatio has no arfcnDL attribute.

## Checks and the OCUDU features that they cover

| OCUDU feature | Checks |
| --- | --- |
| RAN Function Definition | OID and name. REPORT Styles 1 and 2 with their formats. Event Trigger Styles 1 and 2. CONTROL Style 2 for O-RRMPolicyRatio only. Every DU cell. |
| Admission | Each valid subscription is admitted. Each `reject-` subscription fails. |
| REPORT Style 1 | Indication Message Format 1 with one O-GNBDUFunction and its attributes |
| REPORT Style 2 | Indication Message Format 2 with every cell, one O-NRCellDU and two initial BWPs. Each RRM policy member has a PRB_DL and a PRB_UL O-RRMPolicyRatio with equal values. |
| uponSubscription for change triggers only | The first indication of a change subscription is uponSubscription, and only one arrives. A periodic subscription sends periodic indications only. |
| uponSubscription reports every instance | Also for report type change, with no change type and no old values |
| Periodic trigger | Report type all sends every instance at each period, about one period apart. Report type change sends nothing while nothing changes. |
| uponChange | After each CONTROL, each O-RRMPolicyRatio change subscription sends one uponChange. The two instances of the slice have change type modification with the old and new values. |
| Report type all and change | Report type all also reports the unchanged instances with change type none. Report type change reports only the two changed instances. |
| Only the listed attributes | The max-ratio subscription reports and compares rRMPolicyMaxRatio only. |
| Trigger attributes and cells | If the CONTROL changes the reported min ratio, the min-ratio trigger sends uponChange. Otherwise it sends nothing. The max-ratio trigger applies to the tested cell only. |
| Cell entry priority | The cell-priority subscription reports O-BWP for the tested cell and O-NRCellDU for the other cells. |
| Only the listed structures | O-GNBDUFunction, O-NRCellDU and O-BWP subscriptions send no change report for an O-RRMPolicyRatio CONTROL. |
| Periodic reports of a change | Report type change sends one periodic indication per change. Report type all sends the change in exactly one periodic indication. |
| eventTime | 16 hexadecimal digits. It does not decrease in a subscription. All uponChange indications of one CONTROL have the same eventTime. uponChange is after uponSubscription. A periodic report of a change is not before its uponChange. |
| CONTROL | A RIC Control Acknowledge for each CONTROL. After the restore, the slice has the values that the DU reports for the original ratios. |

The xApp expects the values that the DU reports after a CONTROL. The DU converts a ratio to PRBs and reports the smallest ratio of that PRB count, and it keeps no dedicated PRBs. The xApp gets the PRB count from the numberOfRBs of the initial DL BWP.

The xApp cannot cover these features end to end:

- uponChange of O-GNBDUFunction, O-NRCellDU and O-BWP. A CCC CONTROL cannot change them. A change of the cell state can cover O-NRCellDU, for example a cell stop with the OCUDU remote control. The xApp does not stop cells.
- Additions and deletions. They need a new RRM policy member or a new cell while the gNB runs. The xDevSM unit tests decode them.

## Configuration

The xApp reads its configuration from `controls.ccc_report_test` in the xApp descriptor (`$CONFIG_FILE`, default `config/config-file.json`). A command-line option overrides the descriptor value.

| Setting | Option | Default | Meaning |
| --- | --- | --- | --- |
| `gnb_target` | `-g`, `--gnb-target` | first connected E2 node | E2 node inventory name |
| `nci` | `--nci` | first cell of the RAN Function Definition | NR Cell Identity of the cell to control, for example `0x00066C000` |
| `sst`, `sd` | `--sst`, `--sd` | first RRM policy member | slice to control |
| `resource_type` | `--resource-type` | `PRB_DL` | resourceType of the CONTROL |
| `control_max_ratio` | `--control-max-ratio` | 50 | rRMPolicyMaxRatio that the first CONTROL sets |
| `period_ms` | `--period-ms` | 1000 | period of the periodic triggers, at least 10 |
| `periodic_count` | `--periodic-count` | 2 | periodic indications to receive before the CONTROL |
| `e2_node_timeout_s` | `--e2-node-timeout-s` | 60 | wait for a connected E2 node |
| `subscription_timeout_s` | `--subscription-timeout-s` | 10 | wait for the subscription responses |
| `indication_timeout_s` | `--indication-timeout-s` | 5 | wait for an uponSubscription or uponChange indication |
| `control_ack_timeout_s` | `--control-ack-timeout-s` | 5 | wait for a RIC Control Acknowledge |
| `log_level` | `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

If the configured max ratio does not change the reported value, the xApp tries 50, 25, 75, 100 and 10 in this order.

## Layout

```
ccc_report_test_xapp/
  ccc_report_test_xapp.py   entry point: xDevSM wiring, RMR handler, port to the RIC
  ccc_test/                 test logic, importable without RMR
    config.py               descriptor and command-line configuration
    plan.py                 the subscriptions
    journal.py              thread-safe record of indications, responses and acknowledges
    structures.py           what OCUDU reports for each structure
    checks.py               the checks
    scenario.py             the phases of the run, with deadlines
    report.py               PASS and FAIL lines and the summary
  config/                   xApp descriptor, schema and RMR route table
  tests/                    unit tests with the JSON of the OCUDU unit tests and an OCUDU-like E2 node
  pyproject.toml            uv project, Python 3.11
```

## Local development

The uv project installs xdevsm 0.1.9 or later from PyPI.

Run the unit tests:

```bash
cd ccc_report_test_xapp
uv run pytest
```

On macOS, `tests/test_port.py` is skipped because ricxappframe needs RMR and inotify, which are Linux only. The other tests need only the pure-Python CCC codec of xDevSM. To run all tests, use the image:

```bash
docker run --rm --platform linux/amd64 ccc-report-test-xapp:0.1.0-dev uv run --with pytest pytest -q
```

## Build

The image installs xdevsm from PyPI. Run from the repository root:

```bash
docker build --platform linux/amd64 \
  --tag ccc-report-test-xapp:0.1.0-dev \
  --file docker/Dockerfile.ccc_report_test.dev .
```

The image writes the xdevsm version to `/ws/xdevsm_version.log`. The image uses Debian bookworm because apt fails on bullseye: the bullseye-security archive no longer serves the packages of its index.

## Run against an OCUDU gNB

1. Build OCUDU from the branch `feature/e2sm_ccc_report`.
2. In the gNB configuration, enable the DU E2 agent and E2SM-CCC (`e2: enable_du_e2: true` and `e2sm_ccc_enabled: true`), and set the E2Term address.
3. Configure at least one slice in `cell_cfg: slicing`. Without a slice, the cell has no O-RRMPolicyRatio instance and the CONTROL part fails.
4. Start the gNB and make sure that it is connected to the Near-RT RIC.
5. Build the image (see Build). Push it to a registry that the cluster can read, and set `containers[].image` in `config/config-file.json`.
6. Onboard and install the xApp with the OSC tools. A guide is in the [ORANInABox wiki](https://github.com/aferaudo/ORANInABox/wiki/Deploying-xApp).
7. Start the test in the pod:

   ```bash
   kubectl exec -it <xapp-pod> -n ricxapp-j -- uv run python ccc_report_test_xapp.py -g <E2 node inventory name>
   ```

8. Read the `FAIL` lines and the `SUMMARY` line. The exit code of the command is the result.

The test changes the rRMPolicyMaxRatio of one slice for a few seconds. UEs on that slice can get less throughput while it runs.
